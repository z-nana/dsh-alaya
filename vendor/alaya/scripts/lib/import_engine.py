"""Read-only import planning followed by serialized safe publication."""

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from lib.format_converter import detect_format, extract_text, pdf_available
from lib.runtime import (
    AlayaError,
    FileLock,
    commit_text_bundle,
    sha256_file,
    verified_copy,
)
from lib.yaml_utils import (
    discover_related_cards,
    extract_description_from_body,
    get_field,
    read_frontmatter,
    slugify,
    yaml_quote,
)


SUPPORTED = {"markdown", "text", "pdf"}


def collect_files(source):
    source = Path(source).expanduser().resolve()
    if source.is_file():
        return [source]
    if source.is_dir():
        return [
            path for path in sorted(source.rglob("*"), key=lambda item: str(item).casefold())
            if path.is_file()
        ]
    raise AlayaError("Import source does not exist: %s" % source)


def _existing_source_hash(path):
    result = read_frontmatter(path)
    if not result:
        return None
    return get_field(result[1], "source_hash")


def _unique_slug(category_dir, base_slug, source_hash, reserved):
    candidate = base_slug
    target = category_dir / (candidate + ".md")
    identity = candidate.casefold()
    if identity in reserved:
        if reserved[identity] == source_hash:
            return candidate, "duplicate"
        candidate = "%s-%s" % (base_slug, source_hash[:8])
        target = category_dir / (candidate + ".md")
        identity = candidate.casefold()
    if target.exists():
        if _existing_source_hash(target) == source_hash:
            reserved[identity] = source_hash
            return candidate, "duplicate"
        candidate = "%s-%s" % (base_slug, source_hash[:8])
        target = category_dir / (candidate + ".md")
        identity = candidate.casefold()
        if target.exists() and _existing_source_hash(target) == source_hash:
            reserved[identity] = source_hash
            return candidate, "duplicate"
        if target.exists():
            raise AlayaError("Stable collision target already exists with different content: %s" % target)
    reserved[identity] = source_hash
    return candidate, "create"


def _raw_target(raw_dir, source, source_hash, reserved):
    base = slugify(source.stem)
    extension = source.suffix.lower()
    name = base + extension
    target = raw_dir / name
    key = name.casefold()
    if key in reserved and reserved[key] != source_hash:
        name = "%s-%s%s" % (base, source_hash[:8], extension)
        target = raw_dir / name
        key = name.casefold()
    if target.exists():
        existing_hash = sha256_file(target)
        if existing_hash != source_hash:
            name = "%s-%s%s" % (base, source_hash[:8], extension)
            target = raw_dir / name
            key = name.casefold()
            if target.exists() and sha256_file(target) != source_hash:
                raise AlayaError("Stable raw collision target differs: %s" % target)
    reserved[key] = source_hash
    return target


def plan_import(paths, source, category, copy_raw, parallel=False, workers=4, max_chars=None):
    """Build a complete plan.  It performs no directory creation or write."""
    files = collect_files(source)
    category_slug = slugify(category)
    category_dir = paths["wiki"] / category_slug
    reserved_cards = {}
    reserved_hashes = {}
    if category_dir.is_dir():
        for path in category_dir.glob("*.md"):
            existing_hash = _existing_source_hash(path)
            reserved_cards[path.stem.casefold()] = existing_hash or "existing"
            if existing_hash:
                reserved_hashes.setdefault(existing_hash, path.stem)
    reserved_raw = {}
    if paths["raw"].is_dir():
        for path in paths["raw"].iterdir():
            if path.is_file():
                reserved_raw[path.name.casefold()] = sha256_file(path)

    items = []
    for path in files:
        fmt = detect_format(str(path))
        if fmt not in SUPPORTED:
            items.append({"source": str(path), "format": fmt or "unsupported", "action": "llm_required"})
            continue
        if fmt == "pdf" and not pdf_available():
            items.append({"source": str(path), "format": fmt, "action": "pdf_dependency_required"})
            continue
        source_hash = sha256_file(path)
        if source_hash in reserved_hashes:
            slug, action = reserved_hashes[source_hash], "duplicate"
        else:
            slug, action = _unique_slug(category_dir, slugify(path.stem), source_hash, reserved_cards)
            reserved_hashes[source_hash] = slug
        raw_target = _raw_target(paths["raw"], path, source_hash, reserved_raw) if copy_raw else None
        items.append({
            "source": str(path),
            "format": fmt,
            "source_hash": source_hash,
            "slug": slug,
            "target": str(category_dir / (slug + ".md")),
            "raw_target": str(raw_target) if raw_target else None,
            "action": action,
        })
    return {
        "version": 1,
        "category": category_slug,
        "copy_raw": bool(copy_raw),
        "parallel": bool(parallel),
        "workers": int(workers),
        "max_chars": int(max_chars) if max_chars is not None else None,
        "items": items,
    }


