#!/usr/bin/env python3
"""BI observer with replaceable current state and bounded change history."""

import argparse
import json
import os
import shutil
import sys
import hashlib
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.runtime import (  # noqa: E402
    AlayaError,
    atomic_write_json,
    knowledge_paths,
    load_effective_config,
    read_json,
    resolve_kb_root,
)
from lib.yaml_utils import get_description, get_field, get_all_cards, read_frontmatter  # noqa: E402


DOMAINS = (
    "user_trajectory",
    "persona_ecology",
    "knowledge_ecology",
    "retrieval_effect",
    "import_growth",
    "system_maintenance",
)
STATE_MAX_BYTES = 256 * 1024


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Observe Alaya patterns without ranking personas")
    parser.add_argument("--kb-root")
    parser.add_argument("--write", action="store_true", help="Update bi_state.json and bounded bi_notes.json")
    parser.add_argument("--migrate", action="store_true", help="Back up and convert a legacy snapshot list")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args(argv)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def observation(domain, kind, subject, conclusion, evidence_count=1, evidence=None, severity="info", action=""):
    return {
        "id": "%s:%s:%s" % (domain, kind, subject),
        "domain": domain,
        "type": kind,
        "subject": subject,
        "conclusion": conclusion,
        "evidence_count": int(evidence_count),
        "evidence": list(evidence or [])[:3],
        "severity": severity,
        "suggested_action": action,
    }


