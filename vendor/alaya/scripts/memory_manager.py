#!/usr/bin/env python3
"""Explicit user-facing management of confirmed shared profile memory."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.runtime import (  # noqa: E402
    AlayaError,
    atomic_write_json,
    contains_secret_like,
    knowledge_paths,
    load_effective_config,
    read_json,
    resolve_kb_root,
)


SENSITIVE_FIELDS = {"health", "religion", "politics", "ethnicity", "sexual_orientation", "finance", "precise_address"}
IDENTITY_FIELDS = {"birth_year", "age_as_of", "gender", "education", "profession", "specialty", "timezone"}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="View, update or forget confirmed shared profile memory")
    parser.add_argument("--kb-root")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("show")
    set_command = commands.add_parser("set")
    set_command.add_argument("--payload-file", required=True, help="UTF-8 JSON field update payload")
    set_command.add_argument("--allow-sensitive", action="store_true")
    forget = commands.add_parser("forget")
    forget.add_argument("field")
    invitation = commands.add_parser("invitation")
    invitation.add_argument("choice", choices=("later", "never", "reset"))
    return parser.parse_args(argv)


def profile_path(paths):
    return paths["memory"] / "shared" / "profile.json"


def set_fields(paths, config, payload_path, allow_sensitive=False):
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("fields"), dict):
        raise AlayaError("Payload must contain a fields object")
    current = read_json(profile_path(paths), default={}) or {}
    current.setdefault("version", 2)
    fields = current.setdefault("fields", {})
    timestamp = datetime.now().isoformat(timespec="seconds")
    for name, item in payload["fields"].items():
        if not isinstance(item, dict) or "value" not in item:
            raise AlayaError("Each profile field requires a value")
        if contains_secret_like(item["value"]):
            raise AlayaError("Secret-like values are never stored in Alaya memory")
        if name in SENSITIVE_FIELDS and not allow_sensitive:
            raise AlayaError("Sensitive field requires --allow-sensitive and explicit user request: %s" % name)
        source = item.get("source", "user_confirmed")
        if name in IDENTITY_FIELDS and source not in ("user_stated", "user_confirmed"):
            raise AlayaError("Identity field cannot be inferred: %s" % name)
        old = fields.get(name)
        if old and old.get("value") != item["value"] and not item.get("replace_confirmed"):
            raise AlayaError("Field conflicts with saved value; set replace_confirmed after user confirmation: %s" % name)
        if old and old.get("value") != item["value"]:
            current.setdefault("change_history", []).append({
                "field": name,
                "old_value": old.get("value"),
                "changed_at": timestamp,
                "source": "user_confirmed",
            })
        fields[name] = {
            "value": item["value"],
            "source": source,
            "evidence": item.get("evidence", "explicit local profile update"),
            "first_seen": old.get("first_seen", timestamp) if old else timestamp,
            "last_confirmed": timestamp,
            "status": "confirmed",
            "sensitivity": item.get("sensitivity", "sensitive" if name in SENSITIVE_FIELDS else "normal"),
            "share_scope": item.get("share_scope", "all_personas"),
            "review_after": item.get("review_after"),
        }
    current["updated_at"] = timestamp
    maximum = int(config.get("memory", {}).get("profile_max_kb", 128)) * 1024
    if len(json.dumps(current, ensure_ascii=False).encode("utf-8")) > maximum:
        raise AlayaError("Confirmed profile exceeds its size limit; remove or summarize fields first")
    atomic_write_json(profile_path(paths), current)
    print("Confirmed profile fields updated: %s" % ", ".join(sorted(payload["fields"])))


def forget_field(paths, field):
    path = profile_path(paths)
    current = read_json(path, default={}) or {}
    fields = current.get("fields", {})
    if field not in fields:
        print("Profile field was not present: %s" % field)
        return
    fields.pop(field)
    current["change_history"] = [item for item in current.get("change_history", []) if item.get("field") != field]
    current["updated_at"] = datetime.now().isoformat(timespec="seconds")
    atomic_write_json(path, current)
    print("Profile field forgotten: %s" % field)


def set_invitation(paths, choice):
    path = paths["memory"] / "shared" / "profile_invitation.json"
    if choice == "reset":
        value = {"status": "not_asked"}
    elif choice == "never":
        value = {"status": "declined", "updated_at": datetime.now().isoformat(timespec="seconds")}
    else:
        from datetime import timedelta
        value = {
            "status": "deferred",
            "defer_until": (datetime.now() + timedelta(days=30)).date().isoformat(),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    atomic_write_json(path, value)
    print("Profile invitation preference updated: %s" % choice)


def main(argv=None):
    args = parse_args(argv)
    try:
        root = resolve_kb_root(args.kb_root)
        paths = knowledge_paths(root)
        config = load_effective_config(root)
        if args.command == "show":
            print(json.dumps(read_json(profile_path(paths), default={}) or {}, ensure_ascii=False, indent=2))
        elif args.command == "set":
            set_fields(paths, config, args.payload_file, args.allow_sensitive)
        elif args.command == "forget":
            forget_field(paths, args.field)
        elif args.command == "invitation":
            set_invitation(paths, args.choice)
        return 0
    except (AlayaError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
