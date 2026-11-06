#!/usr/bin/env python3
"""Alaya interaction commit and idempotent xunxi maintenance."""

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.runtime import (  # noqa: E402
    AlayaError,
    FileLock,
    commit_text_bundle,
    contains_secret_like,
    knowledge_paths,
    load_effective_config,
    read_json,
    resolve_kb_root,
)
from perfume_knowledge import plan_boost_cards, plan_decay_all  # noqa: E402
from perfume_memory import (  # noqa: E402
    build_ambient_update,
    build_private_memory_update,
    build_shared_update,
    render_shared_index,
)
from perfume_persona import plan_decay_affinity, plan_update_affinity  # noqa: E402
from lib.yaml_utils import persona_key  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Commit Alaya interaction memory or run xunxi")
    parser.add_argument(
        "--level",
        required=True,
        choices=("1", "2", "3", "save", "answer", "group"),
        help="1=mechanical, answer/save=single response, group=group summary, 2=manual xunxi, 3=due check",
    )
    parser.add_argument("--kb-root", help="Knowledge-base root override")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--payload-file", help="UTF-8 JSON file, or - for stdin")
    group.add_argument("--payload", help="Legacy inline JSON payload; file/stdin is safer")
    return parser.parse_args(argv)


def load_payload(args):
    if args.payload_file == "-":
        text = sys.stdin.read()
    elif args.payload_file:
        text = Path(args.payload_file).read_text(encoding="utf-8-sig")
    elif args.payload:
        text = args.payload
    else:
        return {}
    value = json.loads(text)
    if not isinstance(value, dict):
        raise AlayaError("Interaction payload must be a JSON object")
    return value


def _json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _persona_exists(paths, name):
    key = persona_key(str(paths["manas"]), name)
    return key, (paths["manas"] / (key + ".json")).is_file()


def validate_payload(paths, payload, level, config):
    if contains_secret_like(payload):
        raise AlayaError("Secret-like values are never stored in Alaya memory")
    event_id = payload.get("group_id") if level == "group" else payload.get("turn_id")
    if not isinstance(event_id, str) or not event_id.strip():
        raise AlayaError("Payload requires a non-empty %s" % ("group_id" if level == "group" else "turn_id"))
    cards = payload.get("cards_cited", [])
    tags = payload.get("tags", [])
    if not isinstance(cards, list) or not all(isinstance(item, str) for item in cards):
        raise AlayaError("cards_cited must be a list of strings")
    if not isinstance(tags, list) or not all(isinstance(item, str) for item in tags):
        raise AlayaError("tags must be a list of strings")
    if payload.get("mood") is not None and not isinstance(payload.get("mood"), str):
        raise AlayaError("mood must be a string")
    for field in ("shared_state", "shared_event"):
        if payload.get(field) is not None and not isinstance(payload.get(field), dict):
            raise AlayaError("%s must be a JSON object" % field)

    participants = payload.get("participants")
    if level == "group":
        if not isinstance(participants, list) or not participants:
            raise AlayaError("Group payload requires participants")
        maximum = int(config.get("persona", {}).get("max_participants_in_discussion", 6))
        if len(participants) > maximum:
            raise AlayaError("Group payload exceeds max_participants_in_discussion")
        normalized = []
        seen = set()
        for item in participants:
            if not isinstance(item, dict) or not item.get("persona"):
                raise AlayaError("Each participant requires persona and optional history")
            key, exists = _persona_exists(paths, item["persona"])
            if not exists:
                raise AlayaError("Persona was not found: %s" % item["persona"])
            if key.casefold() in seen:
                raise AlayaError("Group payload repeats persona: %s" % item["persona"])
            seen.add(key.casefold())
            normalized.append((key, item))
        return event_id, normalized

    persona = payload.get("persona")
    if not persona:
        raise AlayaError("Payload requires persona")
    key, exists = _persona_exists(paths, persona)
    if not exists:
        raise AlayaError("Persona was not found: %s" % persona)
    return event_id, [(key, {"persona": persona, "history": payload.get("history")})]


