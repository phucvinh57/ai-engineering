"""The `Chunker` base class and the markdown primitives strategies share."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass


_HEADING = re.compile(r"^(#{1,6})\s+(\S.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")


@dataclass(frozen=True, slots=True)
class Section:
    """A heading and the body beneath it, with its ancestor headings."""

    path: tuple[str, ...]
    """Heading trail within the document, outermost first."""

    text: str
    level: int


def iter_lines_outside_fences(text: str) -> Iterator[tuple[str, bool]]:
    """Yield `(line, inside_fence)`.

    Markdown headings and `#` comments in shell/Python code are spelled the
    same way, so every structural scan has to know which fence it is in. Only
    a fence closed by the same marker that opened it ends the block, so a
    ```` ``` ```` nested inside a ```` ~~~ ```` block does not terminate it.
    """
    fence: str | None = None
    for line in text.splitlines():
        match = _FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker[0]
                yield line, True
                continue
            if marker[0] == fence:
                fence = None
                yield line, True
                continue
        yield line, fence is not None


def split_sections(text: str, min_level: int = 2, max_level: int = 4) -> list[Section]:
    """Split markdown on headings, tracking the enclosing heading trail.

    Content before the first heading becomes a section with an empty path, so
    a page's intro paragraph is never dropped.
    """
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    buffer: list[str] = []
    current: tuple[tuple[str, ...], int] = ((), 0)

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append(Section(path=current[0], text=body, level=current[1]))

    for line, in_fence in iter_lines_outside_fences(text):
        heading = None if in_fence else _HEADING.match(line)
        if heading and min_level <= len(heading.group(1)) <= max_level:
            flush()
            # Keep the heading line in the body: if two sections are later
            # merged, the second one's title has to survive somewhere.
            buffer = [line]
            level = len(heading.group(1))
            title = heading.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current = (tuple(t for _, t in stack), level)
        else:
            buffer.append(line)

    flush()
    return sections
