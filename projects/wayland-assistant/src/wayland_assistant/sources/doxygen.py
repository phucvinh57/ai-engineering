"""Fetch + parse the wlroots Doxygen-generated API docs.

One page per public header (wlr/types/wlr_cursor.h.html, ...), each page's
<main> holds an h2 page title and one h3 section per struct/function -- that
maps directly onto heading-aware markdown chunking, same as the Book.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

import httpx
import tenacity
from bs4 import BeautifulSoup
from markdownify import markdownify

BASE_URL = "https://wlroots.pages.freedesktop.org/wlroots/"
USER_AGENT = "wayland-assistant-bot/0.1 (+https://github.com/; educational RAG project)"
CONCURRENCY = 4

HEADER_LINK_RE = re.compile(r'href="(wlr/[^"]+\.h\.html)"')


class DoxygenPage:
    def __init__(self, header: str, markdown: str, url: str):
        self.header = header  # e.g. "wlr/types/wlr_cursor.h"
        self.markdown = markdown
        self.url = url


@tenacity.retry(
    retry=tenacity.retry_if_exception_type(httpx.HTTPStatusError),
    wait=tenacity.wait_exponential(multiplier=1, min=2, max=30),
    stop=tenacity.stop_after_attempt(5),
)
def _fetch(client: httpx.Client, url: str) -> str:
    resp = client.get(url, headers={"User-Agent": USER_AGENT})
    if resp.status_code in (429, 500, 502, 503, 504):
        resp.raise_for_status()
    resp.raise_for_status()
    return resp.text


def _list_header_pages(client: httpx.Client) -> list[str]:
    html = _fetch(client, BASE_URL)
    return sorted(set(HEADER_LINK_RE.findall(html)))


def _extract_content(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main")
    if main is None:
        return ""
    return markdownify(str(main), heading_style="ATX").strip()


def _fetch_page(base_url: str, rel_path: str) -> DoxygenPage:
    url = base_url + rel_path
    with httpx.Client(timeout=30.0) as client:
        html = _fetch(client, url)
    markdown = _extract_content(html)
    header = rel_path.removesuffix(".html")
    return DoxygenPage(header=header, markdown=markdown, url=url)


def fetch_doxygen_pages() -> list[DoxygenPage]:
    """Fetch every wlroots header page (Tier 2 only, gated by the caller)."""
    with httpx.Client(timeout=30.0) as client:
        rel_paths = _list_header_pages(client)

    pages: list[DoxygenPage] = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(_fetch_page, BASE_URL, rel) for rel in rel_paths]
        for future in futures:
            pages.append(future.result())
    return pages
