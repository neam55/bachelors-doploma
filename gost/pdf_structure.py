from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import fitz

from gost.exceptions import GostPdfStructureError
from gost.models import GostDocumentStructure, StructureNode, TocEntry
from gost.normative_refs import extract_normative_references_from_section
from gost.pdf_links import extract_pdf_links
from gost.text_normalize import merge_lines, normalize_block, normalize_line, normalize_title

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

@dataclass
class _BLine:
    text: str
    page: int
    x0: float
    x1: float
    y0: float
    y1: float


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

            page_lines = self._extract_page_lines_with_bbox(page, page_number)
            page_lines = self._merge_broken_lines_by_bbox(page_lines, page.rect.width)

            for item in page_lines:
                text = normalize_line(item.text)
                if not text:
                    continue
                if page_index > 0 and header_re.match(text) and len(text) < 40:
                    continue
                lines.append(_Line(text=text, page=page_number))

        return lines

    def _extract_page_lines_with_bbox(self, page: fitz.Page, page_number: int) -> list[_BLine]:
        data = page.get_text("dict", sort=True)
        result: list[_BLine] = []

        for block in data["blocks"]:
            if block.get("type", 0) != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(span.get("text", "") for span in spans).strip()
                if not text:
                    continue
                x0, y0, x1, y1 = line["bbox"]
                result.append(_BLine(text=text, page=page_number, x0=x0, x1=x1, y0=y0, y1=y1))

        result.sort(key=lambda ln: (ln.y0, ln.x0))
        return result

    def _merge_broken_lines_by_bbox(
        self,
        lines: list[_BLine],
        page_width: float,
    ) -> list[_BLine]:
        """
        Склеивает:
        1. Переносы между PDF-строками:
            основопо
            лагающих

        2. OCR/PDF-разрывы внутри строки:
            стандар тов -> стандартов
            информа ции -> информации
        """

        if not lines:
            return lines

        merged: list[_BLine] = []
        i = 0

        while i < len(lines):
            cur = lines[i]

            # -----------------------------
            # FIX 1: чистим разрывы внутри строки
            # -----------------------------
            cur_text = self._fix_inner_word_breaks(cur.text)

            cur = _BLine(
                text=cur_text,
                page=cur.page,
                x0=cur.x0,
                x1=cur.x1,
                y0=cur.y0,
                y1=cur.y1,
            )

            if i + 1 < len(lines):
                nxt = lines[i + 1]

                nxt_text = self._fix_inner_word_breaks(nxt.text)

                nxt = _BLine(
                    text=nxt_text,
                    page=nxt.page,
                    x0=nxt.x0,
                    x1=nxt.x1,
                    y0=nxt.y0,
                    y1=nxt.y1,
                )

                # -----------------------------
                # Геометрия строк
                # -----------------------------
                y_gap = nxt.y0 - cur.y1

                same_paragraph = 0 <= y_gap < 12

                same_column = abs(nxt.x0 - cur.x0) < page_width * 0.15

                ends_at_right_edge = cur.x1 > page_width * 0.78

                starts_lowercase = (
                    bool(nxt.text)
                    and nxt.text[0].islower()
                )

                ends_with_word = (
                    bool(cur.text)
                    and cur.text[-1].isalnum()
                )

                # -----------------------------
                # FIX 2: перенос без дефиса
                # -----------------------------
                word_broken = (
                    same_paragraph
                    and same_column
                    and ends_at_right_edge
                    and starts_lowercase
                    and ends_with_word
                )

                if word_broken:
                    joined_text = (
                        cur.text.rstrip()
                        + nxt.text.lstrip()
                    )

                    merged.append(
                        _BLine(
                            text=joined_text,
                            page=cur.page,
                            x0=cur.x0,
                            x1=nxt.x1,
                            y0=cur.y0,
                            y1=nxt.y1,
                        )
                    )

                    i += 2
                    continue

            merged.append(cur)
            i += 1

        return merged


    @staticmethod
    def _fix_inner_word_breaks(text: str) -> str:
        """
        Склеивает PDF/OCR-разрывы внутри строки.

        Примеры:
            стандар тов -> стандартов
            информа ции -> информации
            компе тенции -> компетенции
        """

        pattern = re.compile(
            r"(?P<a>[а-яёa-z]{4,})\s+(?P<b>[а-яёa-z]{2,})",
            flags=re.IGNORECASE,
        )

        def repl(match: re.Match) -> str:
            left = match.group("a")
            right = match.group("b")

            # не склеиваем слишком длинные куски
            if len(left) > 15 or len(right) > 15:
                return match.group(0)

            # не склеиваем слова после точки
            if left.endswith((".", ":", ";")):
                return match.group(0)

            return left + right

        prev = None

        while prev != text:
            prev = text
            text = pattern.sub(repl, text)

        return text

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

        def append_body(target: StructureNode, line: str) -> None:
            line = normalize_line(line)
            if not line:
                return
            if target.text:
                target.text += "\n" + line
            else:
                target.text = line

        def active_node() -> StructureNode | None:
            if current_appendix is not None:
                return current_appendix
            return stack[-1] if stack else None

        i = body_start
        while i < len(lines):
            line = lines[i]
            if any(line.text.startswith(marker) for marker in _STOP_MARKERS):
                break

            appendix_match = _APPENDIX_HEADING_RE.match(line.text)
            if appendix_match and not self._is_toc_like(line.text):
                stack = []
                kind = appendix_match.group("kind")
                title = normalize_title(appendix_match.group("title") or "")
                if kind:
                    title = f"({kind}) {title}".strip()
                if not title:
                    title = normalize_title(line.text)
                current_appendix = StructureNode(
                    kind="appendix",
                    number=f"Приложение {appendix_match.group('id')}",
                    title=title,
                    page_start=line.page,
                    text="",
                )
                appendices.append(current_appendix)
                i += 1
                continue

            clause_match = _CLAUSE_HEADING_RE.match(line.text)
            if clause_match and not self._is_toc_like(line.text):
                if current_appendix is not None:
                    append_body(current_appendix, line.text)
                    i += 1
                    continue

                number = clause_match.group("number")
                rest = clause_match.group("rest").strip()
                depth = number.count(".")
                if depth == 0:
                    title, skip = self._complete_title(rest, lines, i + 1)
                    initial_body = ""
                else:
                    title = ""
                    skip = 0
                    initial_body = normalize_line(rest)
                if depth == 0 and (not title or not self._is_valid_heading(number, title)):
                    node = active_node()
                    if node is not None:
                        append_body(node, line.text)
                    i += 1
                    continue

                if depth > 0 and not self._belongs_to_current_tree(number, stack):
                    node = active_node()
                    if node is not None:
                        append_body(node, line.text)
                    i += 1
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
                    text=initial_body,
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

                i += 1 + skip
                continue

            node = active_node()
            if node is not None:
                append_body(node, line.text)

            i += 1

        for section in sections:
            self._finalize_node_text(section)
        for appendix in appendices:
            self._finalize_node_text(appendix)

        return sections, appendices

    def _finalize_node_text(self, node: StructureNode) -> None:
        node.text = normalize_block(node.text)
        for child in node.children:
            self._finalize_node_text(child)

    def _complete_title(
        self, rest: str, lines: list[_Line], start_idx: int
    ) -> tuple[str, int]:
        title = normalize_title(self._strip_page_leaders(rest))
        consumed = 0

        if len(title) >= 50:
            return title, consumed

        while start_idx + consumed < len(lines):
            nxt = lines[start_idx + consumed]
            if self._is_toc_like(nxt.text):
                break
            if _CLAUSE_HEADING_RE.match(nxt.text) or _APPENDIX_HEADING_RE.match(
                nxt.text
            ):
                break
            addition = normalize_line(nxt.text)
            if not addition:
                consumed += 1
                continue
            if re.match(r"^\d+(?:\.\d+)*\s", addition):
                break
            title = normalize_title(f"{title} {addition}")
            consumed += 1
            if len(title) >= 80:
                break

        return title, consumed

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
        lines = [normalize_line(ln) for ln in full_text.splitlines()]
        start_idx = next(
            (i + 1 for i, line in enumerate(lines) if line == "Содержание"),
            None,
        )
        if start_idx is None:
            return []

        entries: list[TocEntry] = []
        idx = start_idx
        while idx < len(lines):
            stripped = lines[idx]
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
                        title=normalize_title(title),
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
                        title=normalize_title(title),
                        page=page,
                    )
                )
                continue

            if entries and not stripped[0].isdigit():
                if "НАЦИОНАЛЬНЫЙ" in stripped or "Standardization in" in stripped:
                    break
                prev = entries[-1]
                extra_title, extra_page = self._parse_toc_rest(stripped)
                prev.title = normalize_title(f"{prev.title} {extra_title}")
                if prev.page is None:
                    prev.page = extra_page

        return entries

    @staticmethod
    def _line_looks_like_toc(line: str, lookahead: list[str]) -> bool:
        if ".." in line or _TOC_PAGE_RE.search(line):
            return True
        window = " ".join([line, *(ln for ln in lookahead if ln)])
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
