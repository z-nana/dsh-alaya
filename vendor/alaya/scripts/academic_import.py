#!/usr/bin/env python3
"""Compatibility entry point for parallel PDF extraction and serialized import."""

import argparse
import sys

from batch_import import main as batch_main


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Import a PDF collection with parallel extraction")
    parser.add_argument("source")
    parser.add_argument("--category")
    parser.add_argument("--kb-root")
    parser.add_argument("--copy-raw", choices=("yes", "no"), required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--parallel", action="store_true", help="Accepted for compatibility; extraction is parallel")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    forwarded = [args.source, "--copy-raw", args.copy_raw, "--parallel"]
    if args.category:
        forwarded.extend(["--category", args.category])
    if args.kb_root:
        forwarded.extend(["--kb-root", args.kb_root])
    if args.dry_run:
        forwarded.append("--dry-run")
    if args.workers is not None:
        forwarded.extend(["--workers", str(args.workers)])
    return batch_main(forwarded)


if __name__ == "__main__":
    sys.exit(main())
