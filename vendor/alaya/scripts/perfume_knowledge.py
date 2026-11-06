"""Idempotent card activation and calendar-based strength settlement."""

import os
from datetime import date, datetime
from pathlib import Path

from lib.runtime import atomic_write_text, is_within
from lib.yaml_utils import (
    find_card,
    get_field,
    get_field_float,
    get_all_cards,
    read_frontmatter,
    rebuild_content,
    set_field,
)


def _as_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _read_card(wiki_dir, card_path):
    candidate = Path(card_path)
    if str(card_path).startswith(("wiki/", "wiki\\")):
        candidate = Path(wiki_dir).parent / card_path
    elif not candidate.is_absolute():
        direct = Path(wiki_dir) / candidate
        candidate = direct if direct.is_file() else Path(find_card(wiki_dir, candidate.stem) or "")
    if not candidate.is_file() or not is_within(candidate, wiki_dir):
        return None
    result = read_frontmatter(candidate)
    if not result:
        return None
    content, yaml_str, dash = result
    return content, yaml_str, dash, candidate


def plan_boost_cards(wiki_dir, cited_cards, kcfg, today, event_id):
    writes = []
    dirty = list(kcfg.get("dirty_categories", []))
    for card_path in cited_cards or []:
        result = _read_card(wiki_dir, card_path)
        if not result:
            continue
        content, yaml_str, dash, path = result
        if get_field(yaml_str, "last_activation_event") == event_id:
            continue
        strength = min(1.0, (get_field_float(yaml_str, "strength") or 0.5) + 0.03)
        try:
            count = int(get_field(yaml_str, "activation_count") or 0) + 1
        except ValueError:
            count = 1
        yaml_str = set_field(yaml_str, "strength", "%.4f" % strength)
        yaml_str = set_field(yaml_str, "activation_count", str(count))
        yaml_str = set_field(yaml_str, "last_activated", str(today))
        yaml_str = set_field(yaml_str, "strength_updated_at", str(today))
        yaml_str = set_field(yaml_str, "last_activation_event", event_id)
        writes.append((path, rebuild_content(yaml_str, dash, content)))
        if path.parent.name not in dirty:
            dirty.append(path.parent.name)
    return writes, dirty


def boost_cards(wiki_dir, cited_cards, kcfg, today, event_id="manual"):
    writes, dirty = plan_boost_cards(wiki_dir, cited_cards, kcfg, today, event_id)
    for path, content in writes:
        atomic_write_text(path, content)
    return len(writes), dirty


def plan_decay_all(wiki_dir, kcfg, today):
    today_date = today if isinstance(today, date) else _as_date(str(today))
    if today_date is None:
        raise ValueError("today must be YYYY-MM-DD or a date")
    global_decay = float(kcfg.get("strength_decay", 0.982276))
    threshold = float(kcfg.get("sleep_threshold", 0.1))
    writes = []
    total = decayed = slept = 0
    for _category, _name, path_string in get_all_cards(wiki_dir):
        path = Path(path_string)
        result = read_frontmatter(path)
        if not result:
            continue
        content, yaml_str, dash = result
        strength = get_field_float(yaml_str, "strength")
        if strength is None:
            continue
        total += 1
        last_activation = _as_date(get_field(yaml_str, "last_activated"))
        last_settlement = _as_date(get_field(yaml_str, "strength_updated_at"))

        # Compatibility baseline: the first new-style run never back-charges history.
        if last_settlement is None:
            yaml_str = set_field(yaml_str, "strength_updated_at", today_date.isoformat())
            writes.append((path, rebuild_content(yaml_str, dash, content)))
            continue

        base = max(value for value in (last_activation, last_settlement) if value is not None)
        days = max(0, (today_date - base).days)
        if days == 0:
            continue

        custom_half_life = get_field_float(yaml_str, "half_life")
        decay = global_decay
        if custom_half_life and abs(custom_half_life - 30.0) > 1e-9:
            decay = 0.5 ** (1.0 / custom_half_life)
        new_strength = round(strength * (decay ** days), 6)
        if strength > threshold and new_strength <= threshold:
            slept += 1
        yaml_str = set_field(yaml_str, "strength", "%.6f" % new_strength)
        yaml_str = set_field(yaml_str, "strength_updated_at", today_date.isoformat())
        writes.append((path, rebuild_content(yaml_str, dash, content)))
        decayed += 1
    return writes, total, decayed, slept


def decay_all(wiki_dir, kcfg, today):
    writes, total, decayed, slept = plan_decay_all(wiki_dir, kcfg, today)
    for path, content in writes:
        atomic_write_text(path, content)
    return total, decayed, slept


def wake_seeds(wiki_dir, keyword, kcfg, today):
    keyword_lower = keyword.casefold()
    wake_strength = float(kcfg.get("wake_strength", 0.5))
    threshold = float(kcfg.get("sleep_threshold", 0.1))
    count = 0
    for _category, name, path_string in get_all_cards(wiki_dir):
        if keyword_lower not in name.casefold().replace("-", " "):
            continue
        path = Path(path_string)
        result = read_frontmatter(path)
        if not result:
            continue
        content, yaml_str, dash = result
        strength = get_field_float(yaml_str, "strength")
        if strength is None or strength >= threshold:
            continue
        yaml_str = set_field(yaml_str, "strength", str(wake_strength))
        yaml_str = set_field(yaml_str, "last_activated", str(today))
        yaml_str = set_field(yaml_str, "strength_updated_at", str(today))
        atomic_write_text(path, rebuild_content(yaml_str, dash, content))
        count += 1
    return count


def sleep_check(kcfg):
    counter = int(kcfg.get("sleep_counter", 0))
    threshold = int(kcfg.get("sleep_notification_threshold", 30))
    return counter >= threshold, counter, threshold
