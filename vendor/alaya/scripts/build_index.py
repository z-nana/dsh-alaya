#!/usr/bin/env python3
"""Build complete three-tier indexes with safe incremental publication."""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.runtime import (  # noqa: E402
    AlayaError,
    commit_text_bundle,
    knowledge_paths,
    load_effective_config,
    read_json,
    resolve_kb_root,
)
from lib.index_utils import (  # noqa: E402
    all_paired_blocks,
    block,
    block_status,
    outside_generated_blocks,
    paired_block,
)
from lib.yaml_utils import (  # noqa: E402
    category_file_for,
    extract_description_from_body,
    extract_title,
    get_description,
    get_tags,
    is_knowledge_card,
    read_frontmatter,
    rebuild_content,
    set_description,
)


BASE = "AUTO (base)"
REFINED = "AUTO (refined)"
MANUAL = "MANUAL"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Build Alaya category and total indexes")
    parser.add_argument("--kb-root", help="Knowledge-base root override")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--full", action="store_true", help="Scan every category")
    mode.add_argument("--category", help="Rescan one category and republish the complete total index")
    mode.add_argument("--mark-description-updated", metavar="CATEGORY")
    parser.add_argument("--check-only", action="store_true", help="Report without writing")
    parser.add_argument("--confirm-removals", action="store_true", help="Allow published categories to disappear")
    return parser.parse_args(argv)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def discover_categories(wiki_dir):
    root = Path(wiki_dir)
    return [
        path.name for path in sorted(root.iterdir(), key=lambda item: item.name.casefold())
        if path.is_dir() and not path.name.startswith(".") and not path.name.startswith("~$")
    ] if root.is_dir() else []


def semantic_fingerprint(card_rows):
    payload = [
        {"path": row["path"], "title": row["title"], "description": row["description"], "tags": row["tags"]}
        for row in card_rows
    ]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def semantic_map(card_rows):
    result = {}
    for row in card_rows:
        value = json.dumps(
            {"title": row["title"], "description": row["description"], "tags": row["tags"]},
            ensure_ascii=False,
            sort_keys=True,
        )
        result[row["path"]] = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return result


def changed_items(baseline, current):
    keys = set(baseline or {}) | set(current or {})
    return sum(1 for key in keys if (baseline or {}).get(key) != (current or {}).get(key))


def scan_category(wiki_dir, category, write_descriptions=True):
    directory = Path(wiki_dir) / category
    rows = []
    card_writes = []
    manifest = []
    for path in sorted(directory.glob("*.md"), key=lambda item: item.name.casefold()):
        if not is_knowledge_card(path):
            continue
        stat = path.stat()
        manifest.append([path.name, stat.st_size, stat.st_mtime_ns])
        result = read_frontmatter(path)
        if not result:
            raise AlayaError("Card has invalid frontmatter: %s" % path)
        content, yaml_str, dash = result
        body = content[dash + 3:].lstrip("\r\n")
        description = get_description(yaml_str)
        if not description:
            description = extract_description_from_body(body) or ("Knowledge card: %s" % path.stem)
            if write_descriptions:
                new_yaml = set_description(yaml_str, description)
                card_writes.append((path, rebuild_content(new_yaml, dash, content)))
        rows.append({
            "path": path.name,
            "name": path.stem,
            "title": extract_title(yaml_str, path.stem),
            "description": description,
            "tags": get_tags(yaml_str),
        })
    manifest_hash = hashlib.sha256(json.dumps(manifest, ensure_ascii=False).encode("utf-8")).hexdigest()
    return rows, card_writes, manifest_hash


def threshold_for(size, config):
    thresholds = config.get("knowledge", {}).get("description_change_thresholds", [])
    for item in thresholds:
        maximum = item.get("max_cards")
        if maximum is None or size <= int(maximum):
            return int(item.get("changes", 1))
    return 10


def generate_base_description(category, rows):
    tags = []
    for row in rows:
        for tag in row["tags"]:
            if tag not in tags:
                tags.append(tag)
    topic = "、".join(tags[:5]) if tags else "本类别主题"
    return "本类别收录 %d 张知识卡片，主要覆盖 %s。可从卡片描述选择与当前问题最相关的内容继续阅读。" % (len(rows), topic)


