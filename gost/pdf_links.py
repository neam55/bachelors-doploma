from __future__ import annotations

import re
from urllib.parse import urlparse

import fitz

from gost.models import LinkSource, PdfLink

_URL_RE = re.compile(
    r"https?://[^\s\]\)>,;\"']+|www\.[^\s\]\)>,;\"']+",
    re.IGNORECASE,
)


def _normalize_url(raw: str) -> str:
    url = raw.strip().rstrip(".,;)")
    if url.endswith("#"):
        url = url.rstrip("#")
    if url.lower().startswith("www."):
        url = "https://" + url
    return url


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)


def extract_pdf_links(doc: fitz.Document) -> list[PdfLink]:
    by_key: dict[tuple[str, int], LinkSource] = {}

    def add(url: str, page: int, source: LinkSource) -> None:
        normalized = _normalize_url(url)
        if not _is_valid_url(normalized):
            return
        key = (normalized, page)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = source
            return
        if existing == "text" and source == "annotation":
            by_key[key] = "annotation"

    for page_index in range(doc.page_count):
        page_number = page_index + 1
        page = doc.load_page(page_index)

        for link in page.get_links():
            uri = link.get("uri")
            if uri:
                add(uri, page_number, "annotation")

        text = page.get_text("text")
        for match in _URL_RE.finditer(text):
            add(match.group(0), page_number, "text")

    links = [
        PdfLink(url=url, page=page, source=source)
        for (url, page), source in sorted(by_key.items(), key=lambda x: (x[0][1], x[0][0]))
    ]
    return links
