"""Splitter para el ETL: markdown -> chunks aptos para embeddings."""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


@dataclass(slots=True)
class TextChunk:
    index: int
    content: str
    token_count: int
    metadata: dict


_DEFAULT_HEADERS = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


def _token_length_factory(model: str = "gpt-4o-mini"):
    """Devuelve una funcion que mide tokens para `model`.

    Intenta usar el encoder real de tiktoken; si la red no esta disponible
    para descargar el encoding, cae a un encoder bundled (`cl100k_base`)
    y, en ultimo caso, a un heuristico basado en caracteres.
    """

    encoding = None
    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            encoding = None

    if encoding is None:
        def _token_length_fallback(text: str) -> int:
            return max(1, len(text) // 4)

        return _token_length_fallback

    def _token_length(text: str) -> int:
        return len(encoding.encode(text))

    return _token_length


class MarkdownChunker:
    """Splittea markdown preservando headers y luego refina por tokens.

    No hace I/O: util para tests y para correr offline.
    """

    def __init__(
        self,
        *,
        chunk_tokens: int = 500,
        overlap_tokens: int = 50,
        model_for_tokenizer: str = "gpt-4o-mini",
    ) -> None:
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=_DEFAULT_HEADERS,
            strip_headers=False,
        )
        token_length = _token_length_factory(model_for_tokenizer)
        self._token_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_tokens,
            chunk_overlap=overlap_tokens,
            length_function=token_length,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        self._token_length = token_length

    def split(self, markdown: str) -> list[TextChunk]:
        if not markdown.strip():
            return []

        header_chunks = self._header_splitter.split_text(markdown)
        flat: list[TextChunk] = []
        index = 0
        for header_chunk in header_chunks:
            pieces = self._token_splitter.split_text(header_chunk.page_content)
            metadata_base = dict(header_chunk.metadata or {})
            for piece in pieces:
                content = piece.strip()
                if not content:
                    continue
                flat.append(
                    TextChunk(
                        index=index,
                        content=content,
                        token_count=self._token_length(content),
                        metadata=metadata_base,
                    )
                )
                index += 1
        return flat