def category_content(category, rows, existing="", extra_manual=None):
    for name in (BASE, REFINED, MANUAL):
        if block_status(existing, name) == "unpaired":
            raise AlayaError("Category page contains an unpaired %s block: %s" % (name, category))
    refined = paired_block(existing, REFINED)
    manuals = all_paired_blocks(existing, MANUAL)
    outside = outside_generated_blocks(existing)
    if outside and outside not in manuals:
        manuals.append(outside)
    for value in extra_manual or []:
        if value and value not in manuals:
            manuals.append(value)
    lines = [generate_base_description(category, rows), "", "## Cards"]
    for row in rows:
        lines.append("- [[%s]] — %s" % (row["name"], row["description"]))
    sections = ["# %s" % category, ""]
    if refined:
        sections.extend([block(REFINED, refined), ""])
    sections.append(block(BASE, "\n".join(lines)))
    for manual in manuals:
        sections.extend(["", block(MANUAL, manual)])
    return "\n".join(sections).rstrip() + "\n"


def category_description(content, category):
    refined = paired_block(content, REFINED)
    if refined:
        return " ".join(line.strip() for line in refined.splitlines() if line.strip())
    base = paired_block(content, BASE)
    if base:
        before_cards = base.split("## Cards", 1)[0]
        return " ".join(line.strip() for line in before_cards.splitlines() if line.strip())
    return "Category %s" % category


def generate_total_index(wiki_dir, categories, pending_category_content):
    entries = ["## Categories", ""]
    missing = []
    for category in categories:
        path = Path(wiki_dir) / category / category_file_for(category)
        content = pending_category_content.get(category)
        if content is None:
            try:
                content = path.read_text(encoding="utf-8-sig")
            except OSError:
                missing.append(str(path))
                continue
        description = category_description(content, category)
        entries.extend([
            "- [[%s/%s|%s]]" % (category, category_file_for(category)[:-3], category),
            "  %s" % description,
            "",
        ])
    if missing:
        raise AlayaError("Cannot publish total index; category indexes are missing: %s" % ", ".join(missing))
    body = block(BASE, "\n".join(entries).rstrip())
    return "# Knowledge Index\n\n%s\n" % body


def load_metadata(paths):
    value = read_json(paths["alaya"] / ".index_metadata.json", default={}) or {}
    if not isinstance(value, dict):
        raise AlayaError(".index_metadata.json must contain an object")
    value["_legacy_upgrade"] = (
        value.get("version") != "3.0.0" or not isinstance(value.get("published_categories"), list)
    )
    value["version"] = "3.0.0"
    value.setdefault("categories", {})
    value.setdefault("published_categories", [])
    return value


def update_description_state(meta, category, rows, manifest_hash, config):
    state = dict(meta.get("categories", {}).get(category, {}))
    current = semantic_map(rows)
    baseline = state.get("description_baseline")
    if baseline is None:
        pending = max(1, len(rows)) if category not in meta.get("published_categories", []) else 0
        baseline = current if pending == 0 else {}
    else:
        pending = changed_items(baseline, current)
    if pending and not state.get("pending_since"):
        state["pending_since"] = now_iso()
    if not pending:
        state.pop("pending_since", None)
    state.update({
        "card_count": len(rows),
        "manifest_fingerprint": manifest_hash,
        "semantic_fingerprint": semantic_fingerprint(rows),
        "current_cards": current,
        "pending_changes": pending,
        "description_threshold": threshold_for(max(1, len(baseline)), config),
        "last_indexed_at": now_iso(),
    })
    meta.setdefault("categories", {})[category] = state


def due_categories(meta, config):
    due = []
    max_wait = int(config.get("maintenance", {}).get("description_refresh_max_wait_days", 3))
    now = datetime.now(timezone.utc)
    for category, state in meta.get("categories", {}).items():
        pending = int(state.get("pending_changes", 0))
        if pending <= 0:
            continue
        threshold = int(state.get("description_threshold", 1))
        started = state.get("pending_since")
        age_due = False
        if started:
            try:
                parsed = datetime.fromisoformat(started.replace("Z", "+00:00"))
                age_due = (now - parsed).days >= max_wait
            except ValueError:
                pass
        if pending >= threshold or age_due:
            due.append(category)
    return sorted(due, key=str.casefold)


def merge_legacy_manual(category_dir, category):
    old = category_dir / "_category.md"
    new = category_dir / category_file_for(category)
    if not old.is_file() or old.resolve() == new.resolve():
        return [], None
    old_content = old.read_text(encoding="utf-8-sig")
    for name in (BASE, REFINED, MANUAL):
        if block_status(old_content, name) == "unpaired":
            raise AlayaError("Legacy category page contains an unpaired %s block: %s" % (name, old))
    manuals = all_paired_blocks(old_content, MANUAL)
    outside = outside_generated_blocks(old_content)
    if outside:
        raise AlayaError("Legacy category page has unmarked content; migration stopped without changing files: %s" % old)
    return manuals, old


