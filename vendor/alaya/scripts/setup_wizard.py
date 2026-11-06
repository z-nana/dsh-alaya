#!/usr/bin/env python3
"""Initialize an Alaya knowledge base without coupling it to skill files."""

import argparse
import json
import os
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.runtime import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    AlayaError,
    atomic_write_json,
    atomic_write_text,
    commit_text_bundle,
    knowledge_paths,
    pointer_path,
    read_json,
)
from lib.yaml_utils import safe_persona_key  # noqa: E402


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Initialize or inspect an Alaya knowledge base")
    parser.add_argument("--kb-root", help="Knowledge-base root directory")
    parser.add_argument("--non-interactive", action="store_true")
    role_group = parser.add_mutually_exclusive_group()
    role_group.add_argument("--with-personas", action="store_true")
    role_group.add_argument("--no-personas", action="store_true")
    memory_group = parser.add_mutually_exclusive_group()
    memory_group.add_argument("--with-semantic-memory", action="store_true")
    memory_group.add_argument("--no-semantic-memory", action="store_true")
    parser.add_argument("--with-examples", action="store_true")
    parser.add_argument("--migrate-config", action="store_true", help="Preview config migration")
    parser.add_argument("--apply-migration", action="store_true", help="Apply previewed config migration")
    parser.add_argument("--migrate-shared-memory", action="store_true", help="Preview legacy ambient memory migration")
    parser.add_argument("--apply-shared-memory-migration", action="store_true", help="Apply legacy ambient memory migration")
    return parser.parse_args(argv)


def recommended_root():
    if os.name == "nt":
        drive = Path("D:/")
        if drive.exists() and os.access(str(drive), os.W_OK):
            return drive / "alaya-kb"
    return Path.home() / "alaya-kb"


def choose_root(explicit=None):
    if explicit:
        return Path(explicit).expanduser().resolve()
    recommendation = recommended_root()
    print("Recommended knowledge-base location: %s" % recommendation)
    value = input("Knowledge-base root [%s]: " % recommendation).strip()
    return Path(value or recommendation).expanduser().resolve()


def merge_missing(existing, defaults, prefix=""):
    result = dict(existing)
    additions = []
    for key, value in defaults.items():
        field = "%s.%s" % (prefix, key) if prefix else key
        if key not in result:
            result[key] = value
            additions.append(field)
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key], nested = merge_missing(result[key], value, field)
            additions.extend(nested)
    return result, additions


def migrate_config(paths, apply=False):
    current = read_json(paths["config"])
    defaults = read_json(DEFAULT_CONFIG_PATH)
    if not isinstance(current, dict) or not isinstance(defaults, dict):
        raise AlayaError("Configuration cannot be migrated because JSON is invalid")
    merged, additions = merge_missing(current, defaults)
    if not additions:
        print("Configuration already contains all current fields.")
        return
    print("Configuration migration would add:")
    for field in additions:
        print("  + %s" % field)
    print("Existing and unknown user fields will be preserved.")
    if not apply:
        print("Preview only. Re-run with --apply-migration to write changes.")
        return
    backup_dir = paths["root"] / ".backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / ("config-%s.json" % stamp)
    counter = 1
    while backup.exists():
        backup = backup_dir / ("config-%s-%d.json" % (stamp, counter))
        counter += 1
    shutil.copy2(str(paths["config"]), str(backup))
    merged["version"] = defaults.get("version", merged.get("version"))
    atomic_write_json(paths["config"], merged)
    print("Configuration migrated. Backup: %s" % backup)


def copy_default_personas(paths):
    source = PACKAGE_ROOT / "manas"
    copied = 0
    for item in sorted(source.iterdir()):
        if item.suffix not in (".json", ".md"):
            continue
        destination = paths["manas"] / item.name
        if destination.exists():
            continue
        shutil.copy2(str(item), str(destination))
        copied += 1
    return copied


def copy_examples(paths):
    source = PACKAGE_ROOT / "examples" / "sample_knowledge_base" / "wiki"
    copied = 0
    if any(paths["wiki"].iterdir()):
        raise AlayaError("Examples may only be installed into an empty wiki directory")
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        destination = paths["wiki"] / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(item), str(destination))
            copied += 1
    return copied


