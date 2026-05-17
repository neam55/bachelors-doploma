from __future__ import annotations

from gost.models import GostDocumentStructure, StructureNode

_SEPARATOR = " > "


def assign_breadcrumbs(structure: GostDocumentStructure, document_label: str) -> None:
    label = document_label.strip()
    if not label:
        label = "Документ"

    for section in structure.sections:
        _walk(section, [label], [])

    for appendix in structure.appendices:
        appendix.breadcrumb = _join([label, _segment_label(appendix)])


def _walk(node: StructureNode, root: list[str], parent_segments: list[str]) -> None:
    segment = _segment_label(node)
    node.breadcrumb = _join([*root, *parent_segments, segment])
    child_segments = [*parent_segments, segment]
    for child in node.children:
        _walk(child, root, child_segments)


def _segment_label(node: StructureNode) -> str:
    if node.kind == "section":
        return f"Раздел {node.number}"
    if node.kind == "appendix":
        return node.number
    return node.number


def _join(parts: list[str]) -> str:
    return _SEPARATOR.join(parts)
