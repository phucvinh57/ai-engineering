"""Fetch + parse the Wayland Book (DocBook-derived HTML at wayland.freedesktop.org).

Appendix A (protocol spec) is skipped: it's generated from the same XML
already parsed in protocol_xml.py. What's left is the short preface (tier 1)
and Appendix B/C, the client/server C API reference (tier 2).
"""

from __future__ import annotations

import httpx
import tenacity
from bs4 import BeautifulSoup
from markdownify import markdownify

BASE_URL = "https://wayland.freedesktop.org/docs/html/"
USER_AGENT = "wayland-assistant-bot/0.1 (+https://github.com/; educational RAG project)"

# (page, title, tier) -- apa.html (protocol spec) intentionally omitted:
# it's generated from the same XML already parsed in protocol_xml.py.
PAGES = [
    ("pr01.html", "Preface", 1),
    ("apb.html", "Appendix B. Client API", 2),
    ("apc.html", "Appendix C. Server API", 2),
]


class BookPage:
    def __init__(self, page: str, title: str, markdown: str, url: str):
        self.page = page
        self.title = title
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
    for junk in soup.find_all(class_=["navheader", "navfooter"]):
        junk.decompose()
    body = soup.find("body") or soup
    return markdownify(str(body), heading_style="ATX").strip()


def fetch_book_pages(tier: int = 1) -> list[BookPage]:
    pages: list[BookPage] = []
    with httpx.Client(timeout=30.0) as client:
        for page, title, page_tier in PAGES:
            if page_tier > tier:
                continue
            url = BASE_URL + page
            html = _fetch(client, url)
            markdown = _extract_content(html)
            pages.append(BookPage(page=page, title=title, markdown=markdown, url=url))
    return pages