def invite_profile(paths):
    print("A local shared profile can help all personas follow your preferences.")
    print("You may view, edit or delete it later. Sensitive details are optional.")
    choice = input("Create now, ask again in 30 days, or never ask? [now/later/never]: ").strip().lower() or "later"
    invitation = paths["memory"] / "shared" / "profile_invitation.json"
    if choice in ("never", "no", "不需要"):
        atomic_write_json(invitation, {"status": "declined", "updated_at": datetime.now().isoformat(timespec="seconds")})
        return
    if choice not in ("now", "现在", "yes", "y"):
        from datetime import timedelta
        atomic_write_json(invitation, {
            "status": "deferred",
            "defer_until": (datetime.now() + timedelta(days=30)).date().isoformat(),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })
        return
    timestamp = datetime.now().isoformat(timespec="seconds")
    raw_values = {
        "display_name": input("How should personas address you? ").strip(),
        "language": input("Preferred language [zh]: ").strip() or "zh",
        "response_style": input("Preferred response style: ").strip(),
        "long_term_interests": [
            value.strip()
            for value in input("Main interests, separated by commas: ").split(",")
            if value.strip()
        ],
        "do_not_record": input("Anything Alaya should not record or share? ").strip(),
    }
    profile = {"version": 2, "fields": {}, "updated_at": timestamp}
    for field, value in raw_values.items():
        if value not in ("", []):
            profile["fields"][field] = {
                "value": value,
                "source": "user_confirmed",
                "evidence": "initial local profile interview",
                "first_seen": timestamp,
                "last_confirmed": timestamp,
                "status": "confirmed",
                "sensitivity": "normal",
                "share_scope": "all_personas",
                "review_after": None,
            }
    shared = paths["memory"] / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    atomic_write_json(shared / "profile.json", profile)
    atomic_write_json(invitation, {"status": "completed", "updated_at": timestamp})


