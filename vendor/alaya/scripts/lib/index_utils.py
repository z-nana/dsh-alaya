"""Shared generated-block parsing for current and legacy Alaya indexes."""

import re


CURRENT_NAMES = ("AUTO (base)", "AUTO (refined)", "MANUAL")


def _same_marker(name):
    return "<!-- %s -->" % name


def block_status(content, name):
    """Return current, legacy, missing or unpaired for a generated block."""
    marker = _same_marker(name)
    count = content.count(marker)
    if name == "MANUAL" and content.count("<!-- END-MANUAL -->"):
        return "legacy" if count == 1 and content.count("<!-- END-MANUAL -->") == 1 else "unpaired"
    if count == 2:
        return "current"
    if count:
        return "unpaired"
    if name == "AUTO (base)":
        starts = content.count("<!-- AUTO -->")
        ends = content.count("<!-- END-AUTO -->")
        if starts == 1 and ends == 1:
            return "legacy"
        if starts or ends:
            return "unpaired"
    return "missing"


def paired_block(content, name):
    marker = _same_marker(name)
    first = content.find(marker)
    if first >= 0:
        second = content.find(marker, first + len(marker))
        legacy_end = content.find("<!-- END-MANUAL -->", first + len(marker)) if name == "MANUAL" else -1
        if legacy_end >= 0 and (second < 0 or legacy_end < second):
            return content[first + len(marker):legacy_end].strip()
        if second >= 0:
            return content[first + len(marker):second].strip()
        return ""
    if name == "AUTO (base)":
        start = "<!-- AUTO -->"
        end = "<!-- END-AUTO -->"
        first = content.find(start)
        second = content.find(end, first + len(start)) if first >= 0 else -1
        if first >= 0 and second >= 0:
            return content[first + len(start):second].strip()
    return ""


def all_paired_blocks(content, name):
    marker = _same_marker(name)
    blocks = []
    position = 0
    while True:
        first = content.find(marker, position)
        if first < 0:
            break
        second = content.find(marker, first + len(marker))
        if name == "MANUAL":
            end = "<!-- END-MANUAL -->"
            legacy_end = content.find(end, first + len(marker))
            if legacy_end >= 0 and (second < 0 or legacy_end < second):
                blocks.append(content[first + len(marker):legacy_end].strip())
                position = legacy_end + len(end)
                continue
        if second < 0:
            break
        blocks.append(content[first + len(marker):second].strip())
        position = second + len(marker)
    return blocks


def block(name, body):
    marker = _same_marker(name)
    return "%s\n%s\n%s" % (marker, body.strip(), marker)


def outside_generated_blocks(content):
    """Return explicit prose outside generated blocks, without the first H1."""
    cleaned = content
    for name in CURRENT_NAMES:
        marker = re.escape(_same_marker(name))
        cleaned = re.sub(marker + r".*?" + marker, "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"<!-- MANUAL -->.*?<!-- END-MANUAL -->", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"<!-- AUTO -->.*?<!-- END-AUTO -->", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\A\s*#\s+[^\r\n]+\r?\n", "", cleaned, count=1)
    return cleaned.strip()
