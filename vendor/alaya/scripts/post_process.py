#!/usr/bin/env python3
"""Safely publish one host-generated semantic knowledge card."""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_index import build as build_index  # noqa: E402
from lib.runtime import (  # noqa: E402
    AlayaError,
    commit_text_bundle,
    knowledge_paths,
    load_effective_config,
    resolve_kb_root,
    sha256_file,
    verified_copy,
)
from lib.yaml_utils import (  # noqa: E402
    extract_description_from_body,
    get_description,
    get_field,
    read_frontmatter,
    rebuild_content,
    remove_field,
    set_description,
    set_field,
    slugify,
    yaml_quote,
)
from perfume import run_xunxi  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Publish one Markdown card into Alaya")
    parser.add_argument("card")
    parser.add_argument("--category", required=True)
    parser.add_argument("--kb-root")
    parser.add_argument("--copy-raw", choices=("yes", "no"), required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _existing_hash(path):
    result = read_frontmatter(path)
    return get_field(result[1], "source_hash") if result else None


def _unique_target(base, source_hash):
    if not base.exists():
        return base, "create"
    if _existing_hash(base) == source_hash:
        return base, "duplicate"
    alternate = base.with_name("%s-%s%s" % (base.stem, source_hash[:8], base.suffix))
    if alternate.exists():
        if _existing_hash(alternate) == source_hash:
            return alternate, "duplicate"
        raise AlayaError("Stable card collision target differs: %s" % alternate)
    return alternate, "create"


def _raw_target(paths, source, source_hash):
    base = paths["raw"] / (slugify(source.stem) + source.suffix.lower())
    if not base.exists() or sha256_file(base) == source_hash:
        return base
    alternate = base.with_name("%s-%s%s" % (base.stem, source_hash[:8], base.suffix))
    if alternate.exists() and sha256_file(alternate) != source_hash:
        raise AlayaError("Stable raw collision target differs: %s" % alternate)
    return alternate


def _resolve_original(value, source_card, kb_root):
    if not value:
        return None
    candidate = Path(value).expanduser()
    candidates = [candidate] if candidate.is_absolute() else [source_card.parent / candidate, Path(kb_root) / candidate]
    for item in candidates:
        try:
            resolved = item.resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved
    return None


def publish_card(card_path, category, kb_root, copy_raw=False, dry_run=False):
    source_card = Path(card_path).expanduser().resolve()
    result = read_frontmatter(source_card)
    if not result:
        raise AlayaError("Card has no strict frontmatter")
    content, yaml_str, dash = result
    body = content[dash + 3:].lstrip("\r\n")
    paths = knowledge_paths(kb_root)
    category_slug = slugify(category)

    original_value = get_field(yaml_str, "source_path") or get_field(yaml_str, "source_pdf")
    original = _resolve_original(original_value, source_card, paths["root"])
    if copy_raw and original is None:
        raise AlayaError("--copy-raw yes requires a valid local source_path or source_pdf in the card")
    source_hash = sha256_file(original) if original else sha256_file(source_card)
    base_target = paths["wiki"] / category_slug / (slugify(source_card.stem) + ".md")
    target, action = _unique_target(base_target, source_hash)
    raw_target = _raw_target(paths, original, source_hash) if copy_raw else None

    if dry_run:
        message = "[%s] Would write %s" % (action, target)
        if raw_target:
            message += " and copy source to %s" % raw_target
        return action, str(target), category_slug, message
    if action == "duplicate":
        return action, str(target), category_slug, "Duplicate content already exists; no files changed"

    today = date.today().isoformat()
    description = get_description(yaml_str) or extract_description_from_body(body) or ("Knowledge card: %s" % target.stem)
    yaml_str = set_description(yaml_str, description)
    for key, value in (
        ("seed_type", "REFINED"),
        ("created_by", "post_process"),
        ("strength", get_field(yaml_str, "strength") or "0.5"),
        ("last_activated", get_field(yaml_str, "last_activated") or today),
        ("strength_updated_at", get_field(yaml_str, "strength_updated_at") or today),
        ("activation_count", get_field(yaml_str, "activation_count") or "0"),
        ("source_hash", source_hash),
    ):
        yaml_str = set_field(yaml_str, key, value)
    if original:
        yaml_str = remove_field(remove_field(yaml_str, "source_pdf"), "source_file")
        if copy_raw:
            if not raw_target.exists() or sha256_file(raw_target) != source_hash:
                verified_copy(original, raw_target)
            yaml_str = remove_field(yaml_str, "source_path")
            yaml_str = set_field(yaml_str, "source_file", yaml_quote(raw_target.relative_to(paths["root"]).as_posix()))
        else:
            yaml_str = set_field(yaml_str, "source_path", yaml_quote(str(original)))

    commit_text_bundle(
        paths["alaya"],
        "semantic-import-%s-%s" % (category_slug, source_hash[:16]),
        [(target, rebuild_content(yaml_str, dash, content))],
    )
    return action, str(target), category_slug, "Card published"


def main(argv=None):
    args = parse_args(argv)
    try:
        root = resolve_kb_root(args.kb_root)
        config = load_effective_config(root)
        action, target, category, message = publish_card(
            args.card, args.category, root, copy_raw=args.copy_raw == "yes", dry_run=args.dry_run
        )
        print(message)
        if args.dry_run or action == "duplicate":
            return 0
        try:
            build_index(knowledge_paths(root), config, category=category)
        except Exception as exc:
            print("[ERROR] Card was committed but index publication is pending: %s" % exc, file=sys.stderr)
            return 1
        print("Description choice: update the affected category now, or accumulate until its threshold/3-day deadline.")
        try:
            run_xunxi(knowledge_paths(root), config)
        except Exception as exc:
            print("[WARN] Piggyback xunxi is pending: %s" % exc, file=sys.stderr)
        print("Published target: %s" % target)
        return 0
    except (AlayaError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
