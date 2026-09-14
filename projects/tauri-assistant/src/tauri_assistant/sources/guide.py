"""Read the Tauri docs guide pages (Markdown/MDX) from a local clone of tauri-docs.

The content is already Markdown -- no HTML to scrape, just MDX frontmatter/
imports/JSX to strip out, same spirit as protocol_xml.py reading structured
data directly instead of scraping a rendered page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CONTENT_SUBDIR = "src/content/docs"
LOCALE_DIRS = {"de", "es", "fr", "ja", "zh-cn"}

FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
FRONTMATTER_TITLE_RE = re.compile(r"^title:\s*(.+)$", re.MULTILINE)
IMPORT_RE = re.compile(r"^import .*$\n?", re.MULTILINE)
JSX_TAG_RE = re.compile(r"</?[A-Z][A-Za-z0-9.]*(?:\s[^>]*)?/?>")


@dataclass
class GuidePage:
    rel_path: str  # e.g. "start/prerequisites.mdx"
    title: str
    markdown: str
    url: str


def _frontmatter_title(raw: str) -> str | None:
    match = FRONTMATTER_RE.match(raw)
    if not match:
        return None
    title_match = FRONTMATTER_TITLE_RE.search(match.group(0))
    if not title_match:
        return None
    return title_match.group(1).strip().strip("\"'")


def _strip_mdx(raw: str) -> str:
    text = FRONTMATTER_RE.sub("", raw, count=1)
    text = IMPORT_RE.sub("", text)
    text = JSX_TAG_RE.sub("", text)
    return text.strip()


def _page_url(rel_path: Path) -> str:
    slug = rel_path.with_suffix("").as_posix().removesuffix("/index")
    return f"https://tauri.app/{slug}/"


def list_guide_pages(docs_repo_dir: Path) -> list[GuidePage]:
    content_dir = docs_repo_dir / CONTENT_SUBDIR
    pages: list[GuidePage] = []
    for path in sorted(content_dir.rglob("*")):
        if not path.is_file() or path.suffix not in (".md", ".mdx"):
            continue
        rel = path.relative_to(content_dir)
        if rel.parts[0] in LOCALE_DIRS or rel.parts[:2] == ("reference", "acl"):
            continue

        raw = path.read_text()
        markdown = _strip_mdx(raw)
        if not markdown:
            continue

        title = _frontmatter_title(raw) or path.stem
        pages.append(GuidePage(rel_path=str(rel), title=title, markdown=markdown, url=_page_url(rel)))
    return pages
