"""Parse the @tauri-apps/api TypeScript source (with JSDoc) from a local clone
of the tauri-apps/tauri repo, one record per top-level exported symbol.

The source is prettier-formatted, so every top-level declaration starts at
column 0 and everything indented under it (class members, etc.) belongs to
it -- that's enough to segment a file without a real TS parser. Some modules
declare things bare and export them all in one block at the end of the file
(`export { listen, emit }`) instead of inline (`export function listen`), so
both forms need to be recognized.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

API_SRC_SUBDIR = "packages/api/src"
SKIP_FILES = {"index.ts", "tauri.ts"}  # pure re-export barrels

DECL_RE = re.compile(
    r"^(?P<export>export\s+)?(?:default\s+)?(?:declare\s+)?"
    r"(?P<kind>async function|function|abstract class|class|interface|const enum|enum|type|const|let|var)\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)"
)
BOTTOM_EXPORT_RE = re.compile(
    r"^export\s+(?:type\s+)?\{([^}]*)\}(\s*from\s+['\"][^'\"]+['\"])?", re.MULTILINE
)
DOC_LINE_RE = re.compile(r"^\s*\*\s?")


@dataclass
class JsApiSymbol:
    module: str  # e.g. "event", or "menu/menuItem" for nested files
    kind: str
    name: str
    doc: str
    source: str


def _clean_doc(doc_lines: list[str]) -> str:
    text = "\n".join(doc_lines).strip()
    text = text.removeprefix("/**").removesuffix("*/")
    lines = [DOC_LINE_RE.sub("", line) for line in text.splitlines()]
    return "\n".join(lines).strip()


def _leading_doc(lines: list[str], before: int) -> str:
    """Find a /** ... */ block immediately above `before`, skipping blank lines."""
    i = before - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    if i < 0 or not lines[i].strip().endswith("*/"):
        return ""
    end = i
    while i >= 0 and "/**" not in lines[i]:
        i -= 1
    if i < 0:
        return ""
    return _clean_doc(lines[i : end + 1])


def _bottom_exported_names(text: str) -> set[str]:
    """Names re-exported via a trailing `export { a, b }` / `export type { a, b }`.

    Skips `export { a, b } from "./other"`, which re-exports another module's
    symbols rather than naming a local declaration.
    """
    names: set[str] = set()
    for match in BOTTOM_EXPORT_RE.finditer(text):
        if match.group(2):
            continue
        for item in match.group(1).split(","):
            name = item.strip().split(" as ")[0].strip()
            if name:
                names.add(name)
    return names


def parse_api_file(path: Path, src_dir: Path) -> list[JsApiSymbol]:
    module = path.relative_to(src_dir).with_suffix("").as_posix()
    text = path.read_text()
    lines = text.splitlines()
    bottom_exports = _bottom_exported_names(text)

    starts = [i for i, line in enumerate(lines) if DECL_RE.match(line)]
    symbols: list[JsApiSymbol] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        match = DECL_RE.match(lines[start])
        name = match["name"]
        if not match["export"] and name not in bottom_exports:
            continue  # not part of the module's public API

        doc = _leading_doc(lines, start)
        source = "\n".join(lines[start:end]).strip()
        symbols.append(JsApiSymbol(module=module, kind=match["kind"], name=name, doc=doc, source=source))
    return symbols


def list_api_files(tauri_repo_dir: Path) -> list[Path]:
    src_dir = tauri_repo_dir / API_SRC_SUBDIR
    return sorted(
        p for p in src_dir.rglob("*.ts") if p.name not in SKIP_FILES and not p.name.endswith(".test.ts")
    )
