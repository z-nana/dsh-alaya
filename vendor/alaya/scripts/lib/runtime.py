"""Shared runtime primitives for Alaya.

The module deliberately uses only the Python standard library.  User data lives
under a configured knowledge-base root; the installed skill tree is never a
runtime data directory.
"""

from __future__ import print_function

import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import time
import re
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "config" / "default_config.json"
POINTER_NAME = ".alaya_path"
SECRET_PATTERNS = (
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,})\b"),
    re.compile(r"\b\d{15,19}\b"),
)


class AlayaError(RuntimeError):
    pass


class ConfigError(AlayaError):
    pass


def configure_console():
    """Keep old Windows consoles usable when a message contains Unicode."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(errors="backslashreplace")
            except (AttributeError, ValueError):
                pass


def pointer_path():
    explicit = os.environ.get("ALAYA_PATH_FILE")
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / POINTER_NAME


def _looks_like_kb(path):
    return (path / "alaya" / "config.json").is_file()


def resolve_kb_root(explicit=None, require=True, cwd=None):
    """Resolve the knowledge-base root without ever falling back to skill data."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())

    pfile = pointer_path()
    if pfile.is_file():
        try:
            line = pfile.read_text(encoding="utf-8-sig").splitlines()[0].strip()
            if line:
                candidates.append(Path(line).expanduser())
        except (OSError, IndexError, UnicodeError):
            pass

    base = Path(cwd or os.getcwd())
    if _looks_like_kb(base):
        candidates.append(base)

    checked = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate.absolute()
        if str(resolved) in checked:
            continue
        checked.append(str(resolved))
        if _looks_like_kb(resolved):
            return resolved

    if require:
        detail = ", ".join(checked) if checked else "no configured path"
        raise AlayaError(
            "Alaya knowledge base was not found (%s). Run setup_wizard.py first."
            % detail
        )
    return None


def knowledge_paths(root):
    root = Path(root).resolve()
    return {
        "root": root,
        "alaya": root / "alaya",
        "wiki": root / "wiki",
        "raw": root / "raw",
        "memory": root / "alaya" / "memory",
        "manas": root / "alaya" / "manas",
        "config": root / "alaya" / "config.json",
    }


def is_within(path, base):
    try:
        Path(path).resolve().relative_to(Path(base).resolve())
        return True
    except (ValueError, OSError):
        return False


def require_within(path, base):
    target = Path(path).resolve()
    parent = Path(base).resolve()
    if not is_within(target, parent):
        raise AlayaError("Path escapes allowed directory: %s" % target)
    return target


def read_json(path, default=None):
    try:
        with Path(path).open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default


