import os
import time
from models import create_gateway
from models.plugins import discover_plugins
from models.ProviderRegistry import (
    embedder_registry,
    llm_registry,
    reranker_registry,
)


def main() -> None:
    discover_plugins()

    print("Registered plugins:")
    print("  llm:      ", llm_registry.list_providers())
    print("  embedder: ", embedder_registry.list_providers())
    print("  reranker: ", reranker_registry.list_providers())

    gateway = create_gateway()
    start = time.perf_counter()
    answer = gateway.chat("What is RAG in one sentence?")
    print(answer)
    end = time.perf_counter()
    print(f"LLM response time: {end - start}")
    start = time.perf_counter()
    gateway.rerank("What is RAG in one sentence?", ["RAG is a technology that allows you to retrieve and use information from a large repository of documents.", 
    "RAG is a technology that allows you to retrieve and use information from a large repository of documents.", 
    "RAG isn't a technology that allows you to retrieve and use information from a large repository of documents.",
    "RAG is a cooking recipie",
    "RAG is a cancerous tumor",
    "RAG is short for retrival augmented generation"])
    end = time.perf_counter()
    print(f"Rerank time: {end - start} seconds for reranking")
    start = time.perf_counter()
    gateway.embed(["What is RAG in one sentence?", "My name is Hanz", "I hate Kevin HArt"])
    end = time.perf_counter()
    print(f"Embed time: {end - start} seconds for embedding")


if __name__ == "__main__":
    main()
