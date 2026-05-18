from __future__ import annotations

import re
from typing import Any

from gost import GostParser
from gost.text_normalize import normalize_block


STANDARD_PREFIX_RE = re.compile(
    r"^(ГОСТ(?:\s+Р)?(?:\s+ИСО)?(?:/\s*МЭК)?|ГОСТ\s+МЭК|ISO|IEC|EN)\b",
    re.IGNORECASE,
)

CLAUSE_RE = re.compile(r"^\d+(?:\.\d+){0,4}$")
APPENDIX_RE = re.compile(r"^(Приложение\s+[А-ЯA-Z0-9]+)$", re.IGNORECASE)
SECTION_RE = re.compile(r"^\d+$")


def _clean_ocr_text(text: Any) -> str:
    if not text:
        return ""
    return normalize_block(str(text))


def _looks_like_toc(text: str) -> bool:
    if not text:
        return False

    t = text.lower()

    if "...." in t:
        return True

    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False

    toc_like = 0
    for ln in lines[:25]:
        if re.search(r"\.{3,}", ln) and re.search(r"\d+\s*$", ln):
            toc_like += 1

    return toc_like >= 3


def _infer_target_type(target: str) -> str:
    if not target:
        return "unknown"

    t = target.strip()

    if STANDARD_PREFIX_RE.match(t):
        return "standard"
    if APPENDIX_RE.match(t):
        return "appendix"
    if SECTION_RE.match(t):
        return "section"
    if re.search(r"\bОК\b", t, re.IGNORECASE):
        return "classifier"
    if CLAUSE_RE.match(t):
        return "clause"
    return "unknown"


def _normalize_link_relation(link_type: str, target: str, source_text: str = "") -> str:

    inferred = _infer_target_type(target)

    if inferred == "standard":
        return "standard"
    if inferred == "appendix":
        return "appendix"
    if inferred == "clause":
        return "clause"
    if inferred == "section":
        return "section"

    return link_type or "unknown"


def _iter_nodes(nodes):
    for node in nodes:
        yield node
        children = getattr(node, "children", None)
        if children:
            yield from _iter_nodes(children)


def _group_links_by_source(document_links) -> dict[str, list]:
    grouped: dict[str, list] = {}

    for lk in document_links or []:
        source = getattr(lk, "source", None)
        if not source:
            continue
        grouped.setdefault(source, []).append(lk)

    return grouped


def _extract_node_links(node_number: str, links_by_source: dict) -> list[dict]:
    result = []

    for lk in links_by_source.get(node_number, []):
        relation = _normalize_link_relation(
            getattr(lk, "link_type", None),
            getattr(lk, "target", "") or "",
            getattr(lk, "excerpt", "") or "",
        )

        target = getattr(lk, "target", "") or ""
        target_type = getattr(lk, "target_type", None) or _infer_target_type(target)

        result.append(
            {
                "source": getattr(lk, "source", None),
                "target": target,
                "relation": relation,
                "original_relation": getattr(lk, "link_type", None),
                "target_type": target_type,
                "canonical_target": getattr(lk, "canonical_target", None),
                "resolved": getattr(lk, "resolved", None),
                "page": getattr(lk, "page", None),
                "excerpt": getattr(lk, "excerpt", None),
                "char_start": getattr(lk, "char_start", None),
                "char_end": getattr(lk, "char_end", None),
            }
        )

    return result


def _build_document_chunk(meta, structure, document_links) -> dict:
    designation = getattr(meta, "designation", None)

    doc_links = []
    for lk in document_links or []:
        source = getattr(lk, "source", None)
        if source == designation:
            doc_links.append(
                {
                    "source": getattr(lk, "source", None),
                    "target": getattr(lk, "target", None),
                    "relation": _normalize_link_relation(
                        getattr(lk, "link_type", None),
                        getattr(lk, "target", "") or "",
                        getattr(lk, "excerpt", "") or "",
                    ),
                    "original_relation": getattr(lk, "link_type", None),
                    "target_type": _infer_target_type(getattr(lk, "target", "") or ""),
                    "resolved": getattr(lk, "resolved", None),
                    "page": getattr(lk, "page", None),
                    "excerpt": getattr(lk, "excerpt", None),
                }
            )

    return {
        "entity_type": "Document",
        "kind": "document",
        "number": designation,
        "title": getattr(meta, "title_ru", None),
        "text": _clean_ocr_text(getattr(meta, "scope", "") or ""),
        "own_text": _clean_ocr_text(getattr(meta, "scope", "") or ""),
        "page_start": 1,
        "page_end": getattr(structure, "page_count", None),
        "breadcrumb": designation,
        "hierarchy_path": [designation] if designation else [],
        "depth": 0,
        "parent_number": None,
        "is_toc_like": False,
        "outgoing_links": doc_links,
    }


def _build_node_chunk(node, links_by_source) -> dict:
    breadcrumb = _clean_ocr_text(getattr(node, "breadcrumb", "") or "")
    number = getattr(node, "number", None)
    kind = getattr(node, "kind", None) or "unknown"
    title = _clean_ocr_text(getattr(node, "title", "") or "")
    own_text = _clean_ocr_text(getattr(node, "text", "") or "")
    page_start = getattr(node, "page_start", None)
    page_end = getattr(node, "page_end", None)

    text = own_text

    hierarchy_path = breadcrumb.split(" > ") if breadcrumb else []
    depth = max(len(hierarchy_path) - 1, 0)

    parent_number = hierarchy_path[-2] if len(hierarchy_path) >= 2 else None

    return {
        "entity_type": kind.capitalize() if kind else None,
        "kind": kind,
        "number": number,
        "title": title,
        "text": text,
        "own_text": own_text,
        "page_start": page_start,
        "page_end": page_end,
        "breadcrumb": breadcrumb,
        "hierarchy_path": hierarchy_path,
        "depth": depth,
        "parent_number": parent_number,
        "is_toc_like": _looks_like_toc(text),
        "outgoing_links": _extract_node_links(number, links_by_source) if number else [],
    }


def build_semantic_chunks(url: str) -> list[dict]:

    parsed = GostParser().parse(url)

    meta = parsed.metadata
    structure = parsed.structure

    links_by_source = _group_links_by_source(getattr(structure, "document_links", None))

    chunks = []

    document_chunk = _build_document_chunk(
        meta,
        structure,
        getattr(structure, "document_links", None),
    )
    chunks.append(document_chunk)

    for node in _iter_nodes(getattr(structure, "sections", []) or []):
        if getattr(node, "kind", None) not in {"section", "clause", "subclause"}:
            continue

        chunk = _build_node_chunk(node, links_by_source)

        if chunk["is_toc_like"]:
            continue

        chunks.append(chunk)
    
    for appendix in getattr(structure, "appendices", []) or []:
        chunk = _build_node_chunk(appendix, links_by_source)

        if chunk["is_toc_like"]:
            continue

        chunks.append(chunk)

    return chunks


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    chunks = build_semantic_chunks(
        "https://files.stroyinf.ru/Index/73/73932.htm"
    )
    for chunk in chunks[:10]:
        print("=" * 80)
        print("TYPE:", chunk["entity_type"])
        print("NUMBER:", chunk["number"])
        print("TITLE:", chunk["title"])
        print("PAGES:", chunk["page_start"], "-", chunk["page_end"])
        print("TEXT:", chunk["text"][:100])
        print("OWN TEXT:", chunk.get("own_text", "")[:100])
        print("BREADCRUMB:", chunk["breadcrumb"])
        print("LINKS:", len(chunk["outgoing_links"]))