"""Tauri's Astro Starlight guide pages.

The content is already Markdown, so there is no HTML to scrape -- but it is
MDX, so the JSX has to come out before chunking. Components that carry text
(`<Tabs>`, `<Steps>`, `<CommandTabs>`) are unwrapped to keep their content;
components that only render UI chrome (`<PluginLinks />`, `<Card>`) are
dropped along with the import statements that pull them in.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from fnmatch import fnmatch
from pathlib import Path

from loguru import logger

from tauri_assistant.ingest.chunking.base import iter_lines_outside_fences
from tauri_assistant.ingest.types import Document
from tauri_assistant.settings import ChunkingSettings, settings
from tauri_assistant.sources.base import Source

CONTENT_ROOT = "src/content/docs"
SITE = "https://v2.tauri.app"

# Full translations of the same pages -- including them roughly doubles the
# corpus with near-duplicate vectors that crowd out the English answers.
TRANSLATIONS = frozenset({"zh-cn", "ja", "es", "fr", "de", "it", "ko", "pt", "ru", "tr"})

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_FM_FIELD = re.compile(r"^(\w+)\s*:\s*(.*?)\s*$", re.MULTILINE)
_IMPORT = re.compile(r"^\s*import\s+.*$")
_EXPORT = re.compile(r"^\s*export\s+(?:const|let|var|default|function)\b.*$")

# Components whose children are prose worth keeping: drop the tags, keep the text.
_UNWRAP = (
    "Tabs",
    "TabItem",
    "Steps",
    "Card",
    "CardGrid",
    "Aside",
    "LinkCard",
    "Content",
    "ShowSolution",
    "LinkButton",
    "Search",
    "CommandTabs",
    "Tab",
)
_UNWRAP_TAG = re.compile(rf"</?(?:{'|'.join(_UNWRAP)})\b[^>]*/?>")

# A lone capitalized component tag on its own line renders UI chrome only.
_LONE_COMPONENT = re.compile(r"^\s*</?[A-Z]\w*\b[^>]*/?>\s*$")
_TAG_NAME = re.compile(r"^\s*</?([A-Z]\w*)\b")
_ANY_TAG = re.compile(r"</?[A-Z]\w*\b[^>]*/?>")
_ATTR = re.compile(r'(\w+)="([^"]*)"')

# Starlight directives: :::note[Title] ... ::: -> a blockquote heading.
_DIRECTIVE_OPEN = re.compile(r"^:::(note|tip|caution|danger|warning)(?:\[(.*?)\])?\s*$")
_DIRECTIVE_CLOSE = re.compile(r"^:::\s*$")

_BLANK_RUN = re.compile(r"\n{3,}")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text
    fields = {k: v.strip("'\"") for k, v in _FM_FIELD.findall(match.group(1))}
    return fields, text[match.end() :]


def _render_tag(name: str, tag: str, inner: str) -> str | None:
    """Turn one JSX tag into the prose or code it stands for, or drop it."""
    if name == "CommandTabs":
        # The install commands live in the attributes; they are exactly what
        # someone asking "how do I add the sql plugin" needs to retrieve.
        commands = [v for _, v in _ATTR.findall(tag) if v.strip()]
        if commands:
            body = "\n".join(dict.fromkeys(commands))
            return f"```sh\n{body}\n```"
        return None

    if name in ("LinkCard", "Card", "CardGrid", "LinkButton"):
        attrs = dict(_ATTR.findall(tag))
        parts = [attrs.get("title", ""), attrs.get("description", ""), inner]
        text = " -- ".join(p.strip() for p in parts if p and p.strip())
        return text or None

    if name in _UNWRAP:
        return inner.strip() or None

    return None


def strip_mdx(text: str) -> str:
    """Remove MDX machinery while leaving fenced code exactly as written.

    Fence awareness is the whole point: `windows-installer.mdx` embeds a WiX
    XML sample whose `<Fragment>` and `<DirectoryRef>` tags look identical to
    JSX, and `mobile-multiwindow.mdx` does the same with an Android manifest.
    Stripping by regex over the whole page would quietly gut those examples.
    """
    out: list[str] = []
    pending: list[str] = []  # a JSX tag spanning several lines

    for line, in_fence in iter_lines_outside_fences(text):
        if in_fence and not pending:
            out.append(line)
            continue

        if pending:
            pending.append(line)
            if ">" not in line:
                continue
            tag = "\n".join(pending)
            pending = []
            name = _TAG_NAME.match(tag)
            rendered = _render_tag(name.group(1), tag, "") if name else None
            if rendered:
                out.append(rendered)
            continue

        if _IMPORT.match(line) or _EXPORT.match(line):
            continue

        if directive := _DIRECTIVE_OPEN.match(line):
            label = (directive.group(2) or directive.group(1)).strip()
            out.append(f"> **{label[:1].upper()}{label[1:]}**")
            continue
        if _DIRECTIVE_CLOSE.match(line):
            continue

        opening = _TAG_NAME.match(line)
        if opening and ">" not in line:
            pending = [line]
            continue

        if opening or _LONE_COMPONENT.match(line):
            inner = _ANY_TAG.sub("", line).strip()
            name = opening.group(1) if opening else ""
            rendered = _render_tag(name, line, inner) if name else None
            if rendered:
                out.append(rendered)
            continue

        out.append(_UNWRAP_TAG.sub("", line))

    return _BLANK_RUN.sub("\n\n", "\n".join(out)).strip()


def page_url(rel_path: str) -> str:
    slug = re.sub(r"\.mdx?$", "", rel_path)
    slug = re.sub(r"/index$", "", slug)
    return f"{SITE}/{slug}/"


def _excluded(rel: str, cfg) -> bool:
    top = rel.split("/", 1)[0]
    if not cfg.include_translations and top in TRANSLATIONS:
        return True
    return any(fnmatch(rel, pattern) for pattern in cfg.exclude_globs)


class TauriDocsSource(Source):
    name = "tauri-docs"
    repo = "tauri-docs"
    strategy = "heading"

    def iter_documents(self, cfg: ChunkingSettings | None = None) -> Iterator[Document]:
        cfg = cfg or settings.chunking
        root = self.path / CONTENT_ROOT
        if not root.is_dir():
            logger.warning(f"{root} missing")
            return

        for path in sorted([*root.rglob("*.mdx"), *root.rglob("*.md")]):
            rel = path.relative_to(root).as_posix()
            if _excluded(rel, cfg):
                continue

            fields, body = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            text = strip_mdx(body)
            if not text:
                continue

            title = fields.get("title") or Path(rel).stem.replace("-", " ").title()
            trail = tuple(p.replace("-", " ").title() for p in Path(rel).parent.parts if p != ".")

            if description := fields.get("description"):
                text = f"{description}\n\n{text}"

            yield Document(
                id=f"{self.name}:{rel}",
                text=text,
                breadcrumb=("Tauri Docs", *trail, title),
                metadata={
                    "source": self.name,
                    "repo": self.repo,
                    "path": self.relative_path(path),
                    "url": page_url(rel),
                    "kind": "guide",
                },
            )