def mark_description(paths, config, category, check_only=False):
    meta = load_metadata(paths)
    rows, _writes, manifest = scan_category(paths["wiki"], category, write_descriptions=False)
    state = meta.setdefault("categories", {}).setdefault(category, {})
    state["description_baseline"] = semantic_map(rows)
    state["current_cards"] = semantic_map(rows)
    state["pending_changes"] = 0
    state.pop("pending_since", None)
    state["description_updated_at"] = now_iso()
    state["manifest_fingerprint"] = manifest
    meta["stale_descriptions"] = due_categories(meta, config)
    meta.pop("_legacy_upgrade", None)
    if not check_only:
        commit_text_bundle(
            paths["alaya"], "description-baseline-%s" % category,
            [(paths["alaya"] / ".index_metadata.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")],
        )
    print("Description baseline updated: %s" % category)


def build(paths, config, category=None, check_only=False, confirm_removals=False):
    categories = discover_categories(paths["wiki"])
    if category and category not in categories:
        raise AlayaError("Category directory does not exist: %s" % category)
    meta = load_metadata(paths)
    if meta.pop("_legacy_upgrade", False):
        # Existing published libraries start with a truthful baseline instead of
        # receiving one false "every description is stale" alert on upgrade.
        old_index = paths["wiki"] / "index.md"
        old_published = set()
        if old_index.is_file():
            old_content = old_index.read_text(encoding="utf-8-sig")
            old_published = set(re.findall(r"^- \[\[([^/]+)/", paired_block(old_content, BASE), re.MULTILINE))
        meta["published_categories"] = sorted(old_published or set(categories), key=str.casefold)
        meta["categories"] = {
            key: value for key, value in meta.get("categories", {}).items()
            if key in categories
        }
    published = set(meta.get("published_categories", []))
    removed = sorted(published - set(categories), key=str.casefold)
    if removed and not confirm_removals:
        raise AlayaError("Category removal requires --confirm-removals: %s" % ", ".join(removed))

    targets = categories if category is None else [category]
    writes = []
    pending_content = {}
    legacy_backups = []
    for current in targets:
        rows, card_writes, manifest = scan_category(paths["wiki"], current, write_descriptions=True)
        writes.extend(card_writes)
        category_dir = paths["wiki"] / current
        category_path = category_dir / category_file_for(current)
        existing = category_path.read_text(encoding="utf-8-sig") if category_path.is_file() else ""
        legacy_manual, legacy_path = merge_legacy_manual(category_dir, current)
        content = category_content(current, rows, existing, legacy_manual)
        pending_content[current] = content
        writes.append((category_path, content))
        if legacy_path:
            backup = legacy_path.with_suffix(legacy_path.suffix + ".bak")
            counter = 1
            while backup.exists():
                backup = legacy_path.with_suffix(legacy_path.suffix + ".bak.%d" % counter)
                counter += 1
            legacy_backups.append((legacy_path, backup))
        update_description_state(meta, current, rows, manifest, config)

    total = generate_total_index(paths["wiki"], categories, pending_content)
    # Validate the generated category set before it can replace the old index.
    generated = set(re.findall(r"^- \[\[([^/]+)/", paired_block(total, BASE), re.MULTILINE))
    if generated != set(categories):
        raise AlayaError("Generated total-index categories do not match disk categories")
    writes.append((paths["wiki"] / "index.md", total))
    meta["published_categories"] = categories
    meta["last_build"] = now_iso()
    meta["stale_descriptions"] = due_categories(meta, config)
    writes.append((paths["alaya"] / ".index_metadata.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n"))

    print("Categories on disk: %d" % len(categories))
    print("Categories in generated index: %d" % len(generated))
    print("Categories rescanned: %s" % (", ".join(targets) if targets else "none"))
    print("Description refresh due: %s" % (", ".join(meta["stale_descriptions"]) or "none"))
    if check_only:
        print("Check only: no files were changed.")
        return

    commit_text_bundle(paths["alaya"], "build-index-%s" % datetime.now().strftime("%Y%m%d%H%M%S"), writes)
    for source, backup in legacy_backups:
        os.replace(str(source), str(backup))
    print("Index publication complete.")


def main(argv=None):
    args = parse_args(argv)
    try:
        root = resolve_kb_root(args.kb_root)
        paths = knowledge_paths(root)
        config = load_effective_config(root)
        if args.mark_description_updated:
            mark_description(paths, config, args.mark_description_updated, args.check_only)
        else:
            build(
                paths,
                config,
                category=args.category,
                check_only=args.check_only,
                confirm_removals=args.confirm_removals,
            )
        return 0
    except (AlayaError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
