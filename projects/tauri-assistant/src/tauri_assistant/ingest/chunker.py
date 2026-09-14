"""Turn parsed sources into embeddable chunks.

JS API symbols and plugin permissions each get one chunk per symbol/
permission; guide and Rust API markdown get one chunk per leaf heading
section. Any of these gets subdivided only when it's unusually large. Every
chunk carries a breadcrumb prefix so it reads standalone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import tiktoken

from tauri_assistant.config import Settings
from tauri_assistant.sources.js_api import JsApiSymbol
from tauri_assistant.sources.manifest import content_hash
from tauri_assistant.sources.permissions import PluginPermission

_ENCODING = tiktoken.get_encoding("cl100k_base")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class Chunk:
    text: str
    source: str
    heading_path: str = ""
    url: str = ""
    chunk_index: int = 0
    content_hash: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.content_hash = content_hash(self.text)


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _split_paragraphs_by_tokens(
    paragraphs: list[str], max_tokens: int, overlap_tokens: int
) -> list[str]:
    """Greedily pack paragraphs into windows <= max_tokens, with token overlap."""
    windows: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para)
        if current and current_tokens + para_tokens > max_tokens:
            windows.append("\n\n".join(current))
            overlap: list[str] = []
            overlap_count = 0
            for prev in reversed(current):
                prev_tokens = count_tokens(prev)
                if overlap_count + prev_tokens > overlap_tokens:
                    break
                overlap.insert(0, prev)
                overlap_count += prev_tokens
            current = overlap
            current_tokens = overlap_count
        current.append(para)
        current_tokens += para_tokens

    if current:
        windows.append("\n\n".join(current))
    return windows or ["\n\n".join(paragraphs)]


def _split_text_by_tokens(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return [text] if text.strip() else []
    return _split_paragraphs_by_tokens(paragraphs, max_tokens, overlap_tokens)


def _chunk_body(breadcrumb: str, body: str, source: str, url: str, settings: Settings) -> list[Chunk]:
    full_text = f"{breadcrumb}\n\n{body}"
    if count_tokens(full_text) <= settings.chunk_max_tokens:
        return [Chunk(text=full_text, source=source, heading_path=breadcrumb, url=url, chunk_index=0)]

    windows = _split_text_by_tokens(body, settings.chunk_max_tokens, settings.chunk_overlap_tokens)
    return [
        Chunk(
            text=f"{breadcrumb} (part {i + 1}/{len(windows)})\n\n{window}",
            source=source,
            heading_path=breadcrumb,
            url=url,
            chunk_index=i,
        )
        for i, window in enumerate(windows)
    ]


def chunk_js_symbol(symbol: JsApiSymbol, url: str, settings: Settings) -> list[Chunk]:
    breadcrumb = f"@tauri-apps/api > {symbol.module} > {symbol.name}"
    body = "\n\n".join(part for part in (symbol.doc, f"```ts\n{symbol.source}\n```") if part)
    return _chunk_body(breadcrumb, body, "js-api", url, settings)


def chunk_permission(perm: PluginPermission, settings: Settings) -> list[Chunk]:
    breadcrumb = f"{perm.plugin} plugin > permissions > {perm.identifier}"
    return _chunk_body(breadcrumb, perm.render_text(), "permissions", perm.url, settings)


@dataclass
class _Section:
    heading_path: list[str]
    body_lines: list[str]


def _parse_markdown_sections(markdown: str) -> list[_Section]:
    sections: list[_Section] = []
    stack: list[tuple[int, str]] = []
    current = _Section(heading_path=[], body_lines=[])

    def flush() -> None:
        if any(line.strip() for line in current.body_lines):
            sections.append(_Section(heading_path=list(current.heading_path), body_lines=current.body_lines))

    for line in markdown.splitlines():
        match = HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current = _Section(heading_path=[t for _, t in stack], body_lines=[])
        else:
            current.body_lines.append(line)

    flush()
    return sections


def chunk_markdown(
    root_label: str,
    url: str,
    source: str,
    markdown: str,
    settings: Settings,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in _parse_markdown_sections(markdown):
        heading_path = " > ".join([root_label, *section.heading_path])
        body = "\n".join(section.body_lines).strip()
        if not body:
            continue
        chunks.extend(_chunk_body(heading_path, body, source, url, settings))
    return chunks
