from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

LinkSource = Literal["annotation", "text"]


@dataclass
class NormativeReference:
    designation: str
    title: str | None = None
    source_url: str | None = None
    page: int | None = None


@dataclass
class PdfLink:
    url: str
    page: int
    source: LinkSource


@dataclass
class GostMetadata:
    source_url: str
    designation: str
    status: str | None = None
    title_ru: str | None = None
    title_en: str | None = None
    text_updated_at: str | None = None
    description_updated_at: str | None = None
    published_at: str | None = None
    effective_from: str | None = None
    replaces: str | None = None
    scope: str | None = None
    classification_path: list[str] = field(default_factory=list)
    pdf_url: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class TocEntry:
    number: str
    title: str
    page: int | None = None


@dataclass
class StructureNode:
    kind: Literal["section", "clause", "subclause", "appendix"]
    number: str
    title: str
    page_start: int | None = None
    page_end: int | None = None
    breadcrumb: str = ""
    text: str = ""
    children: list[StructureNode] = field(default_factory=list)


LinkType = Literal[
    "clause", "section", "appendix", "standard", "classifier", "range"
]


@dataclass
class DocumentLink:
    source: str
    target: str
    link_type: LinkType
    target_type: str | None = None
    canonical_target: str | None = None
    page: int | None = None
    resolved: bool = True
    excerpt: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    range_end: str | None = None


@dataclass
class GostDocumentStructure:
    page_count: int
    table_of_contents: list[TocEntry] = field(default_factory=list)
    sections: list[StructureNode] = field(default_factory=list)
    appendices: list[StructureNode] = field(default_factory=list)
    normative_references: list[NormativeReference] = field(default_factory=list)
    pdf_links: list[PdfLink] = field(default_factory=list)
    document_links: list[DocumentLink] = field(default_factory=list)


@dataclass
class ParsedGost:
    metadata: GostMetadata
    pdf_path: Path
    structure: GostDocumentStructure
    index_normative_references: list[NormativeReference] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        from gost.json_export import export_parsed_gost

        return export_parsed_gost(self)
