"""Test del chunker compartido."""

from __future__ import annotations

from biomont_common.integrations.text_splitter import MarkdownChunker


def test_markdown_chunker_split_into_non_empty_chunks() -> None:
    markdown = (
        "# Producto X\n\n"
        "Indicaciones: para uso veterinario en bovinos.\n\n"
        "## Dosis\n\n"
        "0.2 mg/kg por via subcutanea.\n\n"
        "## Contraindicaciones\n\n"
        "No usar en animales gestantes.\n"
    )

    chunker = MarkdownChunker(chunk_tokens=200, overlap_tokens=20)
    chunks = chunker.split(markdown)

    assert chunks, "deberia generar al menos un chunk"
    assert all(chunk.content.strip() for chunk in chunks)
    assert all(chunk.token_count > 0 for chunk in chunks)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_markdown_chunker_empty_returns_empty() -> None:
    chunker = MarkdownChunker()
    assert chunker.split("") == []
    assert chunker.split("   \n\n") == []