def summarize_plan(plan):
    counts = {}
    for item in plan["items"]:
        counts[item["action"]] = counts.get(item["action"], 0) + 1
    lines = [
        "Import plan (read-only)",
        "  category: %s" % plan["category"],
        "  copy source files to raw: %s" % ("yes" if plan["copy_raw"] else "no"),
    ]
    for action in sorted(counts):
        lines.append("  %s: %d" % (action, counts[action]))
    for item in plan["items"]:
        lines.append("  [%s] %s -> %s" % (item["action"], item["source"], item.get("target") or "LLM handling"))
        if item.get("raw_target"):
            lines.append("    raw -> %s" % item["raw_target"])
    return "\n".join(lines)


def _extract_candidate(item, paths, category, copy_raw, max_chars=None):
    source = Path(item["source"])
    text = extract_text(str(source), max_chars=max_chars)
    if text is None:
        raise AlayaError("Content extraction failed: %s" % source)
    description = extract_description_from_body(text) or ("Imported content from %s" % source.name)
    today = date.today().isoformat()
    source_fields = []
    if copy_raw:
        relative = Path(item["raw_target"]).relative_to(paths["root"]).as_posix()
        source_fields.append("source_file: %s" % yaml_quote(relative))
    else:
        source_fields.append("source_path: %s" % yaml_quote(str(source)))
    source_fields.extend([
        "source_type: %s" % item["format"],
        "source_hash: %s" % item["source_hash"],
    ])
    body = "# %s\n\n## Content\n\n%s\n" % (source.stem, text)
    links = discover_related_cards(str(paths["wiki"]), text, source_category=category)
    if links:
        body += "\n## Related knowledge\n\n"
        for related_category, name, _context in links:
            body += "- [[../%s/%s]]\n" % (related_category, name)
    frontmatter = [
        "---",
        "title: %s" % yaml_quote(source.stem),
        "description: %s" % yaml_quote(description),
        "seed_type: REFINED",
        "created_by: script_import",
        "strength: 0.5",
        "last_activated: %s" % today,
        "strength_updated_at: %s" % today,
        "activation_count: 0",
    ] + source_fields + ["created: %s" % today, "updated: %s" % today, "---", ""]
    return "\n".join(frontmatter) + "\n" + body


def _plan_still_valid(item):
    if item["action"] != "create":
        return True
    return not Path(item["target"]).exists()


def apply_import_plan(paths, plan):
    actionable = [item for item in plan["items"] if item["action"] == "create"]
    unsupported = [item for item in plan["items"] if item["action"] in ("llm_required", "pdf_dependency_required")]
    if unsupported:
        raise AlayaError("Plan contains items requiring LLM handling or the optional PDF dependency")
    for item in actionable:
        if not _plan_still_valid(item):
            raise AlayaError("Import plan is stale; target appeared after preview: %s" % item["target"])

    with FileLock(paths["alaya"] / ".import.lock", stale_seconds=1800):
        if plan.get("parallel") and len(actionable) > 1:
            with ThreadPoolExecutor(max_workers=max(1, int(plan.get("workers", 4)))) as executor:
                contents = list(executor.map(
                    lambda item: _extract_candidate(
                        item, paths, plan["category"], plan["copy_raw"], plan.get("max_chars")
                    ),
                    actionable,
                ))
        else:
            contents = [
                _extract_candidate(item, paths, plan["category"], plan["copy_raw"], plan.get("max_chars"))
                for item in actionable
            ]

        if plan["copy_raw"]:
            for item in actionable:
                raw_target = Path(item["raw_target"])
                if raw_target.exists() and sha256_file(raw_target) == item["source_hash"]:
                    continue
                verified_copy(item["source"], raw_target)

        writes = [(Path(item["target"]), content) for item, content in zip(actionable, contents)]
        if writes:
            commit_text_bundle(
                paths["alaya"],
                "import-%s-%s" % (plan["category"], date.today().isoformat()),
                writes,
            )
    return {
        "created": len(actionable),
        "duplicates": sum(item["action"] == "duplicate" for item in plan["items"]),
        "llm_required": sum(item["action"] == "llm_required" for item in plan["items"]),
        "pdf_dependency_required": sum(item["action"] == "pdf_dependency_required" for item in plan["items"]),
        "category": plan["category"],
    }
