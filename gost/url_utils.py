from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

STROYINF_BASE = "https://files.stroyinf.ru"

_INDEX_RE = re.compile(
    r"/Index/(?P<folder>\d+)/(?P<doc_id>\d+)\.htm(?:l)?$",
    re.IGNORECASE,
)


def normalize_index_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    path = parsed.path or ""
    if not _INDEX_RE.search(path):
        raise ValueError(
            "Expected stroyinf index URL like "
            "https://files.stroyinf.ru/Index/73/73932.htm"
        )
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def extract_doc_id(url: str) -> int:
    match = _INDEX_RE.search(urlparse(url).path)
    if not match:
        raise ValueError(f"Cannot extract document id from URL: {url}")
    return int(match.group("doc_id"))


def build_pdf_url(doc_id: int, *, base: str = STROYINF_BASE) -> str:
    folder = doc_id // 100
    return f"{base}/Data/{folder}/{doc_id}.pdf"


def resolve_pdf_url(html: str, index_url: str) -> str:
    match = re.search(
        r'href=["\'](?P<path>/Data/\d+/\d+\.pdf)["\']',
        html,
        re.IGNORECASE,
    )
    if match:
        return urljoin(index_url, match.group("path"))
    doc_id = extract_doc_id(index_url)
    return build_pdf_url(doc_id)
