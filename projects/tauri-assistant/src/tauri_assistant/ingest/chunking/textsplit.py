"""Fence-aware text splitting, shared by the fixed strategy and SplitOversized.

The corpus is mostly prose wrapped around Rust/TS/shell examples, and a code
block severed from the sentence that introduces it retrieves badly for both
halves. So fences are atomic units here: the packer moves whole fences between
pieces and only ever cuts *inside* one when a single fence exceeds the budget
on its own -- and then it repeats the opening info string so the language tag
survives into every part.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tauri_assistant.ingest.chunking.base import _FENCE, iter_lines_outside_fences
from tauri_assistant.ingest.chunking.tokens import TokenCounter

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z`\[])")


@dataclass(frozen=True, slots=True)
class Block:
    text: str
    is_fence: bool


def split_blocks(text: str) -> list[Block]:
    """Break text into fence blocks and the prose runs between them."""
    blocks: list[Block] = []
    buffer: list[str] = []
    in_fence = False

    for line, inside in iter_lines_outside_fences(text):
        starting = inside and not in_fence
        ending = in_fence and inside and _FENCE.match(line)

        if starting:
            if buffer:
                blocks.append(Block("\n".join(buffer), is_fence=False))
            buffer = [line]
            in_fence = True
            continue

        buffer.append(line)
        if ending:
            blocks.append(Block("\n".join(buffer), is_fence=True))
            buffer = []
            in_fence = False

    if buffer:
        blocks.append(Block("\n".join(buffer), is_fence=in_fence))
    return [b for b in blocks if b.text.strip()]


def _fence_info(fence_text: str) -> str:
    """The opening line of a fence, e.g. ```` ```rust title="lib.rs" ````."""
    first = fence_text.splitlines()[0] if fence_text else "```"
    return first if _FENCE.match(first) else "```"


def _split_fence(fence_text: str, counter: TokenCounter, budget: int) -> list[str]:
    """Cut a single oversized fence, repeating its info string on each part."""
    lines = fence_text.splitlines()
    info = _fence_info(fence_text)
    opening = _FENCE.match(info)
    closing = opening.group(1) if opening else "```"

    body = lines[1:]
    if body and _FENCE.match(body[-1]):
        body = body[:-1]

    parts: list[str] = []
    current: list[str] = []
    for line in body:
        candidate = "\n".join([info, *current, line, closing])
        if current and counter.count(candidate) > budget:
            parts.append("\n".join([info, *current, closing]))
            current = [line]
        else:
            current.append(line)
    if current:
        parts.append("\n".join([info, *current, closing]))
    return parts or [fence_text]


def _split_prose(text: str, counter: TokenCounter, budget: int) -> list[str]:
    """Cascade paragraph -> sentence -> line until every part fits."""
    for separator, joiner in (("\n\n", "\n\n"), (None, " "), ("\n", "\n")):
        pieces = _SENTENCE_END.split(text) if separator is None else text.split(separator)
        if len(pieces) < 2:
            continue

        parts: list[str] = []
        current: list[str] = []
        for piece in pieces:
            candidate = joiner.join([*current, piece])
            if current and counter.count(candidate) > budget:
                parts.append(joiner.join(current))
                current = [piece]
            else:
                current.append(piece)
        if current:
            parts.append(joiner.join(current))

        if all(counter.count(p) <= budget for p in parts):
            return [p for p in parts if p.strip()]

    # Nothing separable left: hard-cut on whitespace so we never emit a piece
    # the embedding model would silently truncate.
    words = text.split()
    parts, current = [], []
    for word in words:
        if current and counter.count(" ".join([*current, word])) > budget:
            parts.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        parts.append(" ".join(current))
    return [p for p in parts if p.strip()]


def _force_fit(pieces: list[str], counter: TokenCounter, budget: int) -> list[str]:
    """Last resort: chop by character for atoms no separator can break.

    Real content hits this -- `updater.mdx` contains a 286-character run of
    `-` as a table rule, which is one whitespace-delimited "word" costing 286
    tokens. Without this the piece would go to the embedder and be silently
    truncated, which is exactly the failure this whole layer exists to
    prevent, so the guarantee has to hold for arbitrary input rather than
    well-formed prose.
    """
    out: list[str] = []
    for piece in pieces:
        if counter.count(piece) <= budget:
            out.append(piece)
            continue
        remaining = piece
        while remaining:
            low, high, best = 1, len(remaining), 1
            while low <= high:  # largest prefix that still fits
                mid = (low + high) // 2
                if counter.count(remaining[:mid]) <= budget:
                    best, low = mid, mid + 1
                else:
                    high = mid - 1
            out.append(remaining[:best])
            remaining = remaining[best:]
    return [p for p in out if p.strip()]


def pack_to_budget(text: str, counter: TokenCounter, budget: int) -> list[str]:
    """Split `text` into pieces of at most `budget` tokens, fences intact."""
    if counter.count(text) <= budget:
        return [text] if text.strip() else []

    pieces: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            joined = "\n\n".join(current).strip()
            if joined:
                pieces.append(joined)
            current.clear()

    for block in split_blocks(text):
        if counter.count(block.text) > budget:
            flush()
            splitter = _split_fence if block.is_fence else _split_prose
            pieces.extend(splitter(block.text, counter, budget))
            continue

        candidate = "\n\n".join([*current, block.text])
        if current and counter.count(candidate) > budget:
            flush()
        current.append(block.text)

    flush()
    return _force_fit(pieces, counter, budget)


def window_by_tokens(text: str, counter: TokenCounter, size: int, overlap: int) -> list[str]:
    """Fixed-size windows with overlap, snapped to line boundaries.

    The baseline strategy. It cuts through code fences by design -- that is
    precisely what the sweep is meant to measure against `heading`.
    """
    lines = text.splitlines()
    windows: list[str] = []
    start = 0

    while start < len(lines):
        current: list[str] = []
        end = start
        while end < len(lines):
            candidate = "\n".join([*current, lines[end]])
            if current and counter.count(candidate) > size:
                break
            current.append(lines[end])
            end += 1

        window = "\n".join(current).strip()
        if window:
            windows.extend(_force_fit([window], counter, size))
        if end >= len(lines):
            break

        # Step back far enough to carry ~`overlap` tokens into the next window.
        step_back = 0
        carried: list[str] = []
        while step_back < len(current):
            nxt = [current[-(step_back + 1)], *carried]
            if counter.count("\n".join(nxt)) > overlap:
                break
            carried = nxt
            step_back += 1
        start = max(end - step_back, start + 1)

    return windows
