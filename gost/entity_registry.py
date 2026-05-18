from __future__ import annotations

import re
from dataclasses import dataclass, field

from gost.models import GostDocumentStructure, StructureNode
from gost.text_normalize import normalize_title

_GOST_FULL_RE = re.compile(
    r"ГОСТ\s+(?:Р\s+)?\d+(?:\.\d+)*(?:\s*[-—–]\s*\d+)?",
    re.IGNORECASE,
)
_OK_RE = re.compile(
    r"ОК(?:\s*\([^)]+\))?\s+\d{3}(?:\s*\([^)]+\))?(?:\s+\d+)?",
    re.IGNORECASE,
)
_APPENDIX_ID_RE = re.compile(r"^Приложение\s+([А-ЯA-Z])$", re.IGNORECASE)


@dataclass
class EntityRegistry:
    nodes_by_number: dict[str, StructureNode] = field(default_factory=dict)
    standards: set[str] = field(default_factory=set)
    classifiers: set[str] = field(default_factory=set)
    appendix_ids: set[str] = field(default_factory=set)
    section_ids: set[str] = field(default_factory=set)

    def register_structure(self, structure: GostDocumentStructure) -> None:
        def walk(node: StructureNode) -> None:
            self.nodes_by_number[node.number] = node
            if node.kind == "section":
                self.section_ids.add(node.number)
            for child in node.children:
                walk(child)

        for section in structure.sections:
            walk(section)
        for appendix in structure.appendices:
            self.nodes_by_number[appendix.number] = appendix
            match = _APPENDIX_ID_RE.match(appendix.number)
            if match:
                self.appendix_ids.add(match.group(1).upper())

    def register_standard(self, designation: str) -> None:
        cleaned = re.sub(r"\s+", " ", designation).strip()
        if cleaned:
            self.standards.add(cleaned)

    def register_classifier(self, designation: str) -> None:
        cleaned = re.sub(r"\s+", " ", designation).strip()
        if cleaned:
            self.classifiers.add(cleaned)

    def classify_target(self, raw_target: str) -> tuple[str, str, bool]:
        target = re.sub(r"\s+", " ", raw_target).strip()
        if not target:
            return target, "unknown", False

        if _GOST_FULL_RE.fullmatch(target) or target in self.standards:
            return target, "standard", True

        if _OK_RE.fullmatch(target) or target in self.classifiers:
            return target, "classifier", True

        appendix_match = _APPENDIX_ID_RE.match(target)
        if appendix_match:
            canonical = f"Приложение {appendix_match.group(1).upper()}"
            return canonical, "appendix", canonical in self.nodes_by_number

        if target in self.section_ids:
            return target, "section", True

        if target in self.nodes_by_number:
            node = self.nodes_by_number[target]
            return target, node.kind, True

        if re.fullmatch(r"[1-6]", target):
            return target, "section", target in self.section_ids

        if re.fullmatch(r"[1-6](?:\.\d+)+", target):
            return target, self._infer_clause_kind(target), target in self.nodes_by_number

        return target, "unknown", False

    @staticmethod
    def _infer_clause_kind(number: str) -> str:
        depth = number.count(".")
        if depth <= 0:
            return "section"
        if depth == 1:
            return "clause"
        return "subclause"


def build_entity_registry(structure: GostDocumentStructure) -> EntityRegistry:
    registry = EntityRegistry()
    registry.register_structure(structure)
    for ref in structure.normative_references:
        if _OK_RE.search(ref.designation):
            registry.register_classifier(ref.designation)
        else:
            registry.register_standard(ref.designation)
    return registry
