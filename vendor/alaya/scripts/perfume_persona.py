"""Idempotent persona affinity updates."""

import json
from pathlib import Path

from lib.runtime import atomic_write_json
from lib.yaml_utils import persona_key


def _load_persona(path):
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Persona JSON must contain an object: %s" % path)
    return value


def plan_update_affinity(manas_dir, participants, event_id, increment=0.01):
    root = Path(manas_dir)
    keys = []
    for participant in participants or []:
        key = persona_key(str(root), participant)
        if key and key not in keys:
            keys.append(key)
    writes = []
    for key in keys:
        path = root / (key + ".json")
        if not path.is_file():
            continue
        data = _load_persona(path)
        events = list(data.get("recent_affinity_events", []))
        if event_id in events:
            continue
        affinity = data.setdefault("affinity", {})
        for other in keys:
            if other == key:
                continue
            current = affinity.get(other, {"score": 0.0})
            if isinstance(current, dict):
                current["score"] = round(min(1.0, float(current.get("score", 0.0)) + increment), 4)
                affinity[other] = current
            else:
                affinity[other] = round(min(1.0, float(current) + increment), 4)
        data["recent_affinity_events"] = (events + [event_id])[-100:]
        writes.append((path, data))
    return writes


def update_affinity(manas_dir, persona_name, increment=0.01, event_id="manual"):
    writes = plan_update_affinity(manas_dir, [persona_name], event_id, increment)
    for path, value in writes:
        atomic_write_json(path, value)
    return len(writes)


def plan_decay_affinity(manas_dir, affinity_decay, xunxi_days):
    root = Path(manas_dir)
    writes = []
    for path in root.glob("*.json"):
        data = _load_persona(path)
        affinity = data.get("affinity", {})
        if not affinity:
            continue
        for other, value in list(affinity.items()):
            if isinstance(value, dict) and "score" in value:
                value["score"] = round(float(value["score"]) * (affinity_decay ** xunxi_days), 4)
            elif isinstance(value, (int, float)):
                affinity[other] = round(float(value) * (affinity_decay ** xunxi_days), 4)
        writes.append((path, data))
    return writes


def decay_affinity(manas_dir, affinity_decay, xunxi_days):
    writes = plan_decay_affinity(manas_dir, affinity_decay, xunxi_days)
    for path, data in writes:
        atomic_write_json(path, data)
    return len(writes)
