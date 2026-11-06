# Alaya · Format Converter 
# Standard-library text conversion plus optional PDF extraction.
# Handles MD/TXT natively; PDF script import requires PyMuPDF.
# Unsupported formats return None with Agent guidance template.

import os, sys

AGENT_TEMPLATE = """\
Unsupported format detected: {filename}

Agent: Please read this file and generate a high-quality Alaya knowledge card using the LLM General Template:

---
title: "(document title)"
seed_type: REFINED
created_by: llm_import
strength: 0.6
last_activated: {date}
activation_count: 0
description: "一句话描述文件核心内容"
source_path: "{file_path}"
source_type: {source_type}
tags: ["tag1", "tag2", "tag3"]
created: {date}
updated: {date}
---

# (Title)

## 核心内容 / Core Content
[3-5段概括文件核心内容 / 3-5 paragraphs summarizing core content]
- 主要主题 / Main topics
- 关键观点 / Key points
- 重要细节 / Important details

## 关键概念 / Key Concepts
- **概念一**：[说明 / Concept 1: description]
- **概念二**：[说明 / Concept 2: description]
- **概念三**：[说明 / Concept 3: description]

## 价值与应用 / Value and Applications
[文件内容的价值和应用场景 / Value and application scenarios]

## 相关链接 / Related Links
- [[相关概念1]] / [[Related Concept 1]]
- [[相关概念2]] / [[Related Concept 2]]

## 原始文件 / Original File
[📄 打开原始文件 / Open original file](file:///{file_path})

Save to: wiki/{{category}}/{{slug}}.md
Then run: python scripts/build_index.py --category {{category}}
"""


def detect_format(filepath):
    """Return format type string or None for unsupported formats."""
    ext = os.path.splitext(filepath)[1].lower()
    formats = {
        '.md': 'markdown',
        '.markdown': 'markdown',
        '.txt': 'text',
        '.rst': 'text',
        '.py': 'text',
        '.js': 'text',
        '.ts': 'text',
        '.tsx': 'text',
        '.jsx': 'text',
        '.json': 'text',
        '.yaml': 'text',
        '.yml': 'text',
        '.toml': 'text',
        '.csv': 'text',
        '.log': 'text',
        '.pdf': 'pdf',
    }
    return formats.get(ext)


def pdf_available():
    """Return whether the optional PDF extraction dependency is installed."""
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def extract_text(filepath, max_chars=None):
    """Extract text content from file. Returns str or None.

    When max_chars is None (default), reads the entire file.
    When set to a positive integer, limits extraction and prints a warning to stderr if truncated.
    """
    fmt = detect_format(filepath)
    if fmt in ('markdown', 'text'):
        text = _read_direct(filepath, max_chars)
    elif fmt == 'pdf':
        text = _read_pdf(filepath, max_chars)
    else:
        text = None

    if text is not None and max_chars is not None and len(text) >= max_chars:
        print(f"Warning: Content truncated at {max_chars} characters. "
              f"Increase the configured extraction preview limit when needed.",
              file=sys.stderr)
    return text


def extract_metadata(filepath):
    """Try to extract document metadata. Returns dict with available fields."""
    fmt = detect_format(filepath)
    meta = {
        'title': os.path.splitext(os.path.basename(filepath))[0],
        'source': filepath,
    }
    if fmt == 'pdf':
        return _pdf_metadata(filepath, meta)
    return meta


def get_agent_template(filepath, date_str=''):
    """Return Agent guidance template for unsupported formats."""
    from datetime import datetime
    fname = os.path.basename(filepath)
    slug, ext = os.path.splitext(fname)
    slug = slug.lower().replace(' ', '-')
    ext = ext.lstrip('.')
    fmt = detect_format(filepath)
    source_type = fmt if fmt else ext
    return AGENT_TEMPLATE.format(
        filename=fname,
        date=date_str or datetime.now().strftime('%Y-%m-%d'),
        slug=slug,
        ext=ext,
        source_type=source_type,
        file_path=os.path.abspath(filepath).replace('\\', '/'),
    )


def _read_direct(filepath, max_chars):
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            return f.read(max_chars) if max_chars is not None else f.read()
    except (UnicodeDecodeError, IOError):
        try:
            with open(filepath, 'r', encoding='gbk') as f:
                return f.read(max_chars) if max_chars is not None else f.read()
        except (UnicodeDecodeError, IOError):
            return None


def _read_pdf(filepath, max_chars):
    try:
        import fitz
    except ImportError:
        return None
    try:
        doc = fitz.open(filepath)
        text_parts = []
        total = 0
        for page in doc:
            t = page.get_text()
            text_parts.append(t)
            total += len(t)
            if max_chars is not None and total >= max_chars:
                break
        doc.close()
        full = '\n'.join(text_parts)
        return full if max_chars is None else full[:max_chars]
    except Exception:
        return None


def _pdf_metadata(filepath, meta):
    try:
        import fitz
        doc = fitz.open(filepath)
        pdf_meta = doc.metadata or {}
        if pdf_meta.get('title'):
            meta['title'] = pdf_meta['title']
        if pdf_meta.get('author'):
            meta['author'] = pdf_meta['author']
        doc.close()
    except (ImportError, Exception):
        pass
    return meta
