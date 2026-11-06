#!/usr/bin/env python3
"""Safe persona discovery, cloning and recoverable removal."""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.runtime import (  # noqa: E402
    AlayaError,
    atomic_write_json,
    atomic_write_text,
    commit_text_bundle,
    is_within,
    knowledge_paths,
    load_effective_config,
    read_json,
    resolve_kb_root,
)
from lib.yaml_utils import persona_key, safe_persona_key  # noqa: E402


def parser():
    root = argparse.ArgumentParser(description="Manage Alaya personas")
    root.add_argument("--kb-root", help="Knowledge-base root override")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List personas")

    clone = commands.add_parser("clone", help="Clone a persona")
    clone.add_argument("source")
    clone.add_argument("target")

    delete = commands.add_parser("delete", help="Recoverably remove a persona")
    delete.add_argument("name")
    delete.add_argument("--new-default", help="Replacement if deleting the default persona")
    delete.add_argument("--yes", action="store_true", help="Confirm the displayed move")

    restore = commands.add_parser("restore", help="Restore a persona trash entry")
    restore.add_argument("entry", help="Trash entry directory name")

    purge = commands.add_parser("purge", help="Permanently delete one persona trash entry")
    purge.add_argument("entry")
    purge.add_argument("--confirm", required=True, help="Persona key shown in the entry")
    return root


def find_persona(manas_dir, name):
    key = persona_key(str(manas_dir), name)
    path = Path(manas_dir) / (key + ".json")
    if not path.is_file() or path.parent.resolve() != Path(manas_dir).resolve():
        return None, None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None, None, None
    return key, path, data


def effective_language(data, config):
    persona = config.get("persona", {})
    if persona.get("language_mode", "global") == "global":
        return config.get("language", "zh")
    return data.get("language") or config.get("language", "zh")


def cmd_list(paths, config):
    found = 0
    for path in sorted(paths["manas"].glob("*.json"), key=lambda item: item.name.casefold()):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            print("[WARN] Invalid persona JSON: %s" % path.name)
            continue
        found += 1
        profile = paths["manas"] / (path.stem + "_profile.md")
        print("%s\t%s\t%s\tprofile=%s" % (
            path.stem,
            data.get("persona", path.stem),
            effective_language(data, config),
            "yes" if profile.exists() else "no",
        ))
    if not found:
        print("No personas found.")


def cmd_clone(paths, source_name, target_name):
    _source_key, source_path, data = find_persona(paths["manas"], source_name)
    if source_path is None:
        raise AlayaError("Source persona was not found: %s" % source_name)
    target_key = safe_persona_key(target_name)
    target_path = paths["manas"] / (target_key + ".json")
    target_profile = paths["manas"] / (target_key + "_profile.md")
    if target_path.parent.resolve() != paths["manas"].resolve():
        raise AlayaError("Target persona path escaped the manas directory")
    if target_path.exists() or target_profile.exists():
        raise AlayaError("Target persona already exists: %s" % target_key)

    cloned = json.loads(json.dumps(data, ensure_ascii=False))
    cloned["persona"] = target_name
    cloned["affinity"] = {}
    cloned["interaction_history"] = []
    writes = [(target_path, json.dumps(cloned, ensure_ascii=False, indent=2) + "\n")]
    source_profile = source_path.with_name(source_path.stem + "_profile.md")
    if source_profile.is_file():
        writes.append((target_profile, source_profile.read_text(encoding="utf-8-sig")))
    commit_text_bundle(
        paths["alaya"],
        "clone-persona-%s" % target_key,
        writes,
    )
    print("Cloned persona: %s -> %s" % (source_path.stem, target_key))


def mixed_reference_files(paths, key):
    matches = []
    candidates = list(paths["memory"].rglob("*.json")) + [
        paths["alaya"] / "bi_notes.json",
        paths["alaya"] / "bi_state.json",
    ]
    private_name = key + "_history.json"
    for path in candidates:
        if not path.is_file() or path.name == private_name:
            continue
        try:
            if key.casefold() in path.read_text(encoding="utf-8-sig").casefold():
                matches.append(path)
        except (OSError, UnicodeError):
            continue
    return matches


def planned_default_update(paths, config, key, replacement):
    current = config.get("persona", {}).get("default_persona", "feynman")
    if current.casefold() != key.casefold():
        return None
    if not replacement:
        raise AlayaError("Deleting the default persona requires --new-default")
    replacement_key, _path, _data = find_persona(paths["manas"], replacement)
    if not replacement_key or replacement_key.casefold() == key.casefold():
        raise AlayaError("Replacement default persona is invalid")
    raw = read_json(paths["config"], default={})
    updated = json.loads(json.dumps(raw, ensure_ascii=False))
    updated.setdefault("persona", {})["default_persona"] = replacement_key
    return raw, updated


