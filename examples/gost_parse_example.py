from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

from gost import GostParser, export_links_report, export_parsed_gost
from gost.structure_validate import validate_structure_against_toc

INDEX_URL = "https://files.stroyinf.ru/Index/73/73932.htm"
OUT_DIR = Path("./data")


def _truncate_text_in_dict(node: dict, max_len: int = 400) -> dict:
    result = deepcopy(node)
    text = result.get("text", "")
    if len(text) > max_len:
        result["text"] = text[:max_len] + "…"
    result["children"] = [
        _truncate_text_in_dict(child, max_len) for child in result.get("children", [])
    ]
    return result


def _build_sample_export(full: dict, *, section_count: int = 2) -> dict:
    sample = deepcopy(full)
    sample["sections"] = [
        _truncate_text_in_dict(s) for s in full["sections"][:section_count]
    ]
    sample["appendices"] = [
        _truncate_text_in_dict(a) for a in full["appendices"][:1]
    ]
    sample["normative_references"] = full["normative_references"][:20]
    sample["pdf_links"] = full["pdf_links"]
    sample["document_links"] = full["document_links"][:30]
    sample["table_of_contents"] = full["table_of_contents"]
    sample["_note"] = "Sample export: first 2 sections, 1 appendix, truncated text, top 30 document_links"
    return sample


def _validation_report(full: dict, parsed) -> dict:
    section_numbers = [s["number"] for s in full["sections"]]
    appendix_ids = [
        a["number"].replace("Приложение ", "") for a in full["appendices"]
    ]
    return {
        "sections_expected": ["1", "2", "3", "4", "5", "6"],
        "sections_found": section_numbers,
        "sections_ok": section_numbers == ["1", "2", "3", "4", "5", "6"],
        "appendices_expected": ["А", "Б", "В", "Г"],
        "appendices_found": appendix_ids,
        "appendices_ok": appendix_ids == ["А", "Б", "В", "Г"],
        "normative_references_count": len(full["normative_references"]),
        "pdf_links_count": len(full["pdf_links"]),
        "document_links_count": len(full["document_links"]),
        "document_links_by_type": _count_by_type(full["document_links"]),
        "toc_entries": len(full["table_of_contents"]),
        "toc_validation": validate_structure_against_toc(
            parsed.structure, parsed.structure.table_of_contents
        ),
    }


def _count_by_type(links: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for link in links:
        key = link.get("link_type", "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    parsed = GostParser(download_dir=OUT_DIR / "gost_pdfs").parse(INDEX_URL)
    full = export_parsed_gost(parsed)
    sample = _build_sample_export(full, section_count=2)
    links_report = export_links_report(parsed)
    validation = _validation_report(full, parsed)

    paths = {
        "full": OUT_DIR / "gost_r_1_1_2020_full.json",
        "sample": OUT_DIR / "gost_r_1_1_2020_sample.json",
        "links_report": OUT_DIR / "gost_r_1_1_2020_links_report.json",
        "validation": OUT_DIR / "gost_r_1_1_2020_validation.json",
    }
    for key, path in paths.items():
        payload = {"full": full, "sample": sample, "links_report": links_report, "validation": validation}[key]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== Validation ===")
    for k, v in validation.items():
        print(f"  {k}: {v}")
    print("\n=== Links report ===")
    pdf = links_report["pdf_links"]
    doc = links_report["document_links"]
    print(f"  pdf_links: {pdf['total']}, unique URLs: {pdf['unique_urls']}")
    print(f"  document_links: {doc['total']} (resolved {doc['resolved']})")
    print(f"  document_links by_type: {doc['by_type']}")
    print("\n=== Output files ===")
    for path in paths.values():
        print(f"  {path}")


if __name__ == "__main__":
    main()
