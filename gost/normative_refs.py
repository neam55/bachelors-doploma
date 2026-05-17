from __future__ import annotations

import re

from gost.models import NormativeReference, StructureNode

_GOST_DESIGNATION_RE = re.compile(
    r"(ГОСТ\s+(?:Р\s+)?[\d]+(?:\.[\d]+)*(?:\s*[-—]\s*[\d]+)?)",
    re.IGNORECASE,
)
_OK_RE = re.compile(r"(ОК(?:\s*\([^)]+\))?\s+[\d\w\-]+)", re.IGNORECASE)


def extract_normative_references_from_section(
    section: StructureNode | None,
) -> list[NormativeReference]:
    if section is None:
        return []

    refs: list[NormativeReference] = []
    seen: set[str] = set()
    page = section.page_start

    for block in _iter_text_blocks(section):
        for pattern in (_GOST_DESIGNATION_RE, _OK_RE):
            for match in pattern.finditer(block):
                designation = re.sub(r"\s+", " ", match.group(1)).strip()
                if designation in seen:
                    continue
                seen.add(designation)
                title = _title_after_designation(block, match.end())
                refs.append(
                    NormativeReference(
                        designation=designation,
                        title=title,
                        page=page,
                    )
                )
    return refs


def merge_normative_references(
    from_index: list[NormativeReference],
    from_pdf: list[NormativeReference],
) -> list[NormativeReference]:
    by_key: dict[str, NormativeReference] = {}

    for ref in from_pdf:
        key = _normalize_designation(ref.designation)
        by_key[key] = NormativeReference(
            designation=ref.designation,
            title=ref.title,
            source_url=ref.source_url,
            page=ref.page,
        )

    for ref in from_index:
        key = _normalize_designation(ref.designation)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = NormativeReference(
                designation=ref.designation,
                title=ref.title,
                source_url=ref.source_url,
                page=ref.page,
            )
            continue
        by_key[key] = NormativeReference(
            designation=existing.designation,
            title=existing.title or ref.title,
            source_url=ref.source_url or existing.source_url,
            page=existing.page or ref.page,
        )

    return sorted(by_key.values(), key=lambda r: _normalize_designation(r.designation))


def _normalize_designation(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _iter_text_blocks(node: StructureNode) -> list[str]:
    blocks = [node.text] if node.text else []
    for child in node.children:
        blocks.extend(_iter_text_blocks(child))
    return blocks


def _title_after_designation(block: str, start: int) -> str | None:
    tail = block[start:].strip()
    if not tail or tail[0] in ".;,":
        return None
    title = tail.split(";")[0].split(".")[0].strip()
    if len(title) < 3 or title.upper().startswith("ГОСТ"):
        return None
    return title[:200] if title else None