def _parse_date(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def observe_user(paths):
    values = []
    profile = read_json(paths["memory"] / "shared" / "profile.json", default={}) or {}
    if not profile:
        values.append(observation(
            "user_trajectory", "profile_missing", "shared_profile",
            "No confirmed shared user profile exists.",
            severity="info", action="Offer the optional local profile invitation after the main answer.",
        ))
    else:
        updated = _parse_date(profile.get("updated_at"))
        if updated and (date.today() - updated).days > 180:
            values.append(observation(
                "user_trajectory", "profile_stale", "shared_profile",
                "The confirmed shared profile has not been reviewed for more than 180 days.",
                evidence=[profile.get("updated_at")], action="Ask whether the saved preferences are still current.",
            ))
    return values


def newest_private_date(path):
    value = read_json(path, default={}) or {}
    entries = []
    if isinstance(value, dict):
        entries.extend(value.get("hot", []))
        if value.get("active_day"):
            entries.append(value["active_day"])
    dates = [_parse_date(item.get("date")) for item in entries if isinstance(item, dict)]
    dates = [item for item in dates if item]
    return max(dates) if dates else None


def observe_personas(paths, config):
    values = []
    personas = []
    for path in paths["manas"].glob("*.json"):
        personas.append(path.stem)
        if not path.with_name(path.stem + "_profile.md").exists():
            values.append(observation(
                "persona_ecology", "missing_profile", path.stem,
                "Persona configuration exists without a profile.",
                evidence=[path.name], severity="warning", action="Create or restore the persona profile.",
            ))
        last = newest_private_date(paths["memory"] / (path.stem + "_history.json"))
        if last and (date.today() - last).days > 14:
            days = (date.today() - last).days
            values.append(observation(
                "persona_ecology", "dormant_persona", path.stem,
                "Persona has not participated for %d days." % days,
                evidence_count=days, evidence=[last.isoformat()], action="Mention the persona only when its perspective is relevant.",
            ))
    default = config.get("persona", {}).get("default_persona", "feynman")
    if default not in personas:
        values.append(observation(
            "persona_ecology", "missing_default", default,
            "The configured default persona does not exist.", severity="high",
            action="Choose an existing default persona.",
        ))
    return values


def observe_knowledge(paths, config):
    values = []
    by_name = defaultdict(list)
    missing_description = []
    broken_sources = []
    category_counts = defaultdict(int)
    cold_warning = []
    dormant = []
    knowledge_cfg = config.get("knowledge", {})
    warning_days = int(knowledge_cfg.get("cold_warning_days", 75))
    sleep_threshold = float(knowledge_cfg.get("sleep_threshold", 0.1))
    for category, name, path_string in get_all_cards(paths["wiki"]):
        path = Path(path_string)
        category_counts[category] += 1
        by_name[name.casefold()].append("%s/%s" % (category, name))
        result = read_frontmatter(path)
        if not result:
            continue
        yaml_str = result[1]
        if not get_description(yaml_str):
            missing_description.append("%s/%s" % (category, name))
        source_file = get_field(yaml_str, "source_file")
        if source_file and not str(source_file).lower().startswith(("http://", "https://")):
            target = Path(source_file)
            target = target if target.is_absolute() else paths["root"] / target
            if not target.exists():
                broken_sources.append("%s/%s" % (category, name))
        strength_value = get_field(yaml_str, "strength")
        activated = _parse_date(get_field(yaml_str, "last_activated"))
        try:
            strength = float(strength_value)
        except (TypeError, ValueError):
            strength = None
        if strength is not None and strength <= sleep_threshold:
            dormant.append("%s/%s" % (category, name))
        elif activated and (date.today() - activated).days >= warning_days:
            cold_warning.append("%s/%s" % (category, name))
    duplicates = [items for items in by_name.values() if len(items) > 1]
    if duplicates:
        samples = [" | ".join(items) for items in duplicates[:3]]
        values.append(observation(
            "knowledge_ecology", "duplicate_basenames", "wiki",
            "%d card names occur in more than one category; bare-name links may be ambiguous." % len(duplicates),
            len(duplicates), samples, "warning", "Use category-qualified links for ambiguous names.",
        ))
    if missing_description:
        values.append(observation(
            "knowledge_ecology", "missing_descriptions", "wiki",
            "%d cards lack a description." % len(missing_description), len(missing_description), missing_description,
            "warning", "Run the index builder on affected categories.",
        ))
    if broken_sources:
        values.append(observation(
            "knowledge_ecology", "broken_sources", "raw_links",
            "%d source_file references do not exist." % len(broken_sources), len(broken_sources), broken_sources,
            "warning", "Review source links without automatically rewriting them.",
        ))
    sparse = ["%s:%d" % item for item in category_counts.items() if item[1] < 3]
    if sparse:
        values.append(observation(
            "knowledge_ecology", "sparse_categories", "wiki",
            "%d categories contain fewer than three cards." % len(sparse), len(sparse), sparse,
            "info", "Review whether each sparse category is intentional.",
        ))
    if cold_warning:
        values.append(observation(
            "knowledge_ecology", "cold_warning", "knowledge_strength",
            "%d active cards have not been used for at least %d days." % (len(cold_warning), warning_days),
            len(cold_warning), cold_warning, "info", "Mention maintenance only when relevant; daily xunxi already runs by piggyback.",
        ))
    if dormant:
        values.append(observation(
            "knowledge_ecology", "dormant_cards", "knowledge_strength",
            "%d cards are currently at or below the sleep threshold." % len(dormant),
            len(dormant), dormant, "info", "Dormant cards can still be retrieved and reactivated when highly relevant.",
        ))
    return values


def observe_retrieval(paths):
    metrics = read_json(paths["alaya"] / "retrieval_metrics.json", default={}) or {}
    values = []
    if metrics.get("fallback_count", 0):
        values.append(observation(
            "retrieval_effect", "fallback_frequency", "retrieval",
            "Retrieval expanded beyond the initial categories %d times." % metrics["fallback_count"],
            metrics["fallback_count"], severity="info", action="Review category descriptions for repeated misses.",
        ))
    if metrics.get("unsupported_queries", 0):
        values.append(observation(
            "retrieval_effect", "unsupported_queries", "retrieval",
            "%d knowledge-base queries had no supporting cards." % metrics["unsupported_queries"],
            metrics["unsupported_queries"], severity="warning", action="Consider importing sources for recurring unsupported topics.",
        ))
    return values


def observe_import(paths):
    meta = read_json(paths["alaya"] / ".index_metadata.json", default={}) or {}
    due = list(meta.get("stale_descriptions", []))
    values = []
    if due:
        values.append(observation(
            "import_growth", "description_refresh_due", "categories",
            "%d category descriptions reached their change or three-day threshold." % len(due),
            len(due), due, "info", "Update the due category descriptions after the main task.",
        ))
    return values


def observe_system(paths, config):
    values = []
    if (paths["alaya"] / ".commit_journal.json").exists():
        values.append(observation(
            "system_maintenance", "unfinished_commit", "commit_journal",
            "An unfinished local commit journal requires roll-forward recovery.",
            severity="high", action="Retry the same Alaya operation before starting another write.",
        ))
    index = paths["wiki"] / "index.md"
    if not index.exists():
        values.append(observation(
            "system_maintenance", "missing_index", "wiki/index.md",
            "The total knowledge index is missing.", severity="high", action="Build the index.",
        ))
    last = _parse_date(read_json(paths["config"], default={}).get("last_xunxi_time"))
    if not last or (date.today() - last).days > int(config.get("maintenance", {}).get("auto_xunxi_interval_days", 1)):
        values.append(observation(
            "system_maintenance", "xunxi_due", "knowledge",
            "Knowledge strength settlement is due.", severity="warning", action="Run xunxi at the next stable Alaya entry.",
        ))
    knowledge = read_json(paths["config"], default={}).get("knowledge", {})
    sleep_count = int(knowledge.get("sleep_counter", 0))
    notify_at = int(config.get("knowledge", {}).get("sleep_notification_threshold", 30))
    if sleep_count >= notify_at:
        values.append(observation(
            "system_maintenance", "sleep_notification", "knowledge",
            "%d cards have crossed the sleep threshold since the counter was last cleared." % sleep_count,
            sleep_count, severity="info", action="Offer a concise review; do not wake cards automatically.",
        ))
    return values


def collect(paths, config):
    observations = []
    observations.extend(observe_user(paths))
    observations.extend(observe_personas(paths, config))
    observations.extend(observe_knowledge(paths, config))
    observations.extend(observe_retrieval(paths))
    observations.extend(observe_import(paths))
    observations.extend(observe_system(paths, config))
    return observations


def bounded_state(observations, old_state):
    old_by_id = {item["id"]: item for item in old_state.get("observations", []) if isinstance(item, dict) and item.get("id")}
    grouped = defaultdict(list)
    for item in observations:
        old = old_by_id.get(item["id"], {})
        item["first_seen"] = old.get("first_seen", now_iso())
        item["last_confirmed"] = now_iso()
        item["occurrences"] = int(old.get("occurrences", 0)) + 1
        grouped[item["domain"]].append(item)
    final = []
    for domain in DOMAINS:
        items = sorted(grouped[domain], key=lambda value: (value["severity"] != "high", value["id"]))
        final.extend(items[:20])
        overflow = items[20:]
        if overflow:
            final.append(observation(
                domain, "overflow_summary", domain,
                "%d additional observations were summarized by capacity control." % len(overflow),
                len(overflow), [item["id"] for item in overflow[:3]], "info", "Generate a live full report when needed.",
            ))
    for item in final:
        item["conclusion"] = str(item.get("conclusion", ""))[:1000]
        item["suggested_action"] = str(item.get("suggested_action", ""))[:1000]
        item["evidence"] = [str(value)[:500] for value in item.get("evidence", [])[:3]]
    state = {"version": 2, "updated_at": now_iso(), "observations": final}
    removed = defaultdict(int)
    while len(json.dumps(state, ensure_ascii=False).encode("utf-8")) > STATE_MAX_BYTES:
        candidates = [
            (index, item) for index, item in enumerate(state["observations"])
            if item.get("severity") != "high"
        ]
        if not candidates:
            high = list(state["observations"])
            grouped_high = []
            for domain in DOMAINS:
                items = [item for item in high if item.get("domain") == domain]
                if items:
                    grouped_high.append(observation(
                        domain, "high_capacity_summary", domain,
                        "%d high-severity observations were aggregated by the 256 KB state limit." % len(items),
                        len(items), [item.get("id") for item in items[:3]], "high",
                        "Generate a live report before taking corrective action.",
                    ))
            state["observations"] = grouped_high
            break
        index, item = candidates[-1]
        removed[item.get("domain", "system_maintenance")] += 1
        state["observations"].pop(index)
    for domain, count in removed.items():
        summary = observation(
            domain, "capacity_summary", domain,
            "%d observations were omitted from current state by the 256 KB limit." % count,
            count, severity="info", action="Generate a live full report when needed.",
        )
        probe = dict(state)
        probe["observations"] = state["observations"] + [summary]
        if len(json.dumps(probe, ensure_ascii=False).encode("utf-8")) <= STATE_MAX_BYTES:
            state = probe
    return state


def diff_history(old_state, new_state, old_history):
    old = {item["id"]: item for item in old_state.get("observations", []) if isinstance(item, dict) and item.get("id")}
    new = {item["id"]: item for item in new_state.get("observations", []) if isinstance(item, dict) and item.get("id")}
    events = list(old_history.get("events", [])) if isinstance(old_history, dict) else []
    timestamp = now_iso()
    for identity in sorted(set(old) | set(new)):
        if identity not in old:
            event_type = "new"
        elif identity not in new:
            event_type = "resolved"
        elif any(old[identity].get(key) != new[identity].get(key) for key in ("conclusion", "severity", "evidence_count")):
            event_type = "updated"
        else:
            continue
        source = new.get(identity) or old.get(identity)
        events.append({
            "date": timestamp,
            "event": event_type,
            "observation_id": identity,
            "domain": source.get("domain"),
            "summary": source.get("conclusion"),
            "severity": source.get("severity"),
        })
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    retained = []
    for event in events:
        try:
            stamp = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if stamp >= cutoff or event.get("severity") == "high":
            retained.append(event)
    retained = retained[-200:]
    while len(json.dumps(retained, ensure_ascii=False).encode("utf-8")) > 512 * 1024 and len(retained) > 1:
        retained.pop(0)
    return {"version": 2, "updated_at": timestamp, "events": retained}


def _legacy_snapshot_state(snapshot, first_seen, occurrences):
    grouped = defaultdict(list)
    for item in snapshot.get("system_health", []) if isinstance(snapshot, dict) else []:
        if isinstance(item, dict):
            grouped[str(item.get("type", "unknown"))].append(item)
    observed = []
    snapshot_date = str(snapshot.get("date", date.today().isoformat()))
    for kind, items in grouped.items():
        identity = "system_maintenance:legacy_%s:%s" % (kind, kind)
        severity_values = {"high": "high", "medium": "warning", "low": "info"}
        severity = max(
            (severity_values.get(str(item.get("severity", "low")).lower(), "info") for item in items),
            key=lambda value: {"info": 0, "warning": 1, "high": 2}[value],
        )
        evidence = [str(item.get("detail", ""))[:500] for item in items if item.get("detail")][:3]
        observed.append({
            "id": identity,
            "domain": "system_maintenance",
            "type": "legacy_%s" % kind,
            "subject": kind,
            "conclusion": "Legacy BI snapshot reported %d %s item(s)." % (len(items), kind),
            "evidence_count": len(items),
            "evidence": evidence,
            "severity": severity,
            "suggested_action": str(items[0].get("suggestion", ""))[:500] if items else "",
            "first_seen": first_seen.get(identity, snapshot_date),
            "last_confirmed": snapshot_date,
            "occurrences": occurrences.get(identity, 1),
        })
    return observed


def migrate_legacy(paths):
    notes = paths["alaya"] / "bi_notes.json"
    current = read_json(notes, default=[])
    if not isinstance(current, list):
        print("BI notes are already in the current history-object format.")
        return
    if not notes.exists():
        print("No legacy BI notes were found.")
        return
    backup = paths["alaya"] / ("bi_notes.legacy-%s.json" % datetime.now().strftime("%Y%m%d-%H%M%S"))
    counter = 1
    while backup.exists():
        backup = paths["alaya"] / ("bi_notes.legacy-%s-%d.json" % (datetime.now().strftime("%Y%m%d-%H%M%S"), counter))
        counter += 1
    shutil.copy2(str(notes), str(backup))
    snapshots = [item for item in current if isinstance(item, dict)]
    snapshots.sort(key=lambda item: str(item.get("date", "")))
    first_seen = {}
    occurrences = defaultdict(int)
    events = []
    previous = {}
    final_observations = []
    for snapshot in snapshots:
        probe = _legacy_snapshot_state(snapshot, first_seen, occurrences)
        for item in probe:
            first_seen.setdefault(item["id"], item["last_confirmed"])
            occurrences[item["id"]] += 1
        probe = _legacy_snapshot_state(snapshot, first_seen, occurrences)
        current_map = {item["id"]: item for item in probe}
        stamp = str(snapshot.get("date", date.today().isoformat())) + "T00:00:00+00:00"
        for identity in sorted(set(previous) | set(current_map)):
            if identity not in previous:
                event_type = "new"
            elif identity not in current_map:
                event_type = "resolved"
            else:
                old_signature = {key: previous[identity].get(key) for key in ("conclusion", "severity", "evidence_count", "evidence")}
                new_signature = {key: current_map[identity].get(key) for key in ("conclusion", "severity", "evidence_count", "evidence")}
                old_digest = hashlib.sha256(json.dumps(old_signature, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
                new_digest = hashlib.sha256(json.dumps(new_signature, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
                if old_digest == new_digest:
                    continue
                event_type = "updated"
            source = current_map.get(identity) or previous.get(identity)
            events.append({
                "date": stamp,
                "event": event_type,
                "observation_id": identity,
                "domain": "system_maintenance",
                "summary": source.get("conclusion"),
                "severity": source.get("severity"),
            })
        previous = current_map
        final_observations = probe
    state = {"version": 2, "updated_at": now_iso(), "observations": final_observations}
    history = {"version": 2, "updated_at": now_iso(), "events": events[-200:]}
    atomic_write_json(paths["alaya"] / "bi_state.json", state)
    atomic_write_json(notes, history)
    print("Legacy BI snapshots backed up: %s" % backup)


def main(argv=None):
    args = parse_args(argv)
    try:
        root = resolve_kb_root(args.kb_root)
        paths = knowledge_paths(root)
        config = load_effective_config(root)
        if not config.get("bi_enabled", True):
            print("BI is disabled; existing observation files were preserved.")
            return 0
        if args.migrate:
            migrate_legacy(paths)
        old_state = read_json(paths["alaya"] / "bi_state.json", default={}) or {}
        old_history = read_json(paths["alaya"] / "bi_notes.json", default={}) or {}
        if isinstance(old_history, list):
            old_history = {"events": []}
        observations = collect(paths, config)
        state = bounded_state(observations, old_state)
        history = diff_history(old_state, state, old_history)
        if args.write:
            atomic_write_json(paths["alaya"] / "bi_state.json", state)
            atomic_write_json(paths["alaya"] / "bi_notes.json", history)
        report = {"state": state, "new_history_events": len(history["events"]) - len(old_history.get("events", []))}
        if args.json_output:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("BI observations: %d" % len(state["observations"]))
            for domain in DOMAINS:
                items = [item for item in state["observations"] if item["domain"] == domain]
                print("  %s: %d" % (domain, len(items)))
                for item in items[:5]:
                    print("    [%s] %s" % (item["severity"], item["conclusion"]))
            print("Files updated: %s" % ("yes" if args.write else "no (read-only report)"))
        return 0
    except (AlayaError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("[ERROR] %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
