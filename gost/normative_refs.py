from __future__ import annotations

import re

from gost.models import NormativeReference, StructureNode
from gost.text_normalize import normalize_block, normalize_line

_GOST_LINE_RE = re.compile(
    r"^(ГОСТ\s+(?:Р\s+)?\d+(?:\.\d+)*(?:\s*[-—–]\s*\d+)?)\s+(.+)$",
    re.IGNORECASE,
)
_GOST_INLINE_RE = re.compile(
    r"ГОСТ\s+(?:Р\s+)?\d+(?:\.\d+)*(?:\s*[-—–]\s*\d+)?",
    re.IGNORECASE,
)
_OK_LINE_RE = re.compile(
    r"^(ОК(?:\s*\([^)]+\))?\s+\d{3}(?:\s*\([^)]+\))?(?:\s+\d+)?)\s*(.*)$",
    re.IGNORECASE,
)


def extract_normative_references_from_section(
    section: StructureNode | None,
) -> list[NormativeReference]:
    if section is None:
        return []

    refs: list[NormativeReference] = []
    seen: set[str] = set()
    page = section.page_start
    body = section.text or ""

    for line in body.splitlines():
        line = normalize_line(line)
        if not line or line.startswith("2 "):
            continue

        gost_match = _GOST_LINE_RE.match(line)
        if gost_match:
            designation = re.sub(r"\s+", " ", gost_match.group(1)).strip()
            title = _clean_ref_title(gost_match.group(2))
            key = designation.lower()
            if key not in seen:
                seen.add(key)
                refs.append(
                    NormativeReference(
                        designation=designation,
                        title=title,
                        page=page,
                    )
                )
            continue

        ok_match = _OK_LINE_RE.match(line)
        if ok_match:
            designation = re.sub(r"\s+", " ", ok_match.group(1)).strip()
            title = _clean_ref_title(ok_match.group(2)) or None
            key = designation.lower()
            if key not in seen:
                seen.add(key)
                refs.append(
                    NormativeReference(
                        designation=designation,
                        title=title,
                        page=page,
                    )
                )

    if not refs:
        for match in _GOST_INLINE_RE.finditer(normalize_block(body)):
            designation = re.sub(r"\s+", " ", match.group(0)).strip()
            key = designation.lower()
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                NormativeReference(
                    designation=designation,
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


def _clean_ref_title(raw: str) -> str | None:
    title = normalize_line(raw)
    if not title or title.upper().startswith("ГОСТ"):
        return None
    if len(title) < 3:
        return None
    return title[:300]
