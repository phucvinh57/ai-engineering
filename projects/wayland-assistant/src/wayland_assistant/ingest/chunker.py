"""Turn parsed sources into embeddable chunks.

Protocol XML gets one chunk per interface (its requests/events/enums belong
together), subdivided only when an interface is unusually large. Book/Doxygen
markdown gets one chunk per leaf heading section, subdivided the same way.
Every chunk carries a breadcrumb prefix so it reads standalone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import tiktoken

from wayland_assistant.config import Settings
from wayland_assistant.sources.manifest import content_hash
from wayland_assistant.sources.protocol_xml import InterfaceDoc

_ENCODING = tiktoken.get_encoding("cl100k_base")

MATURITY_LABELS = {
    "core": "wayland core protocol",
    "stable": "wayland-protocols/stable",
    "staging": "wayland-protocols/staging",
    "unstable": "wayland-protocols/unstable",
    "experimental": "wayland-protocols/experimental",
    "wlr": "wlr-protocols/unstable",
}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class Chunk:
    text: str
    source: str
    protocol_name: str = ""
    interface_name: str = ""
    version: str = ""
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


def chunk_interface(doc: InterfaceDoc, settings: Settings) -> list[Chunk]:
    label = MATURITY_LABELS.get(doc.maturity, doc.maturity)
    breadcrumb = f"{label} > {doc.protocol_name} > {doc.interface_name}"
    body = doc.render_text()
    full_text = f"{breadcrumb}\n\n{body}"

    if count_tokens(full_text) <= settings.chunk_max_tokens:
        return [
            Chunk(
                text=full_text,
                source=doc.maturity,
                protocol_name=doc.protocol_name,
                interface_name=doc.interface_name,
                version=doc.version,
                heading_path=breadcrumb,
                url=doc.url,
                chunk_index=0,
            )
        ]

    windows = _split_text_by_tokens(body, settings.chunk_max_tokens, settings.chunk_overlap_tokens)
    return [
        Chunk(
            text=f"{breadcrumb} (part {i + 1}/{len(windows)})\n\n{window}",
            source=doc.maturity,
            protocol_name=doc.protocol_name,
            interface_name=doc.interface_name,
            version=doc.version,
            heading_path=breadcrumb,
            url=doc.url,
            chunk_index=i,
        )
        for i, window in enumerate(windows)
    ]


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
    sections = _parse_markdown_sections(markdown)
    chunks: list[Chunk] = []

    for section in sections:
        heading_path = " > ".join([root_label, *section.heading_path])
        body = "\n".join(section.body_lines).strip()
        if not body:
            continue
        full_text = f"{heading_path}\n\n{body}"

        if count_tokens(full_text) <= settings.chunk_max_tokens:
            chunks.append(
                Chunk(
                    text=full_text,
                    source=source,
                    heading_path=heading_path,
                    url=url,
                    chunk_index=0,
                )
            )
            continue

        windows = _split_text_by_tokens(body, settings.chunk_max_tokens, settings.chunk_overlap_tokens)
        for i, window in enumerate(windows):
            chunks.append(
                Chunk(
                    text=f"{heading_path} (part {i + 1}/{len(windows)})\n\n{window}",
                    source=source,
                    heading_path=heading_path,
                    url=url,
                    chunk_index=i,
                )
            )

    return chunks
