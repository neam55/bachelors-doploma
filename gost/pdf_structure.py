from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import fitz

from gost.exceptions import GostPdfStructureError
from gost.models import GostDocumentStructure, StructureNode, TocEntry
from gost.normative_refs import extract_normative_references_from_section
from gost.pdf_links import extract_pdf_links

_TOC_LINE_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)*)\s+(?P<rest>.+)$")
_TOC_PAGE_RE = re.compile(r"\.{2,}\s*(?P<page>\d+)\s*$")
_APPENDIX_TOC_RE = re.compile(
    r"^Приложение\s+(?P<id>[А-ЯA-Z])\s*"
    r"(?:\((?P<kind>[^)]+)\))?\s*(?P<rest>.+)$",
    re.IGNORECASE,
)
_CLAUSE_HEADING_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)*)\s+(?P<rest>.+)$")
_APPENDIX_HEADING_RE = re.compile(
    r"^Приложение\s+(?P<id>[А-ЯA-Z])\s*"
    r"(?:\((?P<kind>[^)]+)\))?\s*(?P<title>.*)$",
    re.IGNORECASE,
)
_STOP_MARKERS = ("Библиография",)


@dataclass
class _Line:
    text: str
    page: int


class PdfStructureParser:
    def parse(self, pdf_path: str | Path) -> GostDocumentStructure:
        path = Path(pdf_path)
        if not path.is_file():
            raise GostPdfStructureError(f"PDF file not found: {path}")

        doc = fitz.open(path)
        try:
            lines = self._extract_lines(doc)
            full_text = "\n".join(line.text for line in lines)
            toc = self._parse_table_of_contents(full_text)
            sections, appendices = self._parse_hierarchy(lines)
            pdf_links = extract_pdf_links(doc)

            section_2 = next((s for s in sections if s.number == "2"), None)
            normative_refs = extract_normative_references_from_section(section_2)

            return GostDocumentStructure(
                page_count=doc.page_count,
                table_of_contents=toc,
                sections=sections,
                appendices=appendices,
                normative_references=normative_refs,
                pdf_links=pdf_links,
            )
        finally:
            doc.close()

    def _extract_lines(self, doc: fitz.Document) -> list[_Line]:
        lines: list[_Line] = []
        header_re = re.compile(r"^ГОСТ\s*Р?\s*[\d\.—\-]+", re.IGNORECASE)

        for page_index in range(doc.page_count):
            page_number = page_index + 1
            page = doc.load_page(page_index)
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (b[1], b[0]))

            for block in blocks:
                if block[6] != 0:
                    continue
                for raw in block[4].splitlines():
                    text = raw.strip()
                    if not text:
                        continue
                    if page_index > 0 and header_re.match(text) and len(text) < 40:
                        continue
                    lines.append(_Line(text=text, page=page_number))
        return lines

    def _parse_hierarchy(
        self, lines: list[_Line]
    ) -> tuple[list[StructureNode], list[StructureNode]]:
        body_start = self._find_body_start(lines)
        if body_start is None:
            return [], []

        sections: list[StructureNode] = []
        appendices: list[StructureNode] = []
        stack: list[StructureNode] = []
        current_appendix: StructureNode | None = None

        def append_text(target: StructureNode, line: str) -> None:
            if target.text:
                target.text += "\n" + line
            else:
                target.text = line

        def active_node() -> StructureNode | None:
            if current_appendix is not None:
                return current_appendix
            return stack[-1] if stack else None

        for line in lines[body_start:]:
            if any(line.text.startswith(marker) for marker in _STOP_MARKERS):
                break

            appendix_match = _APPENDIX_HEADING_RE.match(line.text)
            if appendix_match and not self._is_toc_like(line.text):
                stack = []
                kind = appendix_match.group("kind")
                title = appendix_match.group("title").strip() or line.text
                if kind:
                    title = f"({kind}) {title}".strip()
                current_appendix = StructureNode(
                    kind="appendix",
                    number=f"Приложение {appendix_match.group('id')}",
                    title=title,
                    page_start=line.page,
                    text=line.text,
                )
                appendices.append(current_appendix)
                continue

            clause_match = _CLAUSE_HEADING_RE.match(line.text)
            if clause_match and not self._is_toc_like(line.text):
                if current_appendix is not None:
                    append_text(current_appendix, line.text)
                    continue

                number = clause_match.group("number")
                rest = clause_match.group("rest").strip()
                title = self._strip_page_leaders(rest)
                if not title or not self._is_valid_heading(number, title):
                    node = active_node()
                    if node is not None:
                        append_text(node, line.text)
                    continue
                depth = number.count(".")
                if depth > 0 and not self._belongs_to_current_tree(number, stack):
                    node = active_node()
                    if node is not None:
                        append_text(node, line.text)
                    continue
                kind = (
                    "section"
                    if depth == 0
                    else "clause"
                    if depth == 1
                    else "subclause"
                )
                node = StructureNode(
                    kind=kind,
                    number=number,
                    title=title,
                    page_start=line.page,
                    text=line.text,
                )

                if depth == 0:
                    sections.append(node)
                    stack = [node]
                else:
                    while len(stack) > depth:
                        stack.pop()
                    if not stack:
                        sections.append(node)
                        stack = [node]
                    else:
                        parent_index = min(depth - 1, len(stack) - 1)
                        stack[parent_index].children.append(node)
                        if len(stack) >= depth:
                            stack = stack[:depth] + [node]
                        else:
                            stack = stack + [node]
                continue

            node = active_node()
            if node is not None and line.text != node.text:
                append_text(node, line.text)

        return sections, appendices

    @staticmethod
    def _find_body_start(lines: list[_Line]) -> int | None:
        seen_contents = False
        for i, line in enumerate(lines):
            if line.text.strip() == "Содержание":
                seen_contents = True
                continue
            if not seen_contents:
                continue
            match = _CLAUSE_HEADING_RE.match(line.text)
            if match and match.group("number") == "1" and not PdfStructureParser._is_toc_like(
                line.text
            ):
                return i
        return None

    @staticmethod
    def _is_toc_like(line: str) -> bool:
        return ".." in line or _TOC_PAGE_RE.search(line) is not None

    @staticmethod
    def _strip_page_leaders(rest: str) -> str:
        cleaned = _TOC_PAGE_RE.sub("", rest).strip(" .\t")
        return cleaned

    @staticmethod
    def _belongs_to_current_tree(number: str, stack: list[StructureNode]) -> bool:
        if not stack:
            return True
        root = stack[0].number
        return number == root or number.startswith(f"{root}.")

    @staticmethod
    def _is_valid_heading(number: str, title: str) -> bool:
        depth = number.count(".")
        if depth == 0 and number not in {"1", "2", "3", "4", "5", "6"}:
            return False
        if re.fullmatch(r"[\d\s.]+", title):
            return False
        if len(title) < 3:
            return False
        if not re.match(r"[А-ЯЁA-Z0-9«(]", title):
            return False
        return True

    def _parse_table_of_contents(self, full_text: str) -> list[TocEntry]:
        lines = full_text.splitlines()
        start_idx = next(
            (i + 1 for i, line in enumerate(lines) if line.strip() == "Содержание"),
            None,
        )
        if start_idx is None:
            return []

        entries: list[TocEntry] = []
        idx = start_idx
        while idx < len(lines):
            stripped = lines[idx].strip()
            idx += 1
            if not stripped:
                continue
            if "Библиография" in stripped:
                break

            if entries and self._is_body_heading_line(
                stripped, lookahead=lines[idx : idx + 2]
            ):
                break

            is_toc_line = self._line_looks_like_toc(stripped, lines[idx : idx + 2])

            appendix_match = _APPENDIX_TOC_RE.match(stripped)
            if appendix_match and is_toc_line:
                title, page = self._parse_toc_rest(appendix_match.group("rest"))
                kind = appendix_match.group("kind")
                if kind:
                    title = f"({kind}) {title}"
                entries.append(
                    TocEntry(
                        number=f"Приложение {appendix_match.group('id')}",
                        title=title,
                        page=page,
                    )
                )
                continue

            section_match = _TOC_LINE_RE.match(stripped)
            if section_match and is_toc_line:
                title, page = self._parse_toc_rest(section_match.group("rest"))
                entries.append(
                    TocEntry(
                        number=section_match.group("number"),
                        title=title,
                        page=page,
                    )
                )
                continue

            if entries and not stripped[0].isdigit():
                if "НАЦИОНАЛЬНЫЙ" in stripped or "Standardization in" in stripped:
                    break
                prev = entries[-1]
                extra_title, extra_page = self._parse_toc_rest(stripped)
                prev.title = f"{prev.title} {extra_title}".strip()
                if prev.page is None:
                    prev.page = extra_page

        return entries

    @staticmethod
    def _line_looks_like_toc(line: str, lookahead: list[str]) -> bool:
        if ".." in line or _TOC_PAGE_RE.search(line):
            return True
        window = " ".join([line, *(ln.strip() for ln in lookahead)])
        return ".." in window or _TOC_PAGE_RE.search(window) is not None

    @staticmethod
    def _is_body_heading_line(line: str, *, lookahead: list[str]) -> bool:
        if PdfStructureParser._line_looks_like_toc(line, lookahead):
            return False
        return (
            _CLAUSE_HEADING_RE.match(line) is not None
            or _APPENDIX_HEADING_RE.match(line) is not None
        )

    @staticmethod
    def _parse_toc_rest(rest: str) -> tuple[str, int | None]:
        page_match = _TOC_PAGE_RE.search(rest)
        if page_match:
            title = rest[: page_match.start()].strip(" .\t")
            return title, int(page_match.group("page"))
        trailing_page = re.search(r"(?<!\d)(\d+)\s*$", rest)
        if trailing_page and len(trailing_page.group(1)) <= 3:
            title = rest[: trailing_page.start()].strip(" .\t")
            return title, int(trailing_page.group(1))
        return rest.strip(" .\t"), None
