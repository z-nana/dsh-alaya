#!/usr/bin/env python3
"""Verify the required multi-file Alaya installation contract."""

import argparse
import ast
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Verify an Alaya skill installation")
    parser.add_argument("--root", default=str(ROOT), help="Skill package root")
    parser.add_argument("--single-file", action="store_true", help="Require the optional SKILL_FULL.md artifact")
    return parser.parse_args(argv)


def skill_header(path):
    text = path.read_text(encoding="utf-8-sig")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not match:
        return None
    header = match.group(1)
    keys = re.findall(r"^([A-Za-z_][A-Za-z0-9_-]*):", header, re.MULTILINE)
    name = re.search(r"^name:\s*(.+)$", header, re.MULTILINE)
    description = re.search(r"^description:\s*(.+)$", header, re.MULTILINE)
    return bool(name and description and set(keys) == {"name", "description"})


def verify(root, single_file=False):
    required = [
        "SKILL.md",
        "README.md",
        "SKILL_GUIDE.md",
        "SKILL_REF.md",
        "config/default_config.json",
        "scripts/setup_wizard.py",
        "scripts/batch_import.py",
        "scripts/academic_import.py",
        "scripts/import_paper.py",
        "scripts/post_process.py",
        "scripts/import_quality_review.py",
        "scripts/build_index.py",
        "scripts/perfume.py",
        "scripts/perfume_memory.py",
        "scripts/perfume_knowledge.py",
        "scripts/perfume_persona.py",
        "scripts/persona_manager.py",
        "scripts/memory_manager.py",
        "scripts/bi_observer.py",
        "scripts/fix_links.py",
        "scripts/health_check.py",
        "scripts/build_skill_full.py",
        "scripts/lib/runtime.py",
        "scripts/lib/yaml_utils.py",
        "scripts/lib/index_utils.py",
        "scripts/lib/link_utils.py",
        "scripts/lib/import_engine.py",
        "scripts/lib/format_converter.py",
        "templates/persona_template.json",
        "templates/persona_profile_template.md",
        "requirements.txt",
    ]
    subskills = [
        "skills/%s/SKILL.md" % name
        for name in ("alaya-retrieval", "alaya-memory", "alaya-persona", "alaya-import", "alaya-maintenance")
    ]
    failures = []
    checks = []
    for relative in required + subskills:
        path = root / relative
        ok = path.is_file()
        checks.append((ok, relative))
        if not ok:
            failures.append("Missing required file: %s" % relative)
    for relative in ["SKILL.md"] + subskills:
        path = root / relative
        if path.is_file() and not skill_header(path):
            failures.append("Invalid skill frontmatter: %s" % relative)
    for relative in [item for item in required if item.endswith(".py")]:
        path = root / relative
        if not path.is_file():
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            failures.append("Invalid Python syntax: %s (%s)" % (relative, exc))
    try:
        default = json.loads((root / "config" / "default_config.json").read_text(encoding="utf-8-sig"))
        if not isinstance(default, dict):
            failures.append("Default configuration must contain an object")
    except (OSError, ValueError) as exc:
        failures.append("Default configuration is invalid: %s" % exc)

    optional = root / "SKILL_FULL.md"
    if single_file and not optional.is_file():
        failures.append("Single-file mode requires SKILL_FULL.md")
    return checks, failures, optional.is_file()


def main(argv=None):
    args = parse_args(argv)
    try:
        root = Path(args.root).expanduser().resolve()
        checks, failures, optional_present = verify(root, args.single_file)
        passed = sum(ok for ok, _name in checks)
        print("Required multi-file checks: %d/%d passed" % (passed, len(checks)))
        print("Optional SKILL_FULL.md: %s" % ("present" if optional_present else "not present (allowed)"))
        for failure in failures:
            print("[ERROR] %s" % failure)
        if failures:
            return 1
        print("[OK] Alaya installation is complete for %s mode." % ("single-file" if args.single_file else "multi-file"))
        return 0
    except (OSError, ValueError) as exc:
        print("[ERROR] Verification could not run: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
