__all__ = [
    "prepare_semantic_chunk_input",
    "prepare_from_json",
    "prepare_from_json_file",
    "save_preparation",
]


def __getattr__(name: str):
    if name in __all__:
        from indexing import semantic_chunk_prep

        return getattr(semantic_chunk_prep, name)
    raise AttributeError(name)
