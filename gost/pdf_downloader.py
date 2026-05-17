from __future__ import annotations

from pathlib import Path

import httpx

from gost.exceptions import GostPdfDownloadError


class PdfDownloader:
    def __init__(
        self,
        *,
        download_dir: str | Path = "./data/gost_pdfs",
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._download_dir = Path(download_dir)
        self._timeout = timeout
        self._client = client

    def download(self, pdf_url: str, *, filename: str | None = None) -> Path:
        self._download_dir.mkdir(parents=True, exist_ok=True)
        name = filename or self._filename_from_url(pdf_url)
        target = self._download_dir / name

        if self._client is not None:
            response = self._client.get(pdf_url)
        else:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                response = client.get(pdf_url)

        if response.status_code != 200:
            raise GostPdfDownloadError(
                f"Failed to download PDF {pdf_url}: HTTP {response.status_code}"
            )
        if not response.content.startswith(b"%PDF"):
            raise GostPdfDownloadError(f"Downloaded file is not a PDF: {pdf_url}")

        target.write_bytes(response.content)
        return target

    @staticmethod
    def _filename_from_url(pdf_url: str) -> str:
        stem = Path(pdf_url.rstrip("/")).stem
        return f"{stem}.pdf"
