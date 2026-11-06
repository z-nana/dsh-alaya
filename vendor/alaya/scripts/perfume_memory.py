"""Pure builders and safe writers for private and shared Alaya memory."""

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from lib.runtime import atomic_write_json, read_json


def _today_str():
    return date.today().isoformat()


def stable_event_id(persona_key, user_text, answer_text):
    value = "%s\n%s\n%s" % (persona_key, user_text or "", answer_text or "")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _unique(existing, incoming, key=None):
    result = list(existing or [])
    seen = set()
    for item in result:
        marker = key(item) if key else json.dumps(item, ensure_ascii=False, sort_keys=True)
        seen.add(marker)
    for item in incoming or []:
        marker = key(item) if key else json.dumps(item, ensure_ascii=False, sort_keys=True)
        if marker not in seen:
            result.append(item)
            seen.add(marker)
    return result


def _compress_history_entry(entry):
    return {
        key: entry.get(key)
        for key in (
            "date", "type", "subject", "summary", "before", "after", "topics",
            "tags", "decisions", "group_id", "event_id",
        )
        if entry.get(key) not in (None, "", [])
    }


def _json_bytes(value):
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def build_private_memory_update(memory_dir, persona_key, entry, config, event_id, group_id=None):
    """Build one idempotent active-day update without writing it."""
    memory_path = Path(memory_dir) / (persona_key + "_history.json")
    current = read_json(memory_path, default={}) or {}
    if not isinstance(current, dict):
        raise ValueError("Private memory must be a JSON object: %s" % memory_path)
    hot = list(current.get("hot", []))
    cold = list(current.get("cold", []))
    recent_ids = list(current.get("recent_event_ids", []))
    if event_id in recent_ids:
        return memory_path, current, False

    today = entry.get("date") or _today_str()
    active = current.get("active_day")
    if active and active.get("date") != today:
        hot.append(active)
        active = None

    if not active:
        active = {
            "date": today,
            "topics": [],
            "tags": [],
            "summary": "",
            "key_insights": [],
            "decisions": [],
            "open_threads": [],
            "cards_cited": [],
            "turns": 0,
            "event_ids": [],
            "last_updated": "",
        }

    active["topics"] = _unique(active.get("topics", []), entry.get("topics") or ([entry.get("topic")] if entry.get("topic") else []), key=lambda value: str(value).casefold())
    active["tags"] = _unique(active.get("tags", []), entry.get("tags", []), key=lambda value: str(value).casefold())
    active["key_insights"] = _unique(active.get("key_insights", []), entry.get("key_insights", []))
    active["decisions"] = _unique(active.get("decisions", []), entry.get("decisions", []))
    active["open_threads"] = _unique(active.get("open_threads", []), entry.get("open_threads", []))
    active["cards_cited"] = _unique(active.get("cards_cited", []), entry.get("cards_cited", []), key=lambda value: str(value).casefold())
    if entry.get("summary"):
        active["summary"] = str(entry["summary"])[:4000]
    if entry.get("mood"):
        active["mood"] = entry["mood"]
    active["turns"] = int(active.get("turns", 0)) + max(1, int(entry.get("turns", 1)))
    active["event_ids"] = _unique(active.get("event_ids", []), [event_id])[-100:]
    if group_id:
        active["group_ids"] = _unique(active.get("group_ids", []), [group_id])[-50:]
    active["last_updated"] = datetime.now().isoformat(timespec="seconds")
    for key in ("topics", "tags", "key_insights", "decisions", "open_threads", "cards_cited"):
        active[key] = list(active.get(key, []))[-50:]

    memory_cfg = config.get("memory", {})
    hot_limit = int(memory_cfg.get("hot_zone_size", memory_cfg.get("hot_limit", 5)))
    cold_limit = int(memory_cfg.get("cold_zone_size", memory_cfg.get("cold_limit", 45)))
    while len(hot) > hot_limit:
        cold.append(_compress_history_entry(hot.pop(0)))
    if cold_limit >= 0:
        cold = cold[-cold_limit:] if cold_limit else []

    updated = dict(current)
    updated["hot"] = hot
    updated["cold"] = cold
    updated["active_day"] = active
    updated["recent_event_ids"] = _unique(recent_ids, [event_id])[-200:]
    return memory_path, updated, True


def build_ambient_update(memory_dir, mood, tags, config, participants=None):
    path = Path(memory_dir) / "ambient.json"
    ambient = read_json(path, default={}) or {}
    if not isinstance(ambient, dict):
        raise ValueError("ambient.json must contain a JSON object")
    memory_cfg = config.get("memory", {})
    if mood:
        ambient["recent_mood"] = mood
        trajectory = list(ambient.get("mood_trajectory", []))
        if not trajectory or trajectory[-1] != mood:
            trajectory.append(mood)
        ambient["mood_trajectory"] = trajectory[-int(memory_cfg.get("mood_trajectory_size", 3)):]
    attention = dict(ambient.get("recent_attention", {}))
    decay = float(memory_cfg.get("attention_decay_rate", 0.7))
    boost = float(memory_cfg.get("attention_boost_rate", 0.3))
    prune = float(memory_cfg.get("attention_prune_threshold", 0.1))
    for key in list(attention):
        attention[key] = round(float(attention[key]) * decay, 4)
    for tag in tags or []:
        attention[tag] = round(min(1.0, float(attention.get(tag, 0.0)) + boost), 4)
    ambient["recent_attention"] = {key: value for key, value in attention.items() if value >= prune}
    if len(ambient["recent_attention"]) > 100:
        ranked = sorted(ambient["recent_attention"].items(), key=lambda item: item[1], reverse=True)[:100]
        ambient["recent_attention"] = dict(ranked)
    if participants:
        ambient["recent_personas"] = _unique([], participants)[-10:]
    ambient["last_saved_at"] = datetime.now().isoformat(timespec="seconds")
    maximum = int(memory_cfg.get("ambient_max_kb", 64)) * 1024
    if _json_bytes(ambient) > maximum:
        raise ValueError("ambient.json exceeds its size limit; summarize the incoming state")
    return path, ambient


