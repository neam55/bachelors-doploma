from __future__ import annotations

import sys
from typing import Any

from gost import GostParser
from indexing.chunk_builder import build_semantic_chunks


def _print_list(title: str, items: list[Any], *, limit: int = 15) -> None:
    print(f"\n=== {title} ({len(items)}) ===")
    for item in items[:limit]:
        print(item)
    if len(items) > limit:
        print(f"... and {len(items) - limit} more")


def main(url: str | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    index_url = url or "https://files.stroyinf.ru/Index/73/73932.htm"
    parsed = GostParser().parse(index_url)
    chunks = build_semantic_chunks(index_url)

    documents = [c for c in chunks if c["entity_type"] == "Document"]
    sections = [c for c in chunks if c["kind"] == "section"]
    clauses = [c for c in chunks if c["kind"] == "clause"]
    subclauses = [c for c in chunks if c["kind"] == "subclause"]
    appendices = [c for c in chunks if c["kind"] == "appendix"]

    _print_list("Document", [c["number"] for c in documents])
    _print_list("Section", [(c["number"], c["title"]) for c in sections])
    _print_list("Clause", [(c["number"], c["title"]) for c in clauses])
    _print_list("Subclause", [(c["number"], c["title"]) for c in subclauses])
    _print_list("Appendix", [(c["number"], c["title"]) for c in appendices])

    normative = [
        (r.designation, r.title)
        for r in parsed.structure.normative_references
    ]
    _print_list("Normative references", normative)

    link_types: dict[str, int] = {}
    for lk in parsed.structure.document_links:
        link_types[lk.link_type] = link_types.get(lk.link_type, 0) + 1
    print("\n=== Document link types ===")
    print(link_types)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(arg)
