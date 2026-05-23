from __future__ import annotations

from langchain_core.documents import Document
from razdel import sentenize
from gost.models import GostMetadata
from models.ModelsGateway import ModelsGateway
from sklearn.metrics.pairwise import cosine_similarity
import re
from pymorphy3 import MorphAnalyzer
from langchain_text_splitters import RecursiveCharacterTextSplitter

class OCRFixer:
    def __init__(self):
        self._morph = MorphAnalyzer()

    def best_score(self, word: str) -> float:
        parses = self._morph.parse(word.lower())
        return max((p.score for p in parses), default=0.0)

    def is_known_word(self, word: str) -> bool:
        return any(p.score > 0.01 for p in self._morph.parse(word.lower()))

    def fix_ocr_word_breaks(self, text: str) -> str:
        text = text.replace('\xa0', ' ')
        text = re.sub(r'[ \t]+', ' ', text)

        text = re.sub(
            r'(?<=[А-Яа-яЁёA-Za-z])\s*-\s*\n\s*(?=[А-Яа-яЁёA-Za-z])',
            '',
            text
        )

        text = re.sub(
            r'(?<=[А-Яа-яЁёA-Za-z])\s*\n\s*(?=[А-Яа-яЁёA-Za-z])',
            ' ',
            text
        )

        def try_merge(m):
            left, right = m.group(1), m.group(2)
            merged = left + right

            score_merged = self.best_score(merged)
            score_left = self.best_score(left)
            score_right = self.best_score(right)

            if len(left) >= 4 and len(right) <= 5 and score_merged > 0.08 and score_merged >= max(score_left, score_right) * 2:
                return merged
            return left + ' ' + right

        text = re.sub(
            r'\b([А-Яа-яЁё]{4,})\s([А-Яа-яЁё]{2,5})\b',
            try_merge,
            text
        )

        text = re.sub(r'\s{2,}', ' ', text)
        text = re.sub(r'\s+([,.;:!?])', r'\1', text)
        return text.strip()
    
class Chunker:
    def __init__(
        self,
        max_chunk_length: int = 1000,
        overlap: int = 200
    ) -> None:
        self.max_chunk_length = max_chunk_length
        self.overlap = overlap
        self.ocr_fix = OCRFixer()

    def _recursive_chunker(self, node: dict, meta: dict) -> tuple:
        links: list[list[dict]] = []
        chunks: list[Document] = []
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.max_chunk_length,
            chunk_overlap=self.overlap,
            add_start_index=True,
        )
        docs = splitter.create_documents([node["body_text"]])

        for i, doc in enumerate(docs):            
            chunk_start = doc.metadata["start_index"]
            chunk_end = chunk_start + len(doc.page_content)

            link = [
                j
                for j in node["outgoing_links"]
                if j["char_start"] < chunk_end and j["char_end"] > chunk_start
            ]
            links.append(link)  
            doc.metadata=meta
        return docs, links

    def chunk(self, metadata: GostMetadata, content: dict) -> tuple:
        chunks: list[Document] = []
        links : list[list[dict]] = []
        nodes = content["nodes_for_chunking"]

        for node in nodes:
            node["body_text"] = self.ocr_fix.fix_ocr_word_breaks(node["body_text"])
            meta = metadata.__dict__.copy()
            meta.update({
                    "page_start" : node["page_start"],
                    "page_end" : node["page_end"],
                    "breadcrumb" : node["breadcrumb"]
                })
            if len(node["body_text"]) <= self.max_chunk_length:
                contents = f"{node['number']} {node['title']} {node['body_text']}".strip()
                chunks.append(
                    Document(
                        page_content=(
                            contents
                        ),
                        metadata=meta,
                    )
                )
                links.append(node["outgoing_links"])
            else:
                chunk, link = self._recursive_chunker(node, meta)            
                chunks.extend(chunk)
                links.extend(link)
        return chunks, links
