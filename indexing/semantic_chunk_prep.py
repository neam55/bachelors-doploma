from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterator

from gost.models import (
    DocumentLink,
    GostDocumentStructure,
    GostMetadata,
    NormativeReference,
    ParsedGost,
    StructureNode,
)
from gost.text_normalize import normalize_block, normalize_title
from indexing.chunk_builder import (
    _extract_node_links,
    _group_links_by_source,
    _looks_like_toc,
)

DEFAULT_VERSION = "parsed-v1"
LONG_BODY_THRESHOLD = 800
_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[.!?…;])\s+(?=[А-ЯЁA-Z0-9«\"(])",
)


def prepare_semantic_chunk_input(
    parsed: ParsedGost,
    *,
    document_id: str | None = None,
    version: str = DEFAULT_VERSION,
    long_body_threshold: int = LONG_BODY_THRESHOLD,
) -> dict[str, Any]:
    meta = parsed.metadata
    structure = parsed.structure
    doc_id = document_id or meta.designation.strip()
    links_by_source = _group_links_by_source(structure.document_links)

    nodes_for_chunking: list[dict[str, Any]] = []
    sentences_by_node: dict[str, list[str]] = {}
    links_by_node: dict[str, list[dict[str, Any]]] = {}
    chunking_candidates: list[dict[str, Any]] = []
    structural_nodes: list[dict[str, Any]] = []
    text_blocks: list[dict[str, Any]] = []
    all_sentences: list[dict[str, Any]] = []
    all_links: list[dict[str, Any]] = []

    tree_root = _build_document_tree_node(meta, structure, doc_id, version)

    document_node = _normalize_document_root(meta, structure, doc_id, version, links_by_source)
    _register_node_outputs(
        document_node,
        nodes_for_chunking=nodes_for_chunking,
        sentences_by_node=sentences_by_node,
        links_by_node=links_by_node,
        chunking_candidates=chunking_candidates,
        structural_nodes=structural_nodes,
        text_blocks=text_blocks,
        all_sentences=all_sentences,
        all_links=all_links,
        long_body_threshold=long_body_threshold,
        force_include=True,
    )

    for section in structure.sections:
        tree_root["children"].append(
            _build_subtree(
                section,
                parent_id=document_node["node_id"],
                document_id=doc_id,
                version=version,
                links_by_source=links_by_source,
                nodes_for_chunking=nodes_for_chunking,
                sentences_by_node=sentences_by_node,
                links_by_node=links_by_node,
                chunking_candidates=chunking_candidates,
                structural_nodes=structural_nodes,
                text_blocks=text_blocks,
                all_sentences=all_sentences,
                all_links=all_links,
                long_body_threshold=long_body_threshold,
            )
        )

    appendix_entries: list[dict[str, Any]] = []
    for appendix in structure.appendices:
        appendix_entries.append(
            _build_subtree(
                appendix,
                parent_id=document_node["node_id"],
                document_id=doc_id,
                version=version,
                links_by_source=links_by_source,
                nodes_for_chunking=nodes_for_chunking,
                sentences_by_node=sentences_by_node,
                links_by_node=links_by_node,
                chunking_candidates=chunking_candidates,
                structural_nodes=structural_nodes,
                text_blocks=text_blocks,
                all_sentences=all_sentences,
                all_links=all_links,
                long_body_threshold=long_body_threshold,
                force_include=True,
            )
        )

    tree_root["appendices"] = appendix_entries

    normative_block = _build_normative_references_block(
        structure.normative_references,
        section_2_body=_find_section_body(structure, "2"),
        document_id=doc_id,
        version=version,
        parent_id=_node_id(doc_id, "section", "2"),
    )
    if normative_block:
        _register_node_outputs(
            normative_block,
            nodes_for_chunking=nodes_for_chunking,
            sentences_by_node=sentences_by_node,
            links_by_node=links_by_node,
            chunking_candidates=chunking_candidates,
            structural_nodes=structural_nodes,
            text_blocks=text_blocks,
            all_sentences=all_sentences,
            all_links=all_links,
            long_body_threshold=long_body_threshold,
            force_include=True,
        )
        tree_root["normative_references_block"] = normative_block

    return {
        "document_id": doc_id,
        "version": version,
        "source_url": meta.source_url,
        "nodes_for_chunking": nodes_for_chunking,
        "sentences_by_node": sentences_by_node,
        "links_by_node": links_by_node,
        "chunking_candidates": chunking_candidates,
        "normalized_document_tree": tree_root,
        "structural_nodes": structural_nodes,
        "text_blocks": text_blocks,
        "sentences": all_sentences,
        "links": all_links,
        "normative_references": [
            _export_normative_reference(ref) for ref in structure.normative_references
        ],
        "stats": {
            "nodes_for_chunking": len(nodes_for_chunking),
            "chunking_candidates": len(chunking_candidates),
            "sentences": len(all_sentences),
            "links": len(all_links),
            "normative_references": len(structure.normative_references),
        },
    }


def prepare_from_json(
    data: dict[str, Any],
    *,
    document_id: str | None = None,
    version: str = DEFAULT_VERSION,
    long_body_threshold: int = LONG_BODY_THRESHOLD,
) -> dict[str, Any]:
    parsed = _parsed_from_export_dict(data)
    return prepare_semantic_chunk_input(
        parsed,
        document_id=document_id,
        version=version,
        long_body_threshold=long_body_threshold,
    )


def prepare_from_json_file(
    path: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return prepare_from_json(payload, **kwargs)


def save_preparation(
    result: dict[str, Any],
    path: str | Path,
    *,
    format: str = "json",
) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if format == "jsonl":
        with out.open("w", encoding="utf-8") as handle:
            for node in result.get("nodes_for_chunking", []):
                handle.write(json.dumps(node, ensure_ascii=False) + "\n")
        meta_path = out.with_suffix(".meta.json")
        meta = {k: v for k, v in result.items() if k != "nodes_for_chunking"}
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return out

    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _node_id(document_id: str, kind: str, number: str) -> str:
    safe_number = re.sub(r"\s+", "_", number.strip())
    return f"{document_id}:{kind}:{safe_number}"


def _normalize_text(text: str) -> str:
    return normalize_block(text or "")


def _normalize_breadcrumb(breadcrumb: str) -> str:
    parts = [p.strip() for p in breadcrumb.split(">") if p.strip()]
    return " > ".join(parts)


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = _SENTENCE_SPLIT_RE.split(text)
    sentences = [_normalize_text(part) for part in parts if _normalize_text(part)]
    return sentences


def _normalize_document_root(
    meta: GostMetadata,
    structure: Any,
    document_id: str,
    version: str,
    links_by_source: dict[str, list],
) -> dict[str, Any]:
    body = _normalize_text(meta.scope or "")
    breadcrumb = document_id
    outgoing = _extract_node_links(document_id, links_by_source)
    return {
        "node_id": _node_id(document_id, "document", "root"),
        "source_node_id": document_id,
        "kind": "document",
        "number": document_id,
        "title": _normalize_text(meta.title_ru or ""),
        "body_text": body,
        "page_start": 1,
        "page_end": structure.page_count,
        "parent_id": None,
        "breadcrumb": breadcrumb,
        "hierarchy_path": [document_id],
        "links": [],
        "outgoing_links": outgoing,
        "document_id": document_id,
        "version": version,
    }


def _normalize_structure_node(
    node: StructureNode,
    *,
    document_id: str,
    version: str,
    parent_id: str | None,
    links_by_source: dict[str, list],
) -> dict[str, Any]:
    kind = node.kind
    number = node.number
    title = normalize_title(node.title or "")
    body_text = _normalize_text(node.text or "")
    breadcrumb = _normalize_breadcrumb(node.breadcrumb or "")
    hierarchy_path = [part.strip() for part in breadcrumb.split(">") if part.strip()]
    outgoing = _extract_node_links(number, links_by_source)

    return {
        "node_id": _node_id(document_id, kind, number),
        "source_node_id": number,
        "kind": kind,
        "number": number,
        "title": title,
        "body_text": body_text,
        "page_start": node.page_start,
        "page_end": node.page_end,
        "parent_id": parent_id,
        "breadcrumb": breadcrumb,
        "hierarchy_path": hierarchy_path,
        "links": [],
        "outgoing_links": outgoing,
        "document_id": document_id,
        "version": version,
    }


def _build_normative_references_block(
    references: list[NormativeReference],
    *,
    section_2_body: str,
    document_id: str,
    version: str,
    parent_id: str,
) -> dict[str, Any] | None:
    if not references and not section_2_body:
        return None

    ref_objects = [_export_normative_reference(ref) for ref in references]
    lines = [
        f"{ref['designation']} — {ref['title']}"
        if ref.get("title")
        else ref["designation"]
        for ref in ref_objects
    ]
    body_from_refs = _normalize_text("\n".join(lines))
    body_text = body_from_refs or _normalize_text(section_2_body)

    return {
        "node_id": _node_id(document_id, "normative_references", "2"),
        "source_node_id": "2",
        "kind": "normative_references",
        "number": "2",
        "title": "Нормативные ссылки",
        "body_text": body_text,
        "page_start": None,
        "page_end": None,
        "parent_id": parent_id,
        "breadcrumb": f"{document_id} > Раздел 2 > Нормативные ссылки",
        "hierarchy_path": [document_id, "Раздел 2", "Нормативные ссылки"],
        "links": ref_objects,
        "outgoing_links": [],
        "document_id": document_id,
        "version": version,
        "normative_references": ref_objects,
    }


def _export_normative_reference(ref: NormativeReference | dict[str, Any]) -> dict[str, Any]:
    if isinstance(ref, dict):
        return {
            "designation": ref.get("designation"),
            "title": ref.get("title"),
            "source_url": ref.get("source_url"),
            "page": ref.get("page"),
        }
    return {
        "designation": ref.designation,
        "title": ref.title,
        "source_url": ref.source_url,
        "page": ref.page,
    }


def _find_section_body(structure: Any, number: str) -> str:
    for section in structure.sections:
        if section.number == number:
            return section.text or ""
        for node in _iter_nodes(section.children):
            if node.number == number:
                return node.text or ""
    return ""


def _build_subtree(
    node: StructureNode,
    *,
    parent_id: str,
    document_id: str,
    version: str,
    links_by_source: dict[str, list],
    nodes_for_chunking: list[dict[str, Any]],
    sentences_by_node: dict[str, list[str]],
    links_by_node: dict[str, list[dict[str, Any]]],
    chunking_candidates: list[dict[str, Any]],
    structural_nodes: list[dict[str, Any]],
    text_blocks: list[dict[str, Any]],
    all_sentences: list[dict[str, Any]],
    all_links: list[dict[str, Any]],
    long_body_threshold: int,
    force_include: bool = False,
) -> dict[str, Any]:
    normalized = _normalize_structure_node(
        node,
        document_id=document_id,
        version=version,
        parent_id=parent_id,
        links_by_source=links_by_source,
    )
    _register_node_outputs(
        normalized,
        nodes_for_chunking=nodes_for_chunking,
        sentences_by_node=sentences_by_node,
        links_by_node=links_by_node,
        chunking_candidates=chunking_candidates,
        structural_nodes=structural_nodes,
        text_blocks=text_blocks,
        all_sentences=all_sentences,
        all_links=all_links,
        long_body_threshold=long_body_threshold,
        force_include=force_include or node.kind == "appendix",
    )
    children = [
        _build_subtree(
            child,
            parent_id=normalized["node_id"],
            document_id=document_id,
            version=version,
            links_by_source=links_by_source,
            nodes_for_chunking=nodes_for_chunking,
            sentences_by_node=sentences_by_node,
            links_by_node=links_by_node,
            chunking_candidates=chunking_candidates,
            structural_nodes=structural_nodes,
            text_blocks=text_blocks,
            all_sentences=all_sentences,
            all_links=all_links,
            long_body_threshold=long_body_threshold,
        )
        for child in node.children
    ]
    return _tree_entry_from_normalized(normalized, children)


def _iter_nodes(nodes: list[StructureNode]) -> Iterator[StructureNode]:
    for node in nodes:
        yield node
        yield from _iter_nodes(node.children)


def _build_document_tree_node(
    meta: GostMetadata,
    structure: Any,
    document_id: str,
    version: str,
) -> dict[str, Any]:
    return {
        "node_id": _node_id(document_id, "document", "root"),
        "kind": "document",
        "number": document_id,
        "title": normalize_title(meta.title_ru or ""),
        "document_id": document_id,
        "version": version,
        "children": [],
        "appendices": [],
    }


def _tree_entry_from_normalized(
    normalized: dict[str, Any],
    children: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "node_id": normalized["node_id"],
        "kind": normalized["kind"],
        "number": normalized["number"],
        "title": normalized["title"],
        "page_start": normalized["page_start"],
        "page_end": normalized["page_end"],
        "parent_id": normalized["parent_id"],
        "body_text_length": len(normalized.get("body_text", "")),
        "children": children,
    }


def _should_include_in_chunking(node: dict[str, Any], *, force_include: bool) -> bool:
    if force_include:
        return True
    if _looks_like_toc(node.get("body_text", "")):
        return False

    kind = node.get("kind")
    body = node.get("body_text", "")
    outgoing = node.get("outgoing_links") or []

    if kind == "normative_references":
        return True
    if kind == "appendix":
        return bool(body) or bool(outgoing)
    if kind == "document":
        return bool(body)
    if kind == "section" and node.get("number") == "2":
        return True
    if body:
        return True
    if outgoing:
        return True
    return False


def _register_node_outputs(
    node: dict[str, Any],
    *,
    nodes_for_chunking: list[dict[str, Any]],
    sentences_by_node: dict[str, list[str]],
    links_by_node: dict[str, list[dict[str, Any]]],
    chunking_candidates: list[dict[str, Any]],
    structural_nodes: list[dict[str, Any]],
    text_blocks: list[dict[str, Any]],
    all_sentences: list[dict[str, Any]],
    all_links: list[dict[str, Any]],
    long_body_threshold: int,
    force_include: bool = False,
) -> None:
    node_id = node["node_id"]
    body = node.get("body_text", "")
    outgoing = node.get("outgoing_links") or []
    embedded_links = node.get("links") or []

    structural_nodes.append(
        {
            "node_id": node_id,
            "kind": node["kind"],
            "number": node["number"],
            "title": node["title"],
            "parent_id": node.get("parent_id"),
            "page_start": node.get("page_start"),
            "page_end": node.get("page_end"),
            "breadcrumb": node.get("breadcrumb"),
            "hierarchy_path": node.get("hierarchy_path"),
        }
    )

    if body:
        text_blocks.append(
            {
                "node_id": node_id,
                "source_node_id": node.get("source_node_id"),
                "body_text": body,
                "char_count": len(body),
            }
        )

    if outgoing or embedded_links:
        links_by_node[node_id] = list(outgoing)
        for link in outgoing:
            all_links.append({**link, "node_id": node_id, "source_node_id": node.get("source_node_id")})
        for link in embedded_links:
            item = {**link, "node_id": node_id, "source_node_id": node.get("source_node_id")}
            links_by_node.setdefault(node_id, []).append(item)
            all_links.append(item)

    sentences: list[str] = []
    if len(body) > long_body_threshold:
        sentences = _split_sentences(body)
        sentences_by_node[node_id] = sentences
        for index, sentence in enumerate(sentences):
            all_sentences.append(
                {
                    "node_id": node_id,
                    "source_node_id": node.get("source_node_id"),
                    "index": index,
                    "text": sentence,
                }
            )

    if not _should_include_in_chunking(node, force_include=force_include):
        return

    chunk_entry = {**node}
    if sentences:
        chunk_entry["sentences"] = sentences
    chunk_entry["chunking_mode"] = (
        "semantic_split" if len(body) > long_body_threshold else "whole"
    )
    nodes_for_chunking.append(chunk_entry)

    if len(body) > long_body_threshold or node.get("kind") in ("normative_references",):
        chunking_candidates.append(
            {
                "node_id": node_id,
                "source_node_id": node.get("source_node_id"),
                "kind": node["kind"],
                "number": node["number"],
                "title": node["title"],
                "body_length": len(body),
                "sentence_count": len(sentences),
                "chunking_mode": chunk_entry["chunking_mode"],
                "parent_id": node.get("parent_id"),
                "breadcrumb": node.get("breadcrumb"),
            }
        )


def _parsed_from_export_dict(data: dict[str, Any]) -> ParsedGost:
    meta_raw = data["metadata"]
    meta = GostMetadata(
        source_url=meta_raw["source_url"],
        designation=meta_raw["designation"],
        status=meta_raw.get("status"),
        title_ru=meta_raw.get("title_ru"),
        title_en=meta_raw.get("title_en"),
        text_updated_at=meta_raw.get("text_updated_at"),
        description_updated_at=meta_raw.get("description_updated_at"),
        published_at=meta_raw.get("published_at"),
        effective_from=meta_raw.get("effective_from"),
        replaces=meta_raw.get("replaces"),
        scope=meta_raw.get("scope"),
        classification_path=list(meta_raw.get("classification_path") or []),
        pdf_url=meta_raw.get("pdf_url"),
        extra=dict(meta_raw.get("extra") or {}),
    )

    def load_node(raw: dict[str, Any]) -> StructureNode:
        return StructureNode(
            kind=raw["kind"],
            number=raw["number"],
            title=raw.get("title") or "",
            page_start=raw.get("page_start"),
            page_end=raw.get("page_end"),
            breadcrumb=raw.get("breadcrumb") or "",
            text=raw.get("text") or "",
            children=[load_node(child) for child in raw.get("children") or []],
        )

    doc = data.get("document") or {}
    structure = GostDocumentStructure(
        page_count=doc.get("page_count") or 0,
        table_of_contents=[],
        sections=[load_node(s) for s in data.get("sections") or []],
        appendices=[load_node(a) for a in data.get("appendices") or []],
        normative_references=[
            NormativeReference(
                designation=r["designation"],
                title=r.get("title"),
                source_url=r.get("source_url"),
                page=r.get("page"),
            )
            for r in data.get("normative_references") or []
        ],
        document_links=[
            DocumentLink(
                source=lk["source"],
                target=lk["target"],
                link_type=lk["link_type"],
                target_type=lk.get("target_type"),
                canonical_target=lk.get("canonical_target"),
                page=lk.get("page"),
                resolved=lk.get("resolved", True),
                excerpt=lk.get("excerpt"),
                char_start=lk.get("char_start"),
                char_end=lk.get("char_end"),
                range_end=lk.get("range_end"),
            )
            for lk in data.get("document_links") or []
        ],
    )

    return ParsedGost(
        metadata=meta,
        pdf_path=Path(doc.get("pdf_path") or "."),
        structure=structure,
        index_normative_references=[],
    )


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare parsed GOST data for semantic chunking.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--input-json",
        type=str,
        help="Path to JSON from export_parsed_gost",
    )
    source.add_argument(
        "--url",
        type=str,
        help="Stroyinf index URL (runs GostParser)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/gost_semantic_chunk_input.json",
        help="Output JSON path (default: data/gost_semantic_chunk_input.json)",
    )
    parser.add_argument(
        "--format",
        choices=("json", "jsonl"),
        default="json",
        help="Output format",
    )
    parser.add_argument(
        "--long-threshold",
        type=int,
        default=LONG_BODY_THRESHOLD,
        help="Body length threshold for semantic_split candidates",
    )
    parser.add_argument(
        "--document-id",
        type=str,
        default=None,
        help="Override document_id",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=DEFAULT_VERSION,
        help="Version tag stored in each node",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = _build_cli_parser().parse_args(argv)

    if args.input_json:
        result = prepare_from_json_file(
            args.input_json,
            document_id=args.document_id,
            version=args.version,
            long_body_threshold=args.long_threshold,
        )
    else:
        from gost import GostParser

        parsed = GostParser().parse(args.url)
        result = prepare_semantic_chunk_input(
            parsed,
            document_id=args.document_id,
            version=args.version,
            long_body_threshold=args.long_threshold,
        )

    out_path = save_preparation(result, args.output, format=args.format)
    stats = result["stats"]
    print(f"Saved: {out_path}")
    print(f"nodes_for_chunking: {stats['nodes_for_chunking']}")
    print(f"chunking_candidates: {stats['chunking_candidates']}")
    print(f"sentences: {stats['sentences']}")
    print(f"links: {stats['links']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
