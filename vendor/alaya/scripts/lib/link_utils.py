"""Obsidian-style wiki-link parsing and deterministic resolution."""

import re
import json
from pathlib import Path

from lib.yaml_utils import get_field, read_frontmatter


WIKILINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")


def markdown_files(wiki_dir):
    root = Path(wiki_dir)
    return [
        path for path in sorted(root.rglob("*.md"), key=lambda item: str(item).casefold())
        if not any(part.startswith(".") for part in path.relative_to(root).parts)
        and not path.name.startswith("~$")
        and not path.name.lower().endswith((".bak.md", ".tmp.md"))
    ]


def build_link_index(wiki_dir):
    root = Path(wiki_dir).resolve()
    by_path = {}
    by_name = {}
    by_alias = {}
    for path in markdown_files(root):
        relative = path.relative_to(root).with_suffix("")
        normalized = relative.as_posix()
        by_path[normalized.casefold()] = normalized
        by_name.setdefault(path.stem.casefold(), []).append(normalized)
        if path.stem.endswith("_category"):
            by_alias.setdefault(path.stem[:-9].casefold(), []).append(normalized)
        result = read_frontmatter(path)
        if result:
            for field in ("aliases", "alias"):
                value = get_field(result[1], field)
                if not value:
                    continue
                aliases = []
                if value.startswith("[") and value.endswith("]"):
                    try:
                        aliases = json.loads(value.replace("'", '"'))
                    except (ValueError, TypeError):
                        aliases = [item.strip(" '\"") for item in value[1:-1].split(",")]
                else:
                    aliases = [value]
                for alias in aliases:
                    if alias:
                        by_alias.setdefault(str(alias).casefold(), []).append(normalized)
    return {"root": root, "by_path": by_path, "by_name": by_name, "by_alias": by_alias}


def split_link(raw):
    target_and_anchor, separator, alias = raw.partition("|")
    target, anchor_separator, anchor = target_and_anchor.partition("#")
    return target.strip(), ("#" + anchor if anchor_separator else ""), ("|" + alias if separator else "")


def resolve_link(index, source_path, raw):
    root = index["root"]
    target, anchor, alias = split_link(raw)
    normalized = target.replace("\\", "/").strip()
    if not normalized:
        actual = Path(source_path).resolve().relative_to(root).with_suffix("").as_posix()
        return {"status": "ok", "raw": raw, "target": target, "resolved": actual, "replacement": raw}
    if normalized.lower().endswith(".md"):
        normalized = normalized[:-3]
    if normalized.casefold().startswith("wiki/"):
        normalized = normalized[5:]

    candidates = []
    alias_match = False
    if "/" in normalized:
        if normalized.startswith("../") or normalized.startswith("./"):
            relative_source = Path(source_path).resolve().parent
            candidate_path = (relative_source / normalized).resolve()
            try:
                candidate = candidate_path.relative_to(root).as_posix()
            except ValueError:
                return {"status": "broken", "raw": raw, "target": target}
        else:
            candidate = normalized.strip("/")
        actual = index["by_path"].get(candidate.casefold())
        if actual:
            candidates = [actual]
    else:
        source_relative = Path(source_path).resolve().parent.relative_to(root)
        local = (source_relative / normalized).as_posix()
        local_actual = index["by_path"].get(local.casefold())
        if local_actual:
            candidates = [local_actual]
        else:
            candidates = list(index["by_name"].get(normalized.casefold(), []))
            if not candidates:
                candidates = list(index["by_alias"].get(normalized.casefold(), []))
                alias_match = bool(candidates)

    candidates = list(dict.fromkeys(candidates))

    if not candidates:
        return {"status": "broken", "raw": raw, "target": target}
    if len(candidates) > 1:
        return {"status": "ambiguous", "raw": raw, "target": target, "candidates": candidates}

    actual = candidates[0]
    if alias_match:
        return {"status": "ok", "raw": raw, "target": target, "resolved": actual, "replacement": raw}
    if "/" in normalized:
        if normalized.startswith("../") or normalized.startswith("./"):
            actual_path = root / (actual + ".md")
            suggested = Path(
                __import__("os").path.relpath(str(actual_path.with_suffix("")), str(Path(source_path).parent))
            ).as_posix()
            if not suggested.startswith("."):
                suggested = "./" + suggested
        else:
            suggested = actual
    else:
        suggested = Path(actual).name
    new_raw = suggested + anchor + alias
    if new_raw == raw:
        status = "ok"
    elif new_raw.casefold() == raw.casefold() or target.casefold() == suggested.casefold():
        status = "case_mismatch"
    else:
        status = "ok"
        new_raw = raw
    return {"status": status, "raw": raw, "target": target, "resolved": actual, "replacement": new_raw}


def scan_links(wiki_dir):
    index = build_link_index(wiki_dir)
    findings = []
    total = 0
    for path in markdown_files(wiki_dir):
        content = path.read_text(encoding="utf-8-sig")
        for match in WIKILINK_RE.finditer(content):
            total += 1
            result = resolve_link(index, path, match.group(1))
            if result["status"] != "ok":
                result["file"] = str(path)
                result["start"] = match.start(1)
                result["end"] = match.end(1)
                findings.append(result)
    return total, findings