def build_shared_update(memory_dir, event_id, state_patch=None, history_event=None, config=None):
    shared = Path(memory_dir) / "shared"
    state_path = shared / "state.json"
    history_path = shared / "history.json"
    state = read_json(state_path, default={}) or {}
    history = read_json(history_path, default={}) or {}
    if not isinstance(state, dict) or not isinstance(history, dict):
        raise ValueError("Shared state and history must be JSON objects")
    if not state_patch and not history_event:
        return [], False
    processed = list(history.get("recent_event_ids", []))
    if event_id in processed:
        return [], False

    for key, value in (state_patch or {}).items():
        if isinstance(value, list):
            state[key] = _unique(state.get(key, []), value)[-100:]
        elif value is None:
            state.pop(key, None)
        else:
            state[key] = value
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")

    hot = list(history.get("hot", []))
    cold = list(history.get("cold", []))
    if history_event:
        event = dict(history_event)
        event.setdefault("event_id", event_id)
        event.setdefault("date", _today_str())
        hot.append(event)
    memory_cfg = (config or {}).get("memory", {})
    state_max = int(memory_cfg.get("state_max_kb", 128)) * 1024
    if _json_bytes(state) > state_max:
        raise ValueError("shared/state.json exceeds its size limit; remove expired state or summarize it")
    hot_limit = int(memory_cfg.get("shared_history_hot", 20))
    cold_limit = int(memory_cfg.get("shared_history_cold", 80))
    while len(hot) > hot_limit:
        cold.append(_compress_history_entry(hot.pop(0)))
    history["hot"] = hot
    history["cold"] = cold[-cold_limit:] if cold_limit else []
    history["recent_event_ids"] = _unique(processed, [event_id])[-200:]
    history_max = int(memory_cfg.get("shared_history_max_kb", 512)) * 1024
    while _json_bytes(history) > history_max and history["cold"]:
        history["cold"].pop(0)
    while _json_bytes(history) > history_max and len(history["hot"]) > 1:
        history["hot"].pop(0)
    if _json_bytes(history) > history_max:
        raise ValueError("shared/history.json exceeds its size limit; summarize the newest event")
    return [(state_path, state), (history_path, history)], True


def render_shared_index(memory_dir):
    shared = Path(memory_dir) / "shared"
    profile = read_json(shared / "profile.json", default={}) or {}
    state = read_json(shared / "state.json", default={}) or {}
    lines = ["# Alaya Shared Memory", ""]
    if profile:
        lines.extend(["## User preferences", ""])
        fields = profile.get("fields", {}) if isinstance(profile.get("fields", {}), dict) else {}
        for key in ("display_name", "language", "response_style", "long_term_interests"):
            item = fields.get(key, {}) if isinstance(fields.get(key, {}), dict) else {}
            if (
                item.get("value") not in (None, "", [])
                and item.get("share_scope", "all_personas") == "all_personas"
                and item.get("status", "confirmed") in ("confirmed", "legacy_preserved")
            ):
                lines.append("- %s: %s" % (key, str(item["value"])[:1000]))
        lines.append("")
    if state:
        lines.extend(["## Current shared state", ""])
        for key, value in state.items():
            if key != "updated_at" and value not in (None, "", []):
                lines.append("- %s: %s" % (key, str(value)[:1000]))
        lines.append("")
    lines.extend([
        "## Details",
        "",
        "- Profile: `profile.json`",
        "- Current state: `state.json`",
        "- Change history: `history.json`",
        "- Topic notes: `topics/`",
    ])
    rendered = "\n".join(lines[:200]) + "\n"
    if len(rendered.encode("utf-8")) > 25 * 1024:
        rendered = rendered.encode("utf-8")[:25 * 1024].decode("utf-8", errors="ignore").rstrip() + "\n"
    return rendered


def write_history(memory_dir, persona_key, entry, hot_limit=5, cold_limit=45, event_id=None):
    """Compatibility wrapper: write one semantic event into active_day."""
    config = {"memory": {"hot_zone_size": hot_limit, "cold_zone_size": cold_limit}}
    event_id = event_id or stable_event_id(persona_key, entry.get("topic"), entry.get("summary"))
    path, value, changed = build_private_memory_update(memory_dir, persona_key, entry, config, event_id)
    if changed:
        atomic_write_json(path, value)
    return changed


def update_ambient(memory_dir, mood=None, tags=None, config=None, participants=None):
    path, value = build_ambient_update(memory_dir, mood, tags, config or {}, participants)
    atomic_write_json(path, value)
    return value


def migrate_from_manas(_manas_dir, _memory_dir):
    """Legacy no-op retained for callers; private histories are never auto-moved."""
    return 0
