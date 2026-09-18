"""Rust doc comments from the `tauri` workspace crates.

There is no pure-Python Rust parser worth the dependency, but rustfmt makes
the shape predictable: a run of `///` lines immediately precedes the item it
documents, with any `#[attribute]` lines in between. That is enough to pair
10,577 doc comments with their signatures without parsing Rust properly.
`//!` runs document the enclosing module and become one record per file.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from loguru import logger

from tauri_assistant.ingest.types import Document
from tauri_assistant.settings import ChunkingSettings
from tauri_assistant.sources.base import Source

CRATES_ROOT = "crates"
SITE = "https://docs.rs"

# Crates that document the public API people actually call. The CLI and
# bundler are build tooling; their internals answer few user questions and
# would dominate the corpus by volume.
CRATES = ("tauri", "tauri-utils", "tauri-runtime", "tauri-plugin", "tauri-build", "tauri-macros")

_DOC_LINE = re.compile(r"^\s*///\s?(.*)$")
_MODULE_DOC = re.compile(r"^\s*//!\s?(.*)$")
_ATTRIBUTE = re.compile(r"^\s*#\[")
_ITEM = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?"
    r"(?P<kind>fn|struct|trait|enum|type|const|mod|impl|macro_rules!)\s+"
    r"(?P<name>[A-Za-z_]\w*)"
)
_UNSAFE_ASYNC = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:unsafe\s+|async\s+|extern\s+\S+\s+)+")
# `impl<R: Runtime> Trait for Type<R>` -- the type is what qualifies the
# methods inside, and without it every `fn new` in a file collides.
_IMPL = re.compile(r"^impl(?:<[^>]*>)?\s+(?:(?P<trait>[\w:]+)(?:<[^>]*>)?\s+for\s+)?(?P<type>[\w:]+)")


class TauriRustSource(Source):
    name = "rust-api"
    repo = "tauri"
    strategy = "record"

    def iter_documents(self, cfg: ChunkingSettings | None = None) -> Iterator[Document]:
        # No per-source filtering knobs -- `cfg` only matters to tauri-docs.
        root = self.path / CRATES_ROOT
        if not root.is_dir():
            logger.warning(f"{root} missing -- run `tauri-assistant sync` first")
            return

        for crate in CRATES:
            crate_src = root / crate / "src"
            if not crate_src.is_dir():
                continue
            for path in sorted(crate_src.rglob("*.rs")):
                yield from self._file_documents(crate, path)

    def _file_documents(self, crate: str, path: Path) -> Iterator[Document]:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        module = path.relative_to(self.path / CRATES_ROOT / crate / "src").as_posix()
        module = re.sub(r"(?:/mod)?\.rs$", "", module).replace("/", "::")

        module_doc: list[str] = []
        pending: list[str] = []
        impl_type: str | None = None

        for line in lines:
            if impl := _IMPL.match(line):
                impl_type = impl.group("type")
            elif line.startswith("}"):
                impl_type = None

            if header := _MODULE_DOC.match(line):
                module_doc.append(header.group(1))
                continue

            if doc := _DOC_LINE.match(line):
                pending.append(doc.group(1))
                continue

            if not pending:
                continue
            if _ATTRIBUTE.match(line) or not line.strip():
                continue  # attributes sit between the doc block and the item

            item = _ITEM.match(_UNSAFE_ASYNC.sub("", line))
            if item and (
                document := self._item_document(crate, module, path, item, line, pending, impl_type)
            ):
                yield document
            pending = []

        if module_doc and (text := "\n".join(module_doc).strip()):
            yield self._document(
                crate, module, path, module or "crate", f"# {crate}::{module}\n\n{text}", "module"
            )

    def _item_document(
        self,
        crate: str,
        module: str,
        path: Path,
        item: re.Match,
        line: str,
        doc: list[str],
        impl_type: str | None = None,
    ) -> Document | None:
        body = "\n".join(doc).strip()
        if not body:
            return None

        name = item.group("name")
        kind = item.group("kind")
        signature = line.strip().rstrip("{").strip()
        owner = impl_type if impl_type and kind == "fn" else None
        parts = [p for p in (module, owner, name) if p]
        qualified = "::".join(parts)
        text = f"# {crate}::{qualified}\n\n```rust\n{signature}\n```\n\n{body}"
        return self._document(crate, module, path, name, text, kind, qualified)

    def _document(
        self,
        crate: str,
        module: str,
        path: Path,
        name: str,
        text: str,
        kind: str,
        qualified: str | None = None,
    ) -> Document:
        qualified = qualified or name
        return Document(
            id=f"{self.name}:{crate}/{qualified}",
            text=text,
            breadcrumb=(crate, *(qualified.split("::") if qualified else (name,))),
            metadata={
                "source": self.name,
                "repo": self.repo,
                "path": self.relative_path(path),
                "url": f"{SITE}/{crate}/latest/{crate.replace('-', '_')}/",
                "kind": f"rust-{kind}",
                "crate": crate,
            },
        )
