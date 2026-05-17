from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from gost.exceptions import GostMetadataError, GostPageFetchError
from gost.models import GostMetadata, NormativeReference
from gost.url_utils import STROYINF_BASE, normalize_index_url, resolve_pdf_url

_LABEL_MAP = {
    "обозначение:": "designation",
    "статус:": "status",
    "название рус.:": "title_ru",
    "название англ.:": "title_en",
    "дата актуализации текста:": "text_updated_at",
    "дата актуализации описания:": "description_updated_at",
    "дата издания:": "published_at",
    "дата введения:": "effective_from",
    "взамен:": "replaces",
    "область применения:": "scope",
    "расположен в:": "classification_path",
}

_REF_SPLIT_RE = re.compile(r"\s*;\s*")


class MetadataScraper:
    def __init__(self, *, timeout: float = 30.0, client: httpx.Client | None = None) -> None:
        self._timeout = timeout
        self._client = client

    def fetch(self, index_url: str) -> tuple[GostMetadata, list[NormativeReference], str]:
        url = normalize_index_url(index_url)
        html = self._get_html(url)
        metadata, index_refs = self._parse_html(url, html)
        metadata.pdf_url = resolve_pdf_url(html, url)
        return metadata, index_refs, html

    def _get_html(self, url: str) -> str:
        if self._client is not None:
            response = self._client.get(url, follow_redirects=True)
        else:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                response = client.get(url)
        if response.status_code != 200:
            raise GostPageFetchError(f"Failed to fetch {url}: HTTP {response.status_code}")
        return response.text

    def _parse_html(
        self, source_url: str, html: str
    ) -> tuple[GostMetadata, list[NormativeReference]]:
        soup = BeautifulSoup(html, "lxml")
        rows = self._extract_metadata_rows(soup)
        if not rows:
            raise GostMetadataError("Metadata table not found on index page")

        fields: dict[str, str] = {}
        normative_refs: list[NormativeReference] = []
        extra: dict[str, str] = {}

        for label, cell in rows:
            key = _LABEL_MAP.get(label.lower())
            if key == "classification_path":
                fields[key] = self._parse_classification(cell)
                continue
            if label.lower() == "нормативные ссылки:":
                normative_refs = self._parse_normative_references(cell)
                continue
            value = cell.get_text(" ", strip=True)
            if key:
                fields[key] = value
            else:
                extra[label.rstrip(":")] = value

        designation = fields.get("designation")
        if not designation:
            raise GostMetadataError("Document designation not found on index page")

        metadata = GostMetadata(
            source_url=source_url,
            designation=designation,
            status=fields.get("status"),
            title_ru=fields.get("title_ru"),
            title_en=fields.get("title_en"),
            text_updated_at=fields.get("text_updated_at"),
            description_updated_at=fields.get("description_updated_at"),
            published_at=fields.get("published_at"),
            effective_from=fields.get("effective_from"),
            replaces=fields.get("replaces"),
            scope=fields.get("scope"),
            classification_path=self._split_classification(fields.get("classification_path", "")),
            extra=extra,
        )
        return metadata, normative_refs

    @staticmethod
    def _extract_metadata_rows(soup: BeautifulSoup) -> list[tuple[str, object]]:
        for table in soup.find_all("table"):
            rows: list[tuple[str, object]] = []
            for tr in table.find_all("tr"):
                cells = tr.find_all(["td", "th"])
                if len(cells) != 2:
                    continue
                label = cells[0].get_text(" ", strip=True)
                if label.lower() in _LABEL_MAP or label.lower() == "нормативные ссылки:":
                    rows.append((label, cells[1]))
            if rows:
                return rows
        return []

    @staticmethod
    def _parse_classification(cell) -> str:
        parts = [a.get_text(" ", strip=True) for a in cell.find_all("a")]
        if parts:
            return " > ".join(parts)
        return cell.get_text(" ", strip=True)

    @staticmethod
    def _split_classification(value: str) -> list[str]:
        if not value:
            return []
        if " > " in value:
            return [p.strip() for p in value.split(" > ") if p.strip()]
        return [value.strip()] if value.strip() else []

    @staticmethod
    def _parse_normative_references(cell) -> list[NormativeReference]:
        refs: list[NormativeReference] = []
        for anchor in cell.find_all("a"):
            designation = anchor.get_text(" ", strip=True)
            href = anchor.get("href")
            url = urljoin(STROYINF_BASE, href) if href else None
            if designation:
                refs.append(NormativeReference(designation=designation, source_url=url))

        plain = cell.get_text(" ", strip=True)
        linked = {r.designation for r in refs}
        for chunk in _REF_SPLIT_RE.split(plain):
            chunk = chunk.strip()
            if chunk and chunk not in linked:
                refs.append(NormativeReference(designation=chunk))
        return refs
