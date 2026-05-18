from __future__ import annotations

from typing import Any

from gost.models import (
    DocumentLink,
    GostDocumentStructure,
    GostMetadata,
    NormativeReference,
    ParsedGost,
    PdfLink,
    StructureNode,
    TocEntry,
)

def export_parsed_gost(parsed: ParsedGost) -> dict[str, Any]:
    merged_refs = _merge_refs_for_export(
        parsed.index_normative_references,
        parsed.structure.normative_references,
    )
    return {
        "metadata": _export_metadata(parsed.metadata),
        "table_of_contents": [_export_toc(e) for e in parsed.structure.table_of_contents],
        "sections": [_export_node(n) for n in parsed.structure.sections],
        "appendices": [_export_node(n) for n in parsed.structure.appendices],
        "normative_references": [_export_ref(r) for r in merged_refs],
        "pdf_links": [_export_link(link) for link in parsed.structure.pdf_links],
        "document_links": [
            _export_document_link(link) for link in parsed.structure.document_links
        ],
        "document": {
            "page_count": parsed.structure.page_count,
            "pdf_path": str(parsed.pdf_path),
        },
    }


def export_links_report(parsed: ParsedGost) -> dict[str, Any]:
    pdf_links = parsed.structure.pdf_links
    by_pdf_source: dict[str, int] = {}
    for link in pdf_links:
        by_pdf_source[link.source] = by_pdf_source.get(link.source, 0) + 1

    doc_links = parsed.structure.document_links
    by_link_type: dict[str, int] = {}
    resolved_count = 0
    for link in doc_links:
        by_link_type[link.link_type] = by_link_type.get(link.link_type, 0) + 1
        if link.resolved:
            resolved_count += 1

    return {
        "pdf_links": {
            "total": len(pdf_links),
            "unique_urls": len({link.url for link in pdf_links}),
            "by_source": by_pdf_source,
            "links": [_export_link(link) for link in pdf_links],
        },
        "document_links": {
            "total": len(doc_links),
            "resolved": resolved_count,
            "unresolved": len(doc_links) - resolved_count,
            "by_type": by_link_type,
            "links": [_export_document_link(link) for link in doc_links],
        },
    }


def _merge_refs_for_export(
    index_refs: list[NormativeReference],
    pdf_refs: list[NormativeReference],
) -> list[NormativeReference]:
    from gost.normative_refs import merge_normative_references

    return merge_normative_references(index_refs, pdf_refs)


def _export_metadata(meta: GostMetadata) -> dict[str, Any]:
    return {
        "source_url": meta.source_url,
        "designation": meta.designation,
        "status": meta.status,
        "title_ru": meta.title_ru,
        "title_en": meta.title_en,
        "text_updated_at": meta.text_updated_at,
        "description_updated_at": meta.description_updated_at,
        "published_at": meta.published_at,
        "effective_from": meta.effective_from,
        "replaces": meta.replaces,
        "scope": meta.scope,
        "classification_path": list(meta.classification_path),
        "pdf_url": meta.pdf_url,
        "extra": dict(meta.extra),
    }


def _export_toc(entry: TocEntry) -> dict[str, Any]:
    return {
        "number": entry.number,
        "title": entry.title,
        "page": entry.page,
    }


def _export_node(node: StructureNode) -> dict[str, Any]:
    return {
        "kind": node.kind,
        "number": node.number,
        "title": node.title,
        "page_start": node.page_start,
        "page_end": node.page_end,
        "breadcrumb": node.breadcrumb,
        "text": node.text,
        "children": [_export_node(child) for child in node.children],
    }


def _export_ref(ref: NormativeReference) -> dict[str, Any]:
    return {
        "designation": ref.designation,
        "title": ref.title,
        "source_url": ref.source_url,
        "page": ref.page,
    }


def _export_link(link: PdfLink) -> dict[str, Any]:
    return {
        "url": link.url,
        "page": link.page,
        "source": link.source,
    }


def _export_document_link(link: DocumentLink) -> dict[str, Any]:
    return {
        "source": link.source,
        "target": link.target,
        "link_type": link.link_type,
        "target_type": link.target_type,
        "canonical_target": link.canonical_target,
        "page": link.page,
        "resolved": link.resolved,
        "excerpt": link.excerpt,
        "char_start": link.char_start,
        "char_end": link.char_end,
        "range_end": link.range_end,
    }
