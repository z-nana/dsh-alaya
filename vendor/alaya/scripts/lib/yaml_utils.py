"""Strict frontmatter, card identity and naming helpers for Alaya."""

import json
import os
import re
from pathlib import Path


METADATA_DEFAULTS = {
    "seed_type": "REFINED",
    "created_by": "system",
    "strength": "0.5",
    "activation_count": "0",
}

FRONTMATTER_RE = re.compile(
    r"\A(?:\ufeff)?---[ \t]*\r?\n(?P<yaml>.*?)(?P<close>\r?\n---[ \t]*(?:\r?\n|\Z))",
    re.DOTALL,
)
BACKUP_SUFFIXES = (".bak.md", ".backup.md", ".tmp.md", ".orig.md")


def split_frontmatter(content):
    """Return (yaml, body, closing_delimiter_offset) for strict line delimiters."""
    match = FRONTMATTER_RE.match(content)
    if not match:
        return None
    close_start = match.start("close") + len(match.group("close").split("---", 1)[0])
    return match.group("yaml"), content[match.end():], close_start


def read_frontmatter(filepath):
    path = Path(filepath)
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8-sig")
    result = split_frontmatter(content)
    if not result:
        return None
    yaml_str, _body, dash = result
    return content, yaml_str, dash


def yaml_quote(value):
    """Emit a JSON string, which is a safe YAML double-quoted scalar."""
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def get_field(yaml_str, field):
    match = re.search(r"^%s:\s*(.*?)\s*$" % re.escape(field), yaml_str, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
        if value[0] == "\"":
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                pass
        return value[1:-1]
    return value


def get_field_float(yaml_str, field):
    value = get_field(yaml_str, field)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def set_field(yaml_str, field, value):
    replacement = "%s: %s" % (field, value)
    pattern = re.compile(r"^%s:\s*.*$" % re.escape(field), re.MULTILINE)
    if pattern.search(yaml_str):
        return pattern.sub(lambda _match: replacement, yaml_str, count=1)
    return yaml_str.rstrip() + "\n" + replacement + "\n"


def remove_field(yaml_str, field):
    pattern = re.compile(r"^%s:\s*.*(?:\r?\n|\Z)" % re.escape(field), re.MULTILINE)
    return pattern.sub("", yaml_str, count=1)


def set_string_field(yaml_str, field, value):
    return set_field(yaml_str, field, yaml_quote(value))


def inject_metadata(yaml_str, overrides=None):
    defaults = dict(METADATA_DEFAULTS)
    if overrides:
        defaults.update(overrides)
    result = yaml_str
    for key, value in defaults.items():
        if get_field(result, key) is None:
            result = set_field(result, key, value)
    return result


def rebuild_content(yaml_str, dash_pos, original):
    """Rebuild using the original closing delimiter and body."""
    return "---\n" + yaml_str.strip("\r\n") + "\n" + original[dash_pos:]


def extract_title(yaml_str, fallback=""):
    return get_field(yaml_str, "title") or fallback


def slugify(name):
    value = str(name or "").lower().strip()
    value = re.sub(r"[：，。、（）\[\]{}]", "-", value)
    value = re.sub(r"[\\/:*?\"<>|]", "-", value)
    value = re.sub(r"[\s_]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-. ")
    if value.lower() in ("", ".", "..", "con", "prn", "aux", "nul"):
        return "untitled"
    if re.match(r"^(com|lpt)[1-9]$", value, re.IGNORECASE):
        value = "item-" + value
    return value


def safe_persona_key(name):
    raw = str(name or "").strip()
    if not raw or any(value in raw for value in ("/", "\\", "\x00")) or raw in (".", ".."):
        raise ValueError("Persona name contains an unsafe path component")
    key = slugify(name).replace("-", "_")
    if key in ("", ".", ".."):
        raise ValueError("Persona name does not produce a safe key")
    return key


def persona_key(manas_dir, name):
    if not name:
        return name
    directory = Path(manas_dir)
    lookup = str(name).lower()
    normalized = lookup.replace(" ", "_").replace("'", "")
    if directory.is_dir():
        for path in directory.glob("*.json"):
            key = path.stem
            if key.lower() in (lookup, normalized):
                return key
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                continue
            display = str(data.get("persona", ""))
            display_zh = str(data.get("persona_zh", ""))
            if display.lower().replace(" ", "_").replace("'", "") == normalized:
                return key
            if display_zh == name:
                return key
    return normalized


def is_category_file(fname):
    return Path(fname).name.endswith("_category.md")


def category_file_for(cat_slug):
    return "%s_category.md" % cat_slug


def is_knowledge_card(path_or_name):
    path = Path(path_or_name)
    name = path.name
    lower = name.lower()
    if not lower.endswith(".md") or name.startswith((".", "~$")):
        return False
    if lower in ("index.md", "_index.md", "log.md", "readme.md") or is_category_file(name):
        return False
    if any(lower.endswith(suffix) for suffix in BACKUP_SUFFIXES):
        return False
    if path.is_file():
        try:
            return read_frontmatter(path) is not None
        except (OSError, UnicodeError):
            return False
    return True


def get_all_cards(wiki_dir):
    root = Path(wiki_dir)
    cards = []
    if not root.is_dir():
        return cards
    for category in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not category.is_dir() or category.name.startswith("."):
            continue
        for path in sorted(category.glob("*.md"), key=lambda item: item.name.casefold()):
            if is_knowledge_card(path):
                cards.append((category.name, path.stem, str(path)))
    return cards


def build_card_index(wiki_dir):
    by_identity = {}
    by_name = {}
    for category, name, path in get_all_cards(wiki_dir):
        identity = "%s/%s" % (category, name)
        by_identity[identity.casefold()] = path
        by_name.setdefault(name.casefold(), []).append(path)
    return {"by_identity": by_identity, "by_name": by_name}


def find_cards(wiki_dir, card_name, category=None):
    index = build_card_index(wiki_dir)
    clean = str(card_name).replace("\\", "/").strip("/")
    if category:
        target = index["by_identity"].get((str(category) + "/" + clean).casefold())
        return [target] if target else []
    if "/" in clean:
        target = index["by_identity"].get(clean.casefold())
        return [target] if target else []
    return list(index["by_name"].get(clean.casefold(), []))


def find_card(wiki_dir, card_name, category=None):
    matches = find_cards(wiki_dir, card_name, category=category)
    return matches[0] if len(matches) == 1 else None


def get_description(yaml_str):
    return get_field(yaml_str, "description")


def description_issue(yaml_str):
    """Classify a description problem without rewriting the user's text."""
    match = re.search(r"^description:\s*(.*?)\s*$", yaml_str, re.MULTILINE)
    if not match:
        return "missing"
    raw = match.group(1)
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            return "encoding"
    elif raw.startswith("'"):
        if len(raw) < 2 or not raw.endswith("'"):
            return "encoding"
        value = raw[1:-1].replace("''", "'")
    else:
        if any(token in raw for token in (": ", " #", "\t")) or raw.startswith(("- ", "? ", "{", "[")):
            return "encoding"
        value = raw
    if any(token in value for token in ("\ufffd", "锟斤拷", "[待填写]", "TODO", "TBD")):
        return "content"
    return None


def set_description(yaml_str, description):
    return set_string_field(yaml_str, "description", description)


def _truncate_to_sentence(text, max_length):
    if len(text) <= max_length:
        return text
    positions = [text.rfind(mark, 0, max_length) for mark in "。！？.!?"]
    position = max(positions)
    if position > max_length * 0.6:
        return text[: position + 1]
    return text[:max_length]


def extract_description_from_body(body_text, max_length=200):
    lines = body_text.splitlines()
    for heading in (r"Abstract", r"摘要", r"TL;?DR", r"概要"):
        match = re.search(
            r"^#{1,4}\s*%s\s*$\r?\n+(.+?)(?:\r?\n\s*\r?\n|\r?\n#|\Z)" % heading,
            body_text,
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        if match:
            value = " ".join(line.strip() for line in match.group(1).splitlines() if line.strip())
            if len(value) > 10:
                return _truncate_to_sentence(value, max_length)
    paragraph = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if paragraph:
                value = " ".join(paragraph)
                if len(value) > 10:
                    return _truncate_to_sentence(value, max_length)
                paragraph = []
            continue
        if stripped.startswith("> "):
            stripped = stripped[2:].strip()
        paragraph.append(stripped)
    value = " ".join(paragraph)
    return _truncate_to_sentence(value, max_length) if len(value) > 10 else ""


def get_tags(yaml_str):
    value = get_field(yaml_str, "tags")
    if value is None:
        return []
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value.replace("'", "\""))
            return [str(item) for item in parsed]
        except ValueError:
            return [item.strip(" \"'") for item in value[1:-1].split(",") if item.strip()]
    return [value]


def discover_related_cards(wiki_dir, card_text, source_category=None, min_match_length=4, max_links=10):
    results = []
    normalized_text = card_text.casefold().replace("-", " ")
    for category, name, _path in get_all_cards(wiki_dir):
        if source_category and category == source_category:
            continue
        normalized_name = name.casefold().replace("-", " ")
        if len(normalized_name) >= min_match_length and normalized_name in normalized_text:
            position = normalized_text.find(normalized_name)
            context = card_text[max(0, position - 50): position + len(name) + 50].replace("\n", " ")
            results.append((category, name, context.strip()))
    results.sort(key=lambda item: len(item[1]), reverse=True)
    return results[:max_links]
