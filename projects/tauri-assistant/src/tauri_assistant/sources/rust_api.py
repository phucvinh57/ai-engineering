"""Fetch + parse the `tauri` crate's docs.rs rustdoc pages.

The crate root page links out to every public item via <a> tags inside
`.item-table` sections. One level of links reaches every struct/trait/enum/
fn/macro directly in the `tauri` namespace -- a struct's own methods are
already rendered inline on its page, so no further recursion is needed.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import httpx
import tenacity
from bs4 import BeautifulSoup
from markdownify import markdownify

BASE_URL = "https://docs.rs/tauri/latest/tauri/"
USER_AGENT = "tauri-assistant-bot/0.1 (+https://github.com/; educational RAG project)"
CONCURRENCY = 4
MAX_PAGES = 200

ITEM_LINK_RE = re.compile(r'href="((?:struct|enum|trait|fn|macro|mod)\.[^"#]+\.html)"')


class RustDocPage:
    def __init__(self, item: str, markdown: str, url: str):
        self.item = item  # e.g. "struct.Builder", or "tauri" for the crate root
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


def _extract_content(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    main = soup.find(id="main-content")
    if main is None:
        return ""
    junk = main.find_all(["nav", "script", "button"]) + main.find_all(
        class_=["rustdoc-breadcrumbs", "doc-anchor", "anchor"]
    )
    for elem in junk:
        elem.decompose()
    return markdownify(str(main), heading_style="ATX").strip()


def _fetch_page(rel_path: str) -> RustDocPage:
    url = urljoin(BASE_URL, rel_path)
    with httpx.Client(timeout=30.0) as client:
        html = _fetch(client, url)
    return RustDocPage(item=rel_path.removesuffix(".html"), markdown=_extract_content(html), url=url)


def fetch_rust_api_pages() -> list[RustDocPage]:
    with httpx.Client(timeout=30.0) as client:
        root_html = _fetch(client, BASE_URL)

    rel_paths = sorted(set(ITEM_LINK_RE.findall(root_html)))[:MAX_PAGES]
    pages = [RustDocPage(item="tauri", markdown=_extract_content(root_html), url=BASE_URL)]

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for page in pool.map(_fetch_page, rel_paths):
            if page.markdown:
                pages.append(page)
    return pages
