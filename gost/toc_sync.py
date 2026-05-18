from __future__ import annotations

from gost.models import GostDocumentStructure, StructureNode, TocEntry
from gost.text_normalize import normalize_title, repair_known_title


def apply_toc_to_structure(
    structure: GostDocumentStructure,
    toc: list[TocEntry],
) -> dict[str, list[str]]:
    toc_map = _build_toc_map(toc)
    warnings: list[str] = []

    def walk(nodes: list[StructureNode]) -> None:
        for node in nodes:
            toc_title = toc_map.get(node.number)
            repaired = repair_known_title(node.number, node.title, toc_title)
            if toc_title and normalize_title(node.title) != normalize_title(toc_title):
                if len(normalize_title(node.title)) < len(normalize_title(toc_title)) * 0.5:
                    warnings.append(
                        f"Title mismatch for {node.number}: "
                        f"'{node.title}' -> '{toc_title}'"
                    )
            node.title = repaired
            walk(node.children)

    walk(structure.sections)
    for appendix in structure.appendices:
        toc_title = toc_map.get(appendix.number)
        appendix.title = repair_known_title(appendix.number, appendix.title, toc_title)

    return {"title_warnings": warnings}


def _build_toc_map(toc: list[TocEntry]) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in toc:
        title = normalize_title(entry.title)
        if title:
            result[entry.number] = title
    return result
