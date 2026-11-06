#!/usr/bin/env python3
"""Read-only by default wiki-link checker with explicit safe application."""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.link_utils import scan_links  # noqa: E402
from lib.runtime import AlayaError, atomic_write_text, knowledge_paths, resolve_kb_root  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Check Alaya wiki links")
    parser.add_argument("--kb-root", help="Knowledge-base root override")
    parser.add_argument("--apply", action="store_true", help="Apply only unambiguous case corrections")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args(argv)


def apply_case_fixes(findings):
    grouped = defaultdict(list)
    for finding in findings:
        if finding["status"] == "case_mismatch":
            grouped[finding["file"]].append(finding)
    changed = 0
    for filename, items in grouped.items():
        path = Path(filename)
        content = path.read_text(encoding="utf-8-sig")
        for item in sorted(items, key=lambda value: value["start"], reverse=True):
            content = content[:item["start"]] + item["replacement"] + content[item["end"]:]
            changed += 1
        atomic_write_text(path, content)
    return changed


def main(argv=None):
    args = parse_args(argv)
    try:
        root = resolve_kb_root(args.kb_root)
        paths = knowledge_paths(root)
        total, findings = scan_links(paths["wiki"])
        if args.apply:
            fixed = apply_case_fixes(findings)
            total, findings = scan_links(paths["wiki"])
        else:
            fixed = 0
        summary = {
            "links_scanned": total,
            "case_fixes_applied": fixed,
            "case_mismatch": sum(item["status"] == "case_mismatch" for item in findings),
            "broken": sum(item["status"] == "broken" for item in findings),
            "ambiguous": sum(item["status"] == "ambiguous" for item in findings),
            "findings": findings,
        }
        if args.json_output:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print("Links scanned: %d" % total)
            print("Case corrections applied: %d" % fixed)
            print("Remaining case mismatch: %d" % summary["case_mismatch"])
            print("Broken links: %d" % summary["broken"])
            print("Ambiguous links: %d" % summary["ambiguous"])
            for item in findings[:20]:
                print("  [%s] %s -> [[%s]]" % (item["status"], item["file"], item["raw"]))
            if not args.apply and summary["case_mismatch"]:
                print("Re-run with --apply to correct only the unambiguous case mismatches.")
        return 1 if findings else 0
    except (AlayaError, OSError, ValueError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