def contains_secret_like(value):
    text = json.dumps(value, ensure_ascii=False)
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _deep_merge(base, overlay):
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return overlay
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _positive_int(value, name, minimum=1, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError("%s must be an integer" % name)
    if value < minimum or (maximum is not None and value > maximum):
        raise ConfigError("%s is outside the supported range" % name)
    return value


def _ratio(value, name, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError("%s must be numeric" % name)
    low = 0.0 if allow_zero else 0.0 + 1e-12
    if value < low or value > 1.0:
        raise ConfigError("%s must be between 0 and 1" % name)
    return float(value)


def load_effective_config(kb_root=None, user_config_path=None, defaults_path=None):
    """Merge defaults and user config in memory, including supported aliases."""
    defaults = read_json(defaults_path or DEFAULT_CONFIG_PATH)
    if not isinstance(defaults, dict):
        raise ConfigError("Default configuration is missing or invalid")

    if user_config_path is None:
        if kb_root is None:
            raise ConfigError("kb_root or user_config_path is required")
        user_config_path = knowledge_paths(kb_root)["config"]
    user = read_json(user_config_path, default={})
    if not isinstance(user, dict):
        raise ConfigError("User configuration must be a JSON object")

    effective = _deep_merge(defaults, user)
    memory_user = user.get("memory", {}) if isinstance(user.get("memory", {}), dict) else {}
    memory = effective.setdefault("memory", {})
    if not isinstance(memory.get("semantic_memory_enabled", True), bool):
        raise ConfigError("memory.semantic_memory_enabled must be true or false")
    if "hot_zone_size" not in memory_user and "hot_limit" in memory_user:
        memory["hot_zone_size"] = memory_user["hot_limit"]
    if "cold_zone_size" not in memory_user and "cold_limit" in memory_user:
        memory["cold_zone_size"] = memory_user["cold_limit"]
    memory["hot_limit"] = memory.get("hot_zone_size", 5)
    memory["cold_limit"] = memory.get("cold_zone_size", 45)

    persona = effective.setdefault("persona", {})
    persona.setdefault("default_persona", "feynman")
    persona.setdefault("language_mode", "global")
    if persona["language_mode"] not in ("global", "individual"):
        raise ConfigError("persona.language_mode must be global or individual")

    effective.setdefault("language", "zh")
    if not isinstance(effective["language"], str) or not effective["language"].strip():
        raise ConfigError("language must be a non-empty string")
    effective.setdefault("activation_mode", "contextual")
    if effective["activation_mode"] not in ("contextual", "always"):
        raise ConfigError("activation_mode must be contextual or always")

    knowledge = effective.setdefault("knowledge", {})
    cold_days = _positive_int(
        knowledge.get("cold_after_days_default", 90),
        "knowledge.cold_after_days_default",
        1,
        3650,
    )
    wake = _ratio(knowledge.get("wake_strength", 0.5), "knowledge.wake_strength")
    threshold = _ratio(
        knowledge.get("sleep_threshold", 0.1),
        "knowledge.sleep_threshold",
        allow_zero=False,
    )
    if threshold >= wake:
        raise ConfigError("knowledge.sleep_threshold must be below wake_strength")
    decay = (threshold / wake) ** (1.0 / cold_days)
    knowledge["cold_after_days_default"] = cold_days
    knowledge["strength_decay"] = decay
    knowledge["half_life_default"] = math.log(0.5) / math.log(decay)
    knowledge.setdefault("cold_warning_days", max(1, cold_days - 15))

    _positive_int(memory.get("hot_zone_size", 5), "memory.hot_zone_size", 1, 1000)
    _positive_int(memory.get("cold_zone_size", 45), "memory.cold_zone_size", 0, 10000)
    _positive_int(knowledge.get("top_k", 3), "knowledge.top_k", 1, 100)
    _positive_int(knowledge.get("min_pool", 10), "knowledge.min_pool", 1, 10000)

    return effective


def atomic_write_text(path, text, encoding="utf-8"):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if Path(temp_name).read_text(encoding=encoding) != text:
            raise AlayaError("Temporary file verification failed: %s" % target)
        os.replace(temp_name, str(target))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path, value):
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verified_copy(source, destination):
    """Copy through a same-directory temporary file and verify before publish."""
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=destination.name + ".", suffix=".tmp", dir=str(destination.parent)
    )
    os.close(fd)
    try:
        shutil.copy2(str(source), temp_name)
        if source.stat().st_size != Path(temp_name).stat().st_size:
            raise AlayaError("Copied file size does not match source")
        if sha256_file(source) != sha256_file(temp_name):
            raise AlayaError("Copied file hash does not match source")
        os.replace(temp_name, str(destination))
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def commit_text_bundle(alaya_dir, operation_id, writes):
    """Commit validated text files with one small roll-forward journal."""
    alaya_dir = Path(alaya_dir).resolve()
    prepared = []
    for target, content in writes:
        target = Path(target).resolve()
        if not is_within(target, alaya_dir.parent):
            raise AlayaError("Bundle target is outside the knowledge base: %s" % target)
        if not isinstance(content, str):
            raise AlayaError("Bundle content must be text")
        prepared.append((target, content))

    journal = alaya_dir / ".commit_journal.json"
    state = {
        "operation_id": str(operation_id),
        "completed": [],
        "remaining": [str(target) for target, _ in prepared],
        "updated_at": int(time.time()),
    }
    atomic_write_json(journal, state)
    for target, content in prepared:
        atomic_write_text(target, content)
        state["completed"].append(str(target))
        state["remaining"].remove(str(target))
        state["updated_at"] = int(time.time())
        atomic_write_json(journal, state)
    try:
        journal.unlink()
    except FileNotFoundError:
        pass


def process_running(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


class FileLock(object):
    def __init__(self, path, stale_seconds=1800):
        self.path = Path(path)
        self.stale_seconds = stale_seconds
        self.acquired = False

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "created_at": int(time.time()),
        }
        for _ in range(2):
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                self.acquired = True
                return self
            except FileExistsError:
                existing = read_json(self.path, default={}) or {}
                age = time.time() - float(existing.get("created_at", time.time()))
                if age <= self.stale_seconds or process_running(existing.get("pid")):
                    raise AlayaError("Another Alaya operation holds lock: %s" % self.path)
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
        raise AlayaError("Could not acquire lock: %s" % self.path)

    def release(self):
        if self.acquired:
            try:
                current = read_json(self.path, default={}) or {}
                if current.get("pid") == os.getpid():
                    self.path.unlink()
            except FileNotFoundError:
                pass
            finally:
                self.acquired = False

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return False


configure_console()
