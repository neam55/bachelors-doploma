from __future__ import annotations

import json
import os
import sys

from gost import GostParser
from indexing.chunk_prep import prepare_chunk_input, save_preparation
from indexing.chunker import Chunker


def ingest_doc(url: str) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parsed = GostParser().parse(url)
    metadata = parsed.metadata
    filename = f"data/{metadata.designation}.json"

    if os.path.exists(filename):
        with open(filename, encoding="utf-8") as file:
            result = json.load(file)
    else:
        result = prepare_chunk_input(parsed)
        save_preparation(result, filename)

    chunker = Chunker()
    chunks, links = chunker.chunk(metadata, result)
    print(chunks[:5])
    print(links[:5])
    print(result["normative_references"])


if __name__ == "__main__":
    ingest_doc(
        url="https://files.stroyinf.ru/Index/73/73932.htm",
    )
