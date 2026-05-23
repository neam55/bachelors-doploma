__all__ = [
    "prepare_chunk_input",
    "prepare_from_json",
    "prepare_from_json_file",
    "save_preparation",
    "OCR_fixer"
]


def __getattr__(name: str):
    if name in __all__:
        from indexing import chunk_prep

        return getattr(chunk_prep, name)
    raise AttributeError(name)
