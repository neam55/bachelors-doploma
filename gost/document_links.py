from __future__ import annotations

import re
from typing import Literal

from gost.entity_registry import EntityRegistry, build_entity_registry
from gost.models import DocumentLink, GostDocumentStructure, StructureNode

LinkType = Literal["clause", "section", "appendix", "standard", "classifier", "range"]

_GOST_RE = re.compile(
    r"ГОСТ\s+(?:Р\s+)?\d+(?:\.\d+)*(?:\s*[-—–]\s*\d+)?",
    re.IGNORECASE,
)
_OK_RE = re.compile(
    r"(?<![А-Яа-яA-Za-z])ОК(?:\s*\([^)]+\))?\s+\d{3}(?:\s*\([^)]+\))?(?:\s+\d+)?",
    re.IGNORECASE,
)
_CLAUSE_RANGE_RE = re.compile(
    r"(?<![\d.])([1-6](?:\.\d+)+)\s*[—–\-]\s*([1-6](?:\.\d+)+)(?![\d.])",
)
_CLAUSE_EXPLICIT_RE = re.compile(
    r"(?:пункт[аеу]?\s+|подпункт[аеу]?\s+|согласно\s+|в\s+соответствии\s+с\s+)"
    r"([1-6](?:\.\d+)+)",
    re.IGNORECASE,
)
_CLAUSE_BARE_RE = re.compile(
    r"(?<![\d.])([1-6](?:\.\d+)+)(?![\d.])",
)
_SECTION_RE = re.compile(
    r"раздел[еау]?\s+([1-6])\b",
    re.IGNORECASE,
)
_APPENDIX_RE = re.compile(
    r"приложени[юияе]+\s+([А-ЯA-Z])\b",
    re.IGNORECASE,
)


def extract_document_links(structure: GostDocumentStructure) -> list[DocumentLink]:
    registry = build_entity_registry(structure)
    seen: set[tuple[str, str, LinkType]] = set()
    links: list[DocumentLink] = []

    def add(
        source: str,
        target: str,
        link_type: LinkType,
        *,
        page: int | None,
        text: str,
        start: int,
        end: int,
        range_end: str | None = None,
    ) -> None:
        if source == target and link_type in ("clause", "section"):
            return
        key = (source, target, link_type)
        if key in seen:
            return
        seen.add(key)

        canonical, target_type, resolved = registry.classify_target(target)
        if link_type == "range":
            target_type = "range"
            resolved = True
        elif link_type in ("standard", "classifier"):
            canonical = target
            target_type = link_type
            resolved = True
        elif link_type == "appendix":
            canonical, target_type, resolved = registry.classify_target(target)
        elif link_type == "section":
            canonical, target_type, resolved = registry.classify_target(target)
        else:
            canonical, target_type, resolved = registry.classify_target(target)

        left = max(0, start - 40)
        right = min(len(text), end + 40)
        excerpt = text[left:right].strip()

        links.append(
            DocumentLink(
                source=source,
                target=target,
                link_type=link_type,
                target_type=target_type,
                canonical_target=canonical,
                page=page,
                resolved=resolved,
                excerpt=excerpt,
                char_start=start,
                char_end=end,
                range_end=range_end,
            )
        )

    def walk(node: StructureNode) -> None:
        text = node.text
        if not text:
            for child in node.children:
                walk(child)
            return

        source = node.number
        page = node.page_start
        protected = _collect_protected_spans(text)

        for match in _APPENDIX_RE.finditer(text):
            letter = match.group(1).upper()
            target = f"Приложение {letter}"
            add(
                source,
                target,
                "appendix",
                page=page,
                text=text,
                start=match.start(),
                end=match.end(),
            )

        for match in _SECTION_RE.finditer(text):
            target = match.group(1)
            add(
                source,
                target,
                "section",
                page=page,
                text=text,
                start=match.start(),
                end=match.end(),
            )

        for match in _CLAUSE_RANGE_RE.finditer(text):
            start_id, end_id = match.group(1), match.group(2)
            range_target = f"{start_id}—{end_id}"
            add(
                source,
                range_target,
                "range",
                page=page,
                text=text,
                start=match.start(),
                end=match.end(),
                range_end=end_id,
            )
            for target in _expand_clause_range(start_id, end_id):
                add(
                    source,
                    target,
                    "clause",
                    page=page,
                    text=text,
                    start=match.start(),
                    end=match.end(),
                )

        for pattern in (_CLAUSE_EXPLICIT_RE, _CLAUSE_BARE_RE):
            for match in pattern.finditer(text):
                if _overlaps_protected(protected, match.start(), match.end()):
                    continue
                target = match.group(1)
                if _is_own_heading(text, source, match.start()):
                    continue
                if _inside_range_match(match, text):
                    continue
                add(
                    source,
                    target,
                    "clause",
                    page=page,
                    text=text,
                    start=match.start(),
                    end=match.end(),
                )

        for match in _GOST_RE.finditer(text):
            target = re.sub(r"\s+", " ", match.group(0)).strip()
            add(
                source,
                target,
                "standard",
                page=page,
                text=text,
                start=match.start(),
                end=match.end(),
            )

        for match in _OK_RE.finditer(text):
            target = re.sub(r"\s+", " ", match.group(0)).strip()
            add(
                source,
                target,
                "classifier",
                page=page,
                text=text,
                start=match.start(),
                end=match.end(),
            )

        for child in node.children:
            walk(child)

    for section in structure.sections:
        walk(section)
    for appendix in structure.appendices:
        walk(appendix)

    links.sort(key=lambda link: (link.source, link.link_type, link.target))
    return links


def _collect_protected_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in (_GOST_RE, _OK_RE, _CLAUSE_RANGE_RE):
        for match in pattern.finditer(text):
            spans.append((match.start(), match.end()))
    return spans


def _overlaps_protected(
    protected: list[tuple[int, int]], start: int, end: int
) -> bool:
    for p_start, p_end in protected:
        if not (end <= p_start or start >= p_end):
            return True
    return False


def _is_own_heading(text: str, source: str, match_start: int) -> bool:
    if match_start > 30:
        return False
    prefix = text[:match_start].strip()
    if not prefix:
        return text.lstrip().startswith(f"{source} ")
    return False


def _inside_range_match(match: re.Match[str], text: str) -> bool:
    for range_match in _CLAUSE_RANGE_RE.finditer(text):
        if range_match.start() <= match.start() < range_match.end():
            return True
    return False


def _expand_clause_range(start_id: str, end_id: str) -> list[str]:
    start_parts = start_id.split(".")
    end_parts = end_id.split(".")
    if len(start_parts) != len(end_parts):
        return [start_id, end_id]
    if start_parts[:-1] != end_parts[:-1]:
        return [start_id, end_id]

    try:
        start_last = int(start_parts[-1])
        end_last = int(end_parts[-1])
    except ValueError:
        return [start_id, end_id]

    if end_last < start_last or end_last - start_last > 30:
        return [start_id, end_id]

    prefix = ".".join(start_parts[:-1])
    if prefix:
        return [f"{prefix}.{index}" for index in range(start_last, end_last + 1)]
    return [str(index) for index in range(start_last, end_last + 1)]
