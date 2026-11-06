#!/usr/bin/env python3
"""Plan or apply safe MD/TXT/PDF source-preserving imports."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_index import build as build_index  # noqa: E402
from lib.import_engine import apply_import_plan, plan_import, summarize_plan  # noqa: E402
from lib.runtime import (  # noqa: E402
    AlayaError,
    knowledge_paths,
    load_effective_config,
    resolve_kb_root,
)
from perfume import run_xunxi  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Import local files into Alaya")
    parser.add_argument("source")
    parser.add_argument("--category")
    parser.add_argument("--kb-root", help="Knowledge-base root override")
    parser.add_argument("--copy-raw", choices=("yes", "no"), required=True, help="Copy source files into raw for this task")
    parser.add_argument("--dry-run", action="store_true", help="Show a zero-write import plan")
    parser.add_argument("--parallel", action="store_true", help="Parallelize read/extract only")
    parser.add_argument("--workers", type=int)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        root = resolve_kb_root(args.kb_root)
        paths = knowledge_paths(root)
        config = load_effective_config(root)
        category = args.category or config.get("import", {}).get("default_category", "uncategorized")
        workers = args.workers or int(config.get("import", {}).get("parallel_workers", 4))
        if workers < 1:
            raise AlayaError("--workers must be at least 1")
        plan = plan_import(
            paths,
            args.source,
            category,
            copy_raw=args.copy_raw == "yes",
            parallel=args.parallel,
            workers=workers,
            max_chars=int(config.get("import", {}).get("max_chars_for_extraction", 8000)),
        )
        print(summarize_plan(plan))
        if args.dry_run:
            print("Dry run complete: no files, directories, reports, checkpoints or locks were created.")
            return 0

        blocked = [item for item in plan["items"] if item["action"] in ("llm_required", "pdf_dependency_required")]
        if blocked:
            if any(item["action"] == "pdf_dependency_required" for item in blocked):
                print("PDF script import requires PyMuPDF. Install it with approval, use LLM import, or cancel.")
            if any(item["action"] == "llm_required" for item in blocked):
                print("Some formats require the host agent's LLM import path.")
            return 1

        result = apply_import_plan(paths, plan)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["created"]:
            try:
                build_index(paths, config, category=result["category"])
            except Exception as exc:
                print("[ERROR] Cards were committed but index publication is pending: %s" % exc, file=sys.stderr)
                return 1
            print("Description choice: update the affected category now, or accumulate until its threshold/3-day deadline.")
            try:
                run_xunxi(paths, config)
            except Exception as exc:
                print("[WARN] Piggyback xunxi is pending: %s" % exc, file=sys.stderr)
        return 0
    except (AlayaError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