def move_bundle(paths, key, files):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = paths["alaya"] / ".trash" / "personas" / (stamp + "-" + key)
    destination.mkdir(parents=True, exist_ok=False)
    journal = paths["alaya"] / ".commit_journal.json"
    state = {
        "operation_id": "remove-persona-%s-%s" % (key, stamp),
        "completed": [],
        "remaining": [str(path) for path in files],
        "destination": str(destination),
    }
    atomic_write_json(journal, state)
    moved = []
    try:
        for source in files:
            target = destination / source.name
            os.replace(str(source), str(target))
            moved.append((source, target))
            state["completed"].append(str(source))
            state["remaining"].remove(str(source))
            atomic_write_json(journal, state)
    except Exception:
        for source, target in reversed(moved):
            if target.exists() and not source.exists():
                os.replace(str(target), str(source))
        try:
            destination.rmdir()
        except OSError:
            pass
        raise
    finally:
        if not state["remaining"] or not destination.exists():
            try:
                journal.unlink()
            except FileNotFoundError:
                pass
    return destination


def recover_pending_persona_move(paths):
    journal = paths["alaya"] / ".commit_journal.json"
    state = read_json(journal, default={}) or {}
    operation = str(state.get("operation_id", ""))
    if not operation.startswith("remove-persona-"):
        return None
    destination = Path(state.get("destination", "")).resolve()
    trash_root = paths["alaya"] / ".trash" / "personas"
    if not destination.is_dir() or not is_within(destination, trash_root):
        raise AlayaError("Persona removal journal has an invalid destination")
    for source_value in list(state.get("remaining", [])):
        source = Path(source_value).resolve()
        if not is_within(source, paths["alaya"]):
            raise AlayaError("Persona removal journal contains an unsafe source")
        target = destination / source.name
        if source.exists():
            os.replace(str(source), str(target))
        elif not target.exists():
            raise AlayaError("Persona removal recovery cannot find source or destination: %s" % source)
        state.setdefault("completed", []).append(str(source))
        state["remaining"].remove(source_value)
        atomic_write_json(journal, state)
    journal.unlink()
    print("Completed pending persona removal: %s" % destination.name)
    return destination.name


def cmd_delete(paths, config, name, replacement, confirmed):
    key, persona_path, data = find_persona(paths["manas"], name)
    if persona_path is None:
        raise AlayaError("Persona was not found: %s" % name)
    profile = paths["manas"] / (key + "_profile.md")
    history = paths["memory"] / (key + "_history.json")
    files = [path for path in (persona_path, profile, history) if path.exists()]
    references = mixed_reference_files(paths, key)

    print("Persona to remove: %s (%s)" % (data.get("persona", key), key))
    for path in files:
        print("  MOVE %s" % path)
    for path in references:
        print("  KEEP mixed/shared reference: %s" % path)
    if not confirmed:
        raise AlayaError("Preview only. Re-run with --yes to perform the recoverable move")

    config_update = planned_default_update(paths, config, key, replacement)
    if config_update is not None:
        atomic_write_json(paths["config"], config_update[1])
    try:
        destination = move_bundle(paths, key, files)
    except Exception:
        if config_update is not None:
            atomic_write_json(paths["config"], config_update[0])
        raise
    print("Persona moved to recoverable trash: %s" % destination)


def cmd_restore(paths, entry):
    trash_root = paths["alaya"] / ".trash" / "personas"
    source = (trash_root / entry).resolve()
    if not source.is_dir() or not is_within(source, trash_root):
        raise AlayaError("Persona trash entry was not found")
    targets = []
    for item in source.iterdir():
        base = paths["memory"] if item.name.endswith("_history.json") else paths["manas"]
        target = base / item.name
        if target.exists():
            raise AlayaError("Restore target already exists: %s" % target)
        targets.append((item, target))
    restored = []
    try:
        for item, target in targets:
            os.replace(str(item), str(target))
            restored.append((item, target))
    except Exception:
        for item, target in reversed(restored):
            if target.exists() and not item.exists():
                os.replace(str(target), str(item))
        raise
    source.rmdir()
    print("Restored persona entry: %s" % entry)


def cmd_purge(paths, entry, confirmation):
    trash_root = paths["alaya"] / ".trash" / "personas"
    target = (trash_root / entry).resolve()
    if not target.is_dir() or not is_within(target, trash_root):
        raise AlayaError("Persona trash entry was not found")
    key = entry.split("-", 2)[-1]
    if confirmation != key:
        raise AlayaError("--confirm must exactly match persona key: %s" % key)
    shutil.rmtree(str(target))
    print("Permanently deleted persona trash entry: %s" % entry)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        root = resolve_kb_root(args.kb_root)
        paths = knowledge_paths(root)
        config = load_effective_config(root)
        recovered = recover_pending_persona_move(paths)
        if recovered and args.command == "delete":
            return 0
        if args.command == "list":
            cmd_list(paths, config)
        elif args.command == "clone":
            cmd_clone(paths, args.source, args.target)
        elif args.command == "delete":
            cmd_delete(paths, config, args.name, args.new_default, args.yes)
        elif args.command == "restore":
            cmd_restore(paths, args.entry)
        elif args.command == "purge":
            cmd_purge(paths, args.entry, args.confirm)
        return 0
    except (AlayaError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
