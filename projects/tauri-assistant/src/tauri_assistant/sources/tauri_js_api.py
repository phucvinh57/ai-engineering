"""`@tauri-apps/api` TypeScript sources, one record per documented symbol.

Doc comments are paired with the declaration they document by walking the
real TypeScript AST (via `tree-sitter`) rather than guessing from
indentation: a JSDoc block is a documented symbol's previous sibling in the
tree, and "is this a class member" is answered by which node's `body` the
comment's parent is, not by counting leading spaces. That also means the
scope of "enclosing class" falls out of the recursion for free -- it cannot
leak past the class's closing brace the way a mutable, file-wide "last class
seen" variable can. Splitting classes into their methods matters --
`window.ts` alone is 2711 lines, and "how do I set the window title" should
retrieve `Window.setTitle`, not the whole class.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import tree_sitter_typescript as tsts
from loguru import logger
from tree_sitter import Language, Node, Parser

from tauri_assistant.ingest.types import Document
from tauri_assistant.sources.base import Source

API_ROOT = "packages/api/src"
SITE = "https://v2.tauri.app/reference/javascript"

_LANGUAGE = Language(tsts.language_typescript())

# Kinds a JSDoc block can document. Anything else (an `if`, a bare
# expression statement, an `import`) is never mistaken for one of these --
# the parser already told us what it is, so there is no keyword allowlist to
# maintain the way a regex would need.
_RELEVANT = frozenset(
    {
        "function_declaration",
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
        "type_alias_declaration",
        "lexical_declaration",
        "method_definition",
        "method_signature",
        "public_field_definition",
        "property_signature",
        "function_signature",
    }
)

_GUTTER = re.compile(r"^\s*\* ?")


def clean_jsdoc(body: str) -> str:
    """Strip the leading `*` gutter from a JSDoc block."""
    return "\n".join(_GUTTER.sub("", line) for line in body.splitlines()).strip()


@dataclass(frozen=True)
class Symbol:
    qualified: str
    signature: str
    doc: str


def _node_text(node: Node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode()


def _jsdoc_body(comment_text: str) -> str:
    inner = comment_text[2:-2] if comment_text.endswith("*/") else comment_text[2:]
    return clean_jsdoc(inner)


def _local_name(decl: Node, src: bytes) -> str | None:
    """The identifier a declaration binds, or None if it doesn't bind a plain one.

    `const { a, b } = ...` binds a destructuring pattern rather than a single
    name -- rare enough in this codebase that skipping it (like the old
    regex silently did, since its identifier pattern couldn't match a `{`)
    beats inventing a qualified name out of the pattern's source text.
    """
    if decl.type == "lexical_declaration":
        if not decl.named_children:
            return None
        name = decl.named_children[0].child_by_field_name("name")
        if name is None or name.type != "identifier":
            return None
    else:
        name = decl.child_by_field_name("name")
    return _node_text(name, src) if name is not None else None


def _unwrap_export(node: Node) -> Node:
    """`export function foo() {}` documents `foo`, not the `export` wrapper."""
    if node.type != "export_statement":
        return node
    for child in node.named_children:
        if child.type != "export_clause":
            return child
    return node


def _collect_exports(root: Node, src: bytes) -> set[str]:
    """Names re-exported via a trailing `export { a, b as c }` block.

    Most modules export at the bottom rather than inline: 9 of 14 files use
    `export { listen, emit }` instead of `export function listen`. The
    specifier's *first* child is always the locally declared name -- `emit as
    emitEvent` binds `emit` in this file -- so that is what has to match a
    declaration's own name, not the public alias.
    """
    names: set[str] = set()
    for child in root.named_children:
        if child.type != "export_statement":
            continue
        for clause in child.named_children:
            if clause.type != "export_clause":
                continue
            for spec in clause.named_children:
                if spec.type == "export_specifier" and spec.named_children:
                    names.add(_node_text(spec.named_children[0], src))
    return names


def _signature(following: Node, decl: Node, src: bytes) -> str:
    """The declaration header, without its body.

    Prettier breaks long signatures at the parameter list, so `listen`'s
    first line is just `async function listen<T>(` -- slicing at the body's
    start byte (whatever kind of body: a block, an enum's braces, an arrow
    function's block) keeps the wrapped parameters and drops everything the
    reader doesn't need, in one step instead of a line-by-paren-counting loop.
    """
    end = None
    body = decl.child_by_field_name("body")
    if body is not None:
        end = body.start_byte
    elif decl.type == "lexical_declaration" and decl.named_children:
        value = decl.named_children[0].child_by_field_name("value")
        if value is not None:
            end = (value.child_by_field_name("body") or value).start_byte
    if end is None:
        end = decl.end_byte

    text = src[following.start_byte : end].decode().rstrip()
    if text.endswith("{"):
        text = text[:-1].rstrip()
    return " ".join(line.strip() for line in text.splitlines()).strip()


def _symbols(children: list[Node], enclosing: str | None, exports: set[str], src: bytes) -> Iterator[Symbol]:
    for i, child in enumerate(children):
        if child.type != "comment" or not _node_text(child, src).startswith("/**"):
            continue

        j = i + 1
        while j < len(children) and children[j].type == "comment":
            j += 1
        if j >= len(children):
            continue

        following = children[j]
        decl = _unwrap_export(following)
        if decl.type not in _RELEVANT:
            continue

        doc = _jsdoc_body(_node_text(child, src))
        name = _local_name(decl, src)
        if not doc or not name:
            continue

        if enclosing is None:
            exported = following.type == "export_statement" or name in exports
            if not exported and not doc.startswith("The "):
                continue
            qualified = name
        else:
            qualified = f"{enclosing}.{name}"

        yield Symbol(qualified, _signature(following, decl, src), doc)

        if decl.type == "class_declaration":
            body = decl.child_by_field_name("body")
            if body is not None:
                yield from _symbols(body.named_children, name, exports, src)


def iter_symbols(text: str) -> Iterator[Symbol]:
    """Pair every JSDoc block in a module with the symbol it documents."""
    src = text.encode("utf-8", errors="replace")
    root = Parser(_LANGUAGE).parse(src).root_node
    yield from _symbols(root.named_children, None, _collect_exports(root, src), src)


class TauriJsApiSource(Source):
    name = "js-api"
    repo = "tauri"
    strategy = "record"

    def iter_documents(self) -> Iterator[Document]:
        root = self.path / API_ROOT
        if not root.is_dir():
            logger.warning(f"{root} missing")
            return

        for path in sorted(root.rglob("*.ts")):
            if path.name.endswith(".d.ts") or path.stem in ("mocks", "index"):
                continue
            yield from self._file_documents(path)

    def _file_documents(self, path: Path) -> Iterator[Document]:
        text = path.read_text(encoding="utf-8", errors="replace")
        module = path.stem

        for symbol in iter_symbols(text):
            yield Document(
                id=f"{self.name}:{module}/{symbol.qualified}",
                text=f"# {module}.{symbol.qualified}\n\n```ts\n{symbol.signature}\n```\n\n{symbol.doc}",
                breadcrumb=("@tauri-apps/api", module, symbol.qualified),
                metadata={
                    "source": self.name,
                    "repo": self.repo,
                    "path": self.relative_path(path),
                    "url": f"{SITE}/{module}/",
                    "kind": "js-symbol",
                    "module": module,
                },
            )
