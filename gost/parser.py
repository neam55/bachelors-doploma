from __future__ import annotations

from pathlib import Path

import httpx

from gost.document_links import extract_document_links
from gost.breadcrumbs import assign_breadcrumbs
from gost.page_ranges import assign_page_ends
from gost.toc_sync import apply_toc_to_structure
from gost.metadata_scraper import MetadataScraper
from gost.models import NormativeReference, ParsedGost
from gost.normative_refs import merge_normative_references
from gost.pdf_downloader import PdfDownloader
from gost.pdf_structure import PdfStructureParser
from gost.url_utils import extract_doc_id


class GostParser:
    """Parse GOST documents from files.stroyinf.ru index pages."""

    def __init__(
        self,
        *,
        download_dir: str | Path = "./data/gost_pdfs",
        http_timeout: float = 30.0,
        pdf_timeout: float = 120.0,
    ) -> None:
        self._download_dir = Path(download_dir)
        self._http_timeout = http_timeout
        self._pdf_timeout = pdf_timeout

    def parse(
        self,
        index_url: str,
        *,
        pdf_path: str | Path | None = None,
        skip_download: bool = False,
    ) -> ParsedGost:
        with httpx.Client(
            timeout=self._http_timeout,
            follow_redirects=True,
        ) as client:
            metadata, index_refs, _html = MetadataScraper(client=client).fetch(index_url)

            if pdf_path is not None:
                resolved_pdf = Path(pdf_path)
            elif skip_download:
                doc_id = extract_doc_id(index_url)
                resolved_pdf = self._download_dir / f"{doc_id}.pdf"
                if not resolved_pdf.is_file():
                    raise FileNotFoundError(
                        f"PDF not found at {resolved_pdf}; disable skip_download or pass pdf_path"
                    )
            else:
                if not metadata.pdf_url:
                    raise ValueError("PDF URL was not resolved from metadata page")
                resolved_pdf = PdfDownloader(
                    download_dir=self._download_dir,
                    timeout=self._pdf_timeout,
                    client=client,
                ).download(
                    metadata.pdf_url,
                    filename=f"{extract_doc_id(index_url)}.pdf",
                )

        structure = PdfStructureParser().parse(resolved_pdf)
        apply_toc_to_structure(structure, structure.table_of_contents)
        assign_page_ends(structure)
        assign_breadcrumbs(structure, metadata.designation)
        structure.normative_references = merge_normative_references(
            index_refs,
            structure.normative_references,
        )
        structure.document_links = extract_document_links(structure)

        return ParsedGost(
            metadata=metadata,
            pdf_path=resolved_pdf,
            structure=structure,
            index_normative_references=index_refs,
        )
