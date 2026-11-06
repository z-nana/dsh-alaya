#!/usr/bin/env python3
"""Read-only health report for the current Alaya data contract."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.link_utils import scan_links  # noqa: E402
from lib.index_utils import block_status  # noqa: E402
from lib.runtime import (  # noqa: E402
    AlayaError,
    ConfigError,
    knowledge_paths,
    load_effective_config,
    read_json,
    resolve_kb_root,
)
from lib.yaml_utils import (  # noqa: E402
    category_file_for,
    description_issue,
    get_description,
    get_field,
    get_field_float,
    is_knowledge_card,
    read_frontmatter,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run a read-only Alaya health check")
    parser.add_argument("--kb-root", help="Knowledge-base root override")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args(argv)


def add(findings, severity, code, message, path=None):
    item = {"severity": severity, "code": code, "message": message}
    if path:
        item["path"] = str(path)
    findings.append(item)


def disk_categories(wiki):
    return [
        path.name for path in wiki.iterdir()
        if path.is_dir() and not path.name.startswith(".") and not path.name.startswith("~$")
    ] if wiki.is_dir() else []


def index_categories(index_content):
    return set(re.findall(r"^- \[\[([^/]+)/", index_content, re.MULTILINE))


def check_structure(paths, findings, stats):
    for name in ("alaya", "wiki", "raw", "memory", "manas"):
        if not paths[name].is_dir():
            add(findings, "error", "missing_directory", "Required directory is missing", paths[name])

    categories = sorted(disk_categories(paths["wiki"]), key=str.casefold)
    stats["categories"] = len(categories)
    index_path = paths["wiki"] / "index.md"
    if not index_path.is_file():
        add(findings, "error", "missing_total_index", "wiki/index.md is missing", index_path)
        indexed = set()
    else:
        content = index_path.read_text(encoding="utf-8-sig", errors="replace")
        status = block_status(content, "AUTO (base)")
        if status in ("missing", "unpaired"):
            add(findings, "error", "invalid_base_markers", "Total index needs one paired AUTO (base) block", index_path)
        elif status == "legacy":
            add(findings, "info", "legacy_index_markers", "Total index uses compatible legacy AUTO markers", index_path)
        indexed = index_categories(content)
    if set(categories) != indexed:
        add(
            findings,
            "error",
            "category_set_mismatch",
            "Total-index categories differ from disk categories: disk=%d index=%d" % (len(categories), len(indexed)),
            index_path,
        )

    card_count = 0
    missing_description = 0
    description_encoding = 0
    description_content = 0
    source_broken = 0
    for category in categories:
        directory = paths["wiki"] / category
        category_page = directory / category_file_for(category)
        if not category_page.is_file():
            add(findings, "error", "missing_category_index", "Category index is missing", category_page)
        else:
            content = category_page.read_text(encoding="utf-8-sig", errors="replace")
            status = block_status(content, "AUTO (base)")
            if status in ("missing", "unpaired"):
                add(findings, "error", "invalid_base_markers", "Category index needs one paired AUTO (base) block", category_page)
            elif status == "legacy":
                add(findings, "info", "legacy_index_markers", "Category index uses compatible legacy AUTO markers", category_page)
            if block_status(content, "AUTO (refined)") == "unpaired" or block_status(content, "MANUAL") == "unpaired":
                add(findings, "error", "unpaired_optional_markers", "Optional refined or manual markers are unpaired", category_page)
        for card in directory.glob("*.md"):
            if not is_knowledge_card(card):
                continue
            card_count += 1
            result = read_frontmatter(card)
            if not result:
                add(findings, "error", "invalid_frontmatter", "Card has no strict YAML frontmatter", card)
                continue
            _content, yaml_str, _dash = result
            strength = get_field_float(yaml_str, "strength")
            if strength is None or not 0.0 <= strength <= 1.0:
                add(findings, "warning", "invalid_strength", "Card strength is missing or outside 0..1", card)
            if not get_description(yaml_str):
                missing_description += 1
            issue = description_issue(yaml_str)
            if issue == "encoding":
                description_encoding += 1
            elif issue == "content":
                description_content += 1
            source_file = get_field(yaml_str, "source_file")
            if source_file:
                if re.match(r"^https?://", source_file, re.IGNORECASE):
                    add(findings, "info", "legacy_source_url_field", "URL is stored in legacy source_file; keep readable and migrate when edited", card)
                    continue
                source_path = Path(source_file)
                target = source_path if source_path.is_absolute() else paths["root"] / source_path
                if not target.exists():
                    source_broken += 1
    stats["cards"] = card_count
    stats["cards_missing_description"] = missing_description
    stats["description_encoding_issues"] = description_encoding
    stats["description_content_issues"] = description_content
    stats["broken_source_files"] = source_broken
    if missing_description:
        add(findings, "warning", "missing_descriptions", "%d cards lack descriptions" % missing_description)
    if description_encoding:
        add(findings, "warning", "description_encoding", "%d descriptions need scalar quoting only; content was not rewritten" % description_encoding)
    if description_content:
        add(findings, "warning", "description_content", "%d descriptions contain placeholder or damaged text and need content review" % description_content)
    if source_broken:
        add(findings, "warning", "broken_source_files", "%d source_file paths do not exist" % source_broken)


def check_personas(paths, config, findings, stats):
    personas = []
    for path in paths["manas"].glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(value, dict):
                raise ValueError("not an object")
        except (OSError, ValueError) as exc:
            add(findings, "error", "invalid_persona", "Persona JSON is invalid: %s" % exc, path)
            continue
        personas.append(path.stem)
        profile = path.with_name(path.stem + "_profile.md")
        if not profile.is_file():
            add(findings, "warning", "missing_profile", "Persona profile is missing", profile)
    stats["personas"] = len(personas)
    default = config.get("persona", {}).get("default_persona", "feynman")
    if not personas:
        add(findings, "warning", "no_personas", "No personas are installed; retrieval and maintenance remain available")
    elif default not in personas:
        add(findings, "error", "missing_default_persona", "Configured default persona does not exist: %s" % default)


def check_memory(paths, findings, stats):
    valid = 0
    placeholders = 0
    legacy_group = 0
    phrases = ("维护完成", "自动保存", "会话结束", "好感已更新", "level 1")
    for path in paths["memory"].glob("*_history.json"):
        if "," in path.stem:
            legacy_group += 1
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            add(findings, "error", "invalid_memory", "Memory JSON is invalid: %s" % exc, path)
            continue
        valid += 1
        text = json.dumps(value, ensure_ascii=False).casefold()
        if any(phrase.casefold() in text for phrase in phrases):
            placeholders += 1
    stats["private_memory_files"] = valid
    stats["legacy_group_history_files"] = legacy_group
    stats["placeholder_memory_files"] = placeholders
    if legacy_group:
        add(findings, "warning", "legacy_group_history", "%d legacy combined-persona history files were found; no automatic migration" % legacy_group)
    if placeholders:
        add(findings, "warning", "mechanical_memory_placeholders", "%d history files contain possible mechanical placeholders" % placeholders)
    root_bi = paths["alaya"] / "bi_notes.json"
    misplaced_bi = paths["memory"] / "bi_notes.json"
    if misplaced_bi.exists():
        add(findings, "warning", "misplaced_bi_notes", "BI observations belong at alaya/bi_notes.json", misplaced_bi)
    if root_bi.exists() and read_json(root_bi, default=None) is None:
        add(findings, "error", "invalid_bi_notes", "BI notes JSON is invalid", root_bi)


def check_config(paths, findings, stats):
    raw = read_json(paths["config"], default=None)
    if not isinstance(raw, dict):
        add(findings, "error", "invalid_config", "config.json is missing or invalid", paths["config"])
        return None
    try:
        effective = load_effective_config(paths["root"])
    except ConfigError as exc:
        add(findings, "error", "invalid_config_value", str(exc), paths["config"])
        return None
    stats["config_version"] = raw.get("version", "unknown")
    aliases = []
    memory = raw.get("memory", {}) if isinstance(raw.get("memory", {}), dict) else {}
    if "hot_limit" in memory and "hot_zone_size" not in memory:
        aliases.append("memory.hot_limit -> memory.hot_zone_size")
    if "cold_limit" in memory and "cold_zone_size" not in memory:
        aliases.append("memory.cold_limit -> memory.cold_zone_size")
    stats["legacy_config_aliases"] = aliases
    stats["effective_cold_after_days"] = effective["knowledge"]["cold_after_days_default"]
    stats["effective_default_persona"] = effective["persona"]["default_persona"]
    return effective


def main(argv=None):
    args = parse_args(argv)
    try:
        root = resolve_kb_root(args.kb_root)
        paths = knowledge_paths(root)
        findings = []
        stats = {"kb_root": str(root)}
        config = check_config(paths, findings, stats)
        check_structure(paths, findings, stats)
        if config:
            check_personas(paths, config, findings, stats)
        check_memory(paths, findings, stats)
        link_total, link_findings = scan_links(paths["wiki"])
        stats["links"] = link_total
        stats["broken_links"] = sum(item["status"] == "broken" for item in link_findings)
        stats["ambiguous_links"] = sum(item["status"] == "ambiguous" for item in link_findings)
        if link_findings:
            add(findings, "warning", "link_findings", "%d links need review" % len(link_findings))
        actionable = any(item["severity"] in ("warning", "error") for item in findings)
        report = {"status": "findings" if actionable else ("info" if findings else "pass"), "stats": stats, "findings": findings}
        if args.json_output:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("Alaya health check (read-only)")
            for key, value in stats.items():
                print("  %s: %s" % (key, value))
            for item in findings:
                suffix = " (%s)" % item["path"] if item.get("path") else ""
                print("[%s] %s: %s%s" % (item["severity"].upper(), item["code"], item["message"], suffix))
            if not findings:
                print("[OK] No findings.")
        return 1 if actionable else 0
    except (AlayaError, OSError, ValueError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