def migrate_shared_memory(paths, apply=False):
    ambient_path = paths["memory"] / "ambient.json"
    ambient = read_json(ambient_path, default={}) or {}
    if not isinstance(ambient, dict):
        raise AlayaError("ambient.json must contain a JSON object")
    style = ambient.get("user_style_notes")
    open_threads = ambient.get("open_threads")
    if not style and not open_threads:
        print("No legacy ambient profile or open-thread fields need migration.")
        return
    actions = []
    if style:
        actions.append("user_style_notes -> shared/profile.json:response_style")
    if open_threads:
        actions.append("open_threads -> shared/state.json:open_threads and shared/history.json")
    print("Shared-memory migration would perform:")
    for action in actions:
        print("  + %s" % action)
    print("ambient.json will keep only immediate environment fields; a backup is created first.")
    if not apply:
        print("Preview only. Re-run with --apply-shared-memory-migration to write changes.")
        return

    timestamp = datetime.now().isoformat(timespec="seconds")
    shared = paths["memory"] / "shared"
    profile = read_json(shared / "profile.json", default={}) or {"version": 2, "fields": {}}
    profile.setdefault("version", 2)
    fields = profile.setdefault("fields", {})
    if style and "response_style" not in fields:
        fields["response_style"] = {
            "value": style,
            "source": "legacy_ambient",
            "evidence": "migrated from ambient.user_style_notes",
            "first_seen": timestamp,
            "last_confirmed": timestamp,
            "status": "legacy_preserved",
            "sensitivity": "normal",
            "share_scope": "all_personas",
            "review_after": None,
        }
    profile["updated_at"] = timestamp

    state = read_json(shared / "state.json", default={}) or {}
    if open_threads:
        existing = list(state.get("open_threads", []))
        seen = {json.dumps(item, ensure_ascii=False, sort_keys=True) for item in existing}
        for item in open_threads if isinstance(open_threads, list) else [open_threads]:
            marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if marker not in seen:
                existing.append(item)
                seen.add(marker)
        state["open_threads"] = existing[-100:]
        state["updated_at"] = timestamp

    history = read_json(shared / "history.json", default={}) or {}
    event_id = "migration-legacy-ambient-v2"
    recent_ids = list(history.get("recent_event_ids", []))
    if open_threads and event_id not in recent_ids:
        hot = list(history.get("hot", []))
        hot.append({
            "event_id": event_id,
            "date": date.today().isoformat(),
            "type": "memory_migration",
            "summary": "Legacy ambient open threads were moved into bounded shared state.",
        })
        history["hot"] = hot[-20:]
        history.setdefault("cold", [])
        history["recent_event_ids"] = (recent_ids + [event_id])[-200:]

    cleaned = dict(ambient)
    cleaned.pop("user_style_notes", None)
    cleaned.pop("open_threads", None)
    backup_dir = paths["root"] / ".backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / ("ambient-%s.json" % stamp)
    counter = 1
    while backup.exists():
        backup = backup_dir / ("ambient-%s-%d.json" % (stamp, counter))
        counter += 1
    shutil.copy2(str(ambient_path), str(backup))
    writes = [
        (shared / "profile.json", json.dumps(profile, ensure_ascii=False, indent=2) + "\n"),
        (shared / "state.json", json.dumps(state, ensure_ascii=False, indent=2) + "\n"),
        (shared / "history.json", json.dumps(history, ensure_ascii=False, indent=2) + "\n"),
        (ambient_path, json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n"),
    ]
    commit_text_bundle(paths["alaya"], event_id, writes)
    from perfume_memory import render_shared_index
    atomic_write_text(shared / "INDEX.md", render_shared_index(paths["memory"]))
    print("Shared memory migrated. Backup: %s" % backup)


def initialize(args):
    if args.non_interactive and not args.kb_root:
        raise AlayaError("--kb-root is required with --non-interactive")
    root = Path(args.kb_root).expanduser().resolve() if args.non_interactive else choose_root(args.kb_root)
    paths = knowledge_paths(root)

    existing = paths["config"].exists()
    for key in ("root", "alaya", "wiki", "raw", "memory", "manas"):
        paths[key].mkdir(parents=True, exist_ok=True)
    (paths["memory"] / "shared" / "topics").mkdir(parents=True, exist_ok=True)

    if existing:
        print("Existing Alaya knowledge base detected. User data will not be reseeded.")
        if args.migrate_config or args.apply_migration:
            migrate_config(paths, apply=args.apply_migration)
        if args.migrate_shared_memory or args.apply_shared_memory_migration:
            migrate_shared_memory(paths, apply=args.apply_shared_memory_migration)
    else:
        defaults = read_json(DEFAULT_CONFIG_PATH)
        if not isinstance(defaults, dict):
            raise AlayaError("Default configuration is invalid")
        if args.no_semantic_memory:
            semantic_memory = False
        elif args.with_semantic_memory or args.non_interactive:
            semantic_memory = True
        else:
            semantic_memory = input(
                "Enable short local semantic memory after each completed persona answer? [Y/n]: "
            ).strip().lower() not in ("n", "no", "否")
        defaults.setdefault("memory", {})["semantic_memory_enabled"] = semantic_memory
        atomic_write_json(paths["config"], defaults)

        if args.no_personas:
            install_personas = False
        elif args.with_personas:
            install_personas = True
        elif args.non_interactive:
            install_personas = False
        else:
            install_personas = input("Install the built-in personas? [Y/n]: ").strip().lower() not in ("n", "no", "否")
        if install_personas:
            print("Installed persona files: %d" % copy_default_personas(paths))

        install_examples = args.with_examples
        if not args.non_interactive and not args.with_examples:
            install_examples = input("Install sample knowledge cards? [y/N]: ").strip().lower() in ("y", "yes", "是")
        if install_examples:
            print("Installed example files: %d" % copy_examples(paths))

        if not args.non_interactive:
            invite_profile(paths)

    atomic_write_text(pointer_path(), str(root) + "\n")
    print("Alaya knowledge base ready: %s" % root)
    print("Directories: alaya, wiki, raw")
    if existing:
        print("Existing personas, memories, cards and source files were not modified.")


def main(argv=None):
    try:
        initialize(parse_args(argv))
        return 0
    except (AlayaError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
