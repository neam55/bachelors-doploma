from __future__ import annotations

from gost.models import GostDocumentStructure, StructureNode


def assign_page_ends(structure: GostDocumentStructure) -> None:
    """Set page_end on each node from document order and the next node's page_start."""
    ordered = _collect_nodes_in_order(structure)
    if not ordered:
        return

    page_count = structure.page_count
    for index, node in enumerate(ordered):
        start = node.page_start
        if start is None:
            node.page_end = None
            continue

        end = page_count
        for successor in ordered[index + 1 :]:
            next_start = successor.page_start
            if next_start is not None and next_start > start:
                end = next_start - 1
                break

        node.page_end = max(start, end)


def _collect_nodes_in_order(structure: GostDocumentStructure) -> list[StructureNode]:
    ordered: list[StructureNode] = []

    def walk(nodes: list[StructureNode]) -> None:
        for node in nodes:
            ordered.append(node)
            walk(node.children)

    walk(structure.sections)
    ordered.extend(structure.appendices)
    return ordered
