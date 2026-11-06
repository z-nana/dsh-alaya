#!/usr/bin/env python3
"""Read-only post-import card quality review."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.runtime import AlayaError, atomic_write_json, knowledge_paths, resolve_kb_root  # noqa: E402
from lib.yaml_utils import description_issue, get_description, get_field, is_knowledge_card, read_frontmatter  # noqa: E402


REQUIRED = ("seed_type", "created_by", "strength", "last_activated", "activation_count")
PLACEHOLDERS = ("[待填写]", "[...]", "TODO", "TBD", "待补充", "待完善")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Review imported Alaya cards without modifying them")
    parser.add_argument("--category", required=True)
    parser.add_argument("--kb-root")
    parser.add_argument("--report-file", help="Optional explicit JSON report destination")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def review_card(path, root):
    result = read_frontmatter(path)
    if not result:
        return ["invalid or missing strict frontmatter"]
    content, yaml_str, dash = result
    body = content[dash + 3:].lstrip("\r\n")
    issues = []
    missing = [field for field in REQUIRED if get_field(yaml_str, field) is None]
    if missing:
        issues.append("missing fields: %s" % ", ".join(missing))
    if not get_field(yaml_str, "title"):
        issues.append("missing title")
    if not get_description(yaml_str):
        issues.append("missing description")
    description_problem = description_issue(yaml_str)
    if description_problem == "encoding":
        issues.append("description needs safe YAML scalar quoting")
    elif description_problem == "content":
        issues.append("description content needs review")
    for placeholder in PLACEHOLDERS:
        if placeholder in body:
            issues.append("placeholder text: %s" % placeholder)
    if "\x00" in content or "�" in content:
        issues.append("encoding replacement or null character")
    source_file = get_field(yaml_str, "source_file")
    if source_file:
        source = Path(source_file)
        target = source if source.is_absolute() else Path(root) / source
        if not target.exists():
            issues.append("source_file does not exist: %s" % source_file)
    source_url = get_field(yaml_str, "source_url")
    if source_url and not re.match(r"^https?://", source_url):
        issues.append("source_url is not an HTTP(S) URL")
    return issues


def review_category(paths, category, verbose=False):
    directory = paths["wiki"] / category
    if not directory.is_dir():
        raise AlayaError("Category directory does not exist: %s" % directory)
    cards = [path for path in sorted(directory.glob("*.md")) if is_knowledge_card(path)]
    results = []
    for path in cards:
        issues = review_card(path, paths["root"])
        results.append({"path": str(path), "status": "issues" if issues else "ok", "issues": issues})
        if verbose and issues:
            print("[WARN] %s: %s" % (path.name, "; ".join(issues)))
    issue_count = sum(item["status"] == "issues" for item in results)
    return {
        "category": category,
        "status": "empty" if not cards else "reviewed",
        "total": len(cards),
        "issues": issue_count,
        "pass_rate": None if not cards else round((len(cards) - issue_count) / len(cards) * 100, 1),
        "cards": results,
    }


def main(argv=None):
    args = parse_args(argv)
    try:
        root = resolve_kb_root(args.kb_root)
        paths = knowledge_paths(root)
        result = review_category(paths, args.category, args.verbose)
        if result["status"] == "empty":
            print("No knowledge cards; pass rate is not calculated.")
        else:
            print("Cards: %d" % result["total"])
            print("Cards with issues: %d" % result["issues"])
            print("Pass rate: %.1f%%" % result["pass_rate"])
        if args.report_file:
            report = Path(args.report_file).expanduser().resolve()
            atomic_write_json(report, result)
            print("Report written: %s" % report)
        return 1 if result["issues"] else 0
    except (AlayaError, OSError, ValueError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
