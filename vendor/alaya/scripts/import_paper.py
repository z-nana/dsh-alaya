#!/usr/bin/env python3
"""Inspect one source or delegate a full safe import."""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_import import main as batch_main  # noqa: E402
from lib.format_converter import detect_format, extract_metadata, extract_text, pdf_available  # noqa: E402
from lib.runtime import AlayaError, load_effective_config, resolve_kb_root  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Inspect or import one paper/document")
    parser.add_argument("source")
    parser.add_argument("--mode", choices=("info", "full"), default="info")
    parser.add_argument("--category")
    parser.add_argument("--kb-root")
    parser.add_argument("--copy-raw", choices=("yes", "no"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def is_url(value):
    return urlparse(value).scheme in ("http", "https")


def info(args):
    if is_url(args.source):
        print(json.dumps({
            "source_url": args.source,
            "script_import_available": False,
            "recommendation": "Use the host agent to read/download the URL, then choose raw-copy handling.",
        }, ensure_ascii=False, indent=2))
        return 0
    path = Path(args.source).expanduser().resolve()
    if not path.is_file():
        raise AlayaError("Source file does not exist: %s" % path)
    root = resolve_kb_root(args.kb_root)
    config = load_effective_config(root)
    limit = int(config.get("import", {}).get("max_chars_for_extraction", 8000))
    fmt = detect_format(str(path))
    dependency = not (fmt == "pdf") or pdf_available()
    text = extract_text(str(path), max_chars=limit) if dependency and fmt else None
    metadata = extract_metadata(str(path))
    result = {
        "title": metadata.get("title", path.stem),
        "format": fmt or "unsupported",
        "preview_chars": len(text or ""),
        "preview": (text or "")[:500],
        "script_import_available": bool(fmt and dependency),
        "pdf_dependency_available": pdf_available() if fmt == "pdf" else None,
        "next_question": "Do you want batch import, single-document capture, or host-agent semantic card creation? Separately confirm whether to copy this source into raw.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def full(args):
    if is_url(args.source):
        raise AlayaError("URL import requires the host agent; the local script will not claim a raw copy exists")
    if not args.copy_raw:
        raise AlayaError("--copy-raw yes|no is required for every import task")
    forwarded = [args.source, "--copy-raw", args.copy_raw]
    if args.category:
        forwarded.extend(["--category", args.category])
    if args.kb_root:
        forwarded.extend(["--kb-root", args.kb_root])
    if args.dry_run:
        forwarded.append("--dry-run")
    return batch_main(forwarded)


def main(argv=None):
    args = parse_args(argv)
    try:
        return info(args) if args.mode == "info" else full(args)
    except (AlayaError, OSError, ValueError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
