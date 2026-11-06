#!/usr/bin/env python3
"""Validate explicit trigger contracts and optionally build a single-file bundle."""

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "SKILL.md"
SUBSKILLS = [
    ROOT / "skills" / name / "SKILL.md"
    for name in ("alaya-retrieval", "alaya-memory", "alaya-persona", "alaya-import", "alaya-maintenance")
]
OUTPUT = ROOT / "SKILL_FULL.md"


class ContractError(RuntimeError):
    pass


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Validate Alaya skill trigger contracts")
    parser.add_argument("--check-only", action="store_true", help="Validate without creating SKILL_FULL.md")
    return parser.parse_args(argv)


def body_without_frontmatter(content):
    match = re.match(r"\A---\r?\n.*?\r?\n---\r?\n", content, re.DOTALL)
    return content[match.end():] if match else content


def trigger_block(content, label):
    marker = "<!-- %s -->" % label
    if content.count(marker) != 2:
        raise ContractError("%s must appear exactly twice" % marker)
    body = content.split(marker, 2)[1]
    values = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.fullmatch(r"-\s+(.+)", stripped)
        if not match:
            raise ContractError("Trigger block %s contains a non-list line" % label)
        values.append(match.group(1).strip())
    if not values:
        raise ContractError("Trigger block %s is empty" % label)
    return values


def validate():
    main = MAIN.read_text(encoding="utf-8-sig")
    import_skill = (ROOT / "skills" / "alaya-import" / "SKILL.md").read_text(encoding="utf-8-sig")
    main_values = trigger_block(main, "ALAYA_IMPORT_TRIGGERS")
    import_values = trigger_block(import_skill, "ALAYA_IMPORT_TRIGGERS")
    missing = sorted(set(main_values) ^ set(import_values), key=str.casefold)
    return missing


def build():
    sections = [body_without_frontmatter(MAIN.read_text(encoding="utf-8-sig")).strip()]
    for path in SUBSKILLS:
        sections.append("# Bundled subskill: %s\n\n%s" % (path.parent.name, body_without_frontmatter(path.read_text(encoding="utf-8-sig")).strip()))
    content = "---\nname: Alaya\ndescription: Single-file bundle of Alaya and its five subskills.\n---\n\n"
    content += "\n\n---\n\n".join(sections) + "\n"
    from lib.runtime import atomic_write_text
    atomic_write_text(OUTPUT, content)
    print("Single-file bundle written: %s" % OUTPUT)


def main(argv=None):
    args = parse_args(argv)
    try:
        missing = validate()
        if missing:
            print("Trigger lists differ: %s" % ", ".join(missing), file=sys.stderr)
            return 1
        print("Explicit import trigger lists are consistent.")
        if not args.check_only:
            build()
        return 0
    except (ContractError, OSError, ValueError) as exc:
        print("[ERROR] Checker could not parse the explicit contract: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
