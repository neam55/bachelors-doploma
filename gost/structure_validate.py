from __future__ import annotations

from gost.models import GostDocumentStructure, StructureNode, TocEntry
from gost.text_normalize import normalize_title


def validate_structure_against_toc(
    structure: GostDocumentStructure,
    toc: list[TocEntry],
) -> dict[str, list[str]]:
    toc_map = {entry.number: normalize_title(entry.title) for entry in toc}
    missing_in_tree: list[str] = []
    title_mismatches: list[str] = []
    hierarchy_issues: list[str] = []

    tree_numbers: set[str] = set()

    def walk(node: StructureNode, parent_number: str | None) -> None:
        tree_numbers.add(node.number)
        if parent_number and not node.number.startswith(f"{parent_number}."):
            if node.kind != "appendix":
                hierarchy_issues.append(
                    f"{node.number} is not under parent {parent_number}"
                )

        toc_title = toc_map.get(node.number)
        if toc_title and normalize_title(node.title) != toc_title:
            if abs(len(normalize_title(node.title)) - len(toc_title)) > 5:
                title_mismatches.append(
                    f"{node.number}: tree='{node.title}' toc='{toc_title}'"
                )

        for child in node.children:
            walk(child, node.number if node.kind == "section" else parent_number)

    for section in structure.sections:
        walk(section, None)
    for appendix in structure.appendices:
        tree_numbers.add(appendix.number)
        toc_title = toc_map.get(appendix.number)
        if toc_title and normalize_title(appendix.title) != toc_title:
            title_mismatches.append(
                f"{appendix.number}: tree='{appendix.title}' toc='{toc_title}'"
            )

    for number in toc_map:
        if number not in tree_numbers and not number.startswith("Приложение"):
            if number.count(".") == 0 or any(
                n == number or n.startswith(f"{number}.") for n in tree_numbers
            ):
                continue
            missing_in_tree.append(number)

    return {
        "missing_in_tree": missing_in_tree,
        "title_mismatches": title_mismatches,
        "hierarchy_issues": hierarchy_issues,
    }