def prepare_interaction_writes(paths, config, payload, level):
    event_id, participants = validate_payload(paths, payload, level, config)
    writes = []
    today = date.today().isoformat()
    participant_keys = [key for key, _item in participants]

    card_writes, dirty = plan_boost_cards(
        str(paths["wiki"]), payload.get("cards_cited", []), config.get("knowledge", {}), today, event_id
    )
    writes.extend(card_writes)

    ambient_path, ambient = build_ambient_update(
        paths["memory"],
        payload.get("mood"),
        payload.get("tags", []),
        config,
        participant_keys,
    )
    ambient_events = list(ambient.get("recent_event_ids", []))
    if event_id not in ambient_events:
        ambient["recent_event_ids"] = (ambient_events + [event_id])[-200:]
        writes.append((ambient_path, _json_text(ambient)))

    affinity_writes = plan_update_affinity(paths["manas"], participant_keys, event_id)
    writes.extend((path, _json_text(value)) for path, value in affinity_writes)

    semantic_enabled = (
        config.get("memory", {}).get("semantic_memory_enabled", True)
        and not payload.get("no_semantic_memory", False)
        and level != "1"
    )
    if semantic_enabled:
        for key, item in participants:
            history = item.get("history")
            if not history:
                continue
            if not isinstance(history, dict):
                raise AlayaError("history must be a JSON object")
            private_event = "%s:%s" % (event_id, key) if level == "group" else event_id
            path, value, changed = build_private_memory_update(
                paths["memory"], key, history, config, private_event,
                group_id=event_id if level == "group" else None,
            )
            if changed:
                writes.append((path, _json_text(value)))

        shared_items, shared_changed = build_shared_update(
            paths["memory"],
            event_id,
            state_patch=payload.get("shared_state"),
            history_event=payload.get("shared_event"),
            config=config,
        )
        if shared_changed and shared_items:
            writes.extend((path, _json_text(value)) for path, value in shared_items)

    raw_config = read_json(paths["config"], default={}) or {}
    raw_knowledge = raw_config.setdefault("knowledge", {})
    existing_dirty = list(raw_knowledge.get("dirty_categories", []))
    for category in dirty:
        if category not in existing_dirty:
            existing_dirty.append(category)
    if existing_dirty != raw_knowledge.get("dirty_categories", []):
        raw_knowledge["dirty_categories"] = existing_dirty
        writes.append((paths["config"], _json_text(raw_config)))

    # Validate every target and payload before the first file changes.
    deduplicated = []
    positions = {}
    for path, text in writes:
        path = Path(path).resolve()
        if path in positions:
            deduplicated[positions[path]] = (path, text)
        else:
            positions[path] = len(deduplicated)
            deduplicated.append((path, text))
    return event_id, deduplicated


def commit_interaction(paths, config, payload, level):
    event_id, writes = prepare_interaction_writes(paths, config, payload, level)
    if writes:
        commit_text_bundle(paths["alaya"], event_id, writes)
    shared = paths["memory"] / "shared"
    if shared.exists():
        # The index is derived and intentionally committed after core memory.
        # A retry of the same event can therefore repair this derived file.
        from lib.runtime import atomic_write_text
        atomic_write_text(shared / "INDEX.md", render_shared_index(paths["memory"]))
    print("Interaction committed: %s (%d files)" % (event_id, len(writes)))


def _date_value(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def run_xunxi(paths, config, force=False):
    raw_config = read_json(paths["config"], default={}) or {}
    last = _date_value(raw_config.get("last_xunxi_time"))
    today = date.today()
    interval = int(config.get("maintenance", {}).get("auto_xunxi_interval_days", 1))
    if last is not None and (today - last).days < interval:
        print("Xunxi already settled for the current interval.")
        return False
    days = max(1, (today - last).days) if last else 1
    with FileLock(paths["alaya"] / ".xunxi.lock", stale_seconds=1800):
        card_writes, total, decayed, slept = plan_decay_all(
            str(paths["wiki"]), config.get("knowledge", {}), today
        )
        persona_writes = plan_decay_affinity(
            paths["manas"], config.get("persona", {}).get("affinity_decay", 0.992), days
        )
        raw_config["last_xunxi_time"] = today.isoformat()
        knowledge = raw_config.setdefault("knowledge", {})
        knowledge["sleep_counter"] = int(knowledge.get("sleep_counter", 0)) + slept
        writes = list(card_writes)
        writes.extend((path, _json_text(value)) for path, value in persona_writes)
        index_meta_path = paths["alaya"] / ".index_metadata.json"
        index_meta = read_json(index_meta_path, default={}) or {}
        due = []
        if isinstance(index_meta, dict) and index_meta:
            from build_index import due_categories
            due = due_categories(index_meta, config)
            if due != index_meta.get("stale_descriptions", []):
                index_meta["stale_descriptions"] = due
                writes.append((index_meta_path, _json_text(index_meta)))
        writes.append((paths["config"], _json_text(raw_config)))
        commit_text_bundle(paths["alaya"], "xunxi-%s" % today.isoformat(), writes)
    print("Xunxi complete: cards=%d decayed=%d newly_sleeping=%d" % (total, decayed, slept))
    if due:
        print("Category descriptions due for user choice: %s" % ", ".join(due))
    return True


def main(argv=None):
    args = parse_args(argv)
    try:
        root = resolve_kb_root(args.kb_root)
        paths = knowledge_paths(root)
        config = load_effective_config(root)
        if not config.get("enabled", True):
            print("Alaya is disabled; no maintenance or memory write was performed.")
            return 0
        if args.level in ("2", "3"):
            run_xunxi(paths, config, force=args.level == "2")
        else:
            payload = load_payload(args)
            commit_interaction(paths, config, payload, args.level)
        return 0
    except (AlayaError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
