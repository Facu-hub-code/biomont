"""Tests del StructuredMarkdownChunker (spec 003).

Cubren CA-2: el chunker estructural detecta secciones por tipo de
documento, marca `contains_dose`/`contains_table` y propaga `species` al
metadata.
"""

from __future__ import annotations

import pytest

from biomont_common.integrations.text_splitter import (
    StructuredChunkerError,
    StructuredMarkdownChunker,
)
from biomont_common.schemas.knowledge import DocumentKind


_FT_MARKDOWN = """\
1. NOMBRE COMERCIAL DEL PRODUCTO

Proteggo 3M.

2. DOSIFICACION

Peso corporal kg verde 1400 mg.
Dosis: 25-56 mg/kg via oral.

3. CONTRAINDICACIONES

No usar en cachorros menores de 8 semanas. No usar en gestacion.

4. INFORMACION ADICIONAL

Notas varias.
"""


_BITACORA_MARKDOWN = """\
1° GENERALIDADES DEL PRINCIPIO ACTIVO

Las isoxazolinas son agentes ectoparasiticidas.

1.1 Mecanismo de accion

Actuan sobre canales GABA y glutamato. 10 mg/kg cada 12 semanas.

1.2 Farmacocinetica

Buena biodisponibilidad oral.

2° INTERACCIONES MEDICAMENTOSAS

Pocas interacciones reportadas en perros.
"""


_BALOTARIO_MARKDOWN = """\
Aca va el balotario.

• ¿Puede usarse en gestacion?

Si, los estudios indican seguridad demostrada en perras gestantes.

• ¿Cual es la dosis?

10 mg/kg cada 12 semanas, via oral.
"""


def test_ficha_tecnica_detects_sections():
    chunker = StructuredMarkdownChunker(chunk_tokens=1000)
    result = chunker.split(_FT_MARKDOWN, kind=DocumentKind.ficha_tecnica)

    section_titles = [s.title for s in result.sections]
    assert "NOMBRE COMERCIAL DEL PRODUCTO" in section_titles
    assert "DOSIFICACION" in section_titles
    assert "CONTRAINDICACIONES" in section_titles

    types = [c.section_type for c in result.chunks]
    assert "dosing_table" in types
    assert "contraindications" in types

    dosing_chunk = next(
        c for c in result.chunks if c.section_type == "dosing_table"
    )
    assert dosing_chunk.contains_dose is True
    assert dosing_chunk.contains_table is True


def test_bitacora_detects_macro_and_subsections():
    chunker = StructuredMarkdownChunker(chunk_tokens=1000)
    result = chunker.split(_BITACORA_MARKDOWN, kind=DocumentKind.bitacora)

    kinds = {s.kind for s in result.sections}
    assert "bitacora_macro" in kinds
    assert "bitacora_sub" in kinds

    subs = [s for s in result.sections if s.kind == "bitacora_sub"]
    assert any(s.number == "1.1" for s in subs)
    parents = {s.parent_index for s in subs}
    assert None not in parents  # todas las subsecciones tienen padre


def test_balotario_emits_one_section_per_question():
    chunker = StructuredMarkdownChunker(chunk_tokens=1000)
    result = chunker.split(_BALOTARIO_MARKDOWN, kind=DocumentKind.balotario)

    assert len(result.sections) == 2
    assert all(c.section_type == "faq_item" for c in result.chunks)
    # La segunda pregunta menciona dosis -> debe marcar contains_dose.
    chunks_with_dose = [c for c in result.chunks if c.contains_dose]
    assert len(chunks_with_dose) == 1


def test_species_detection_in_chunk_metadata():
    chunker = StructuredMarkdownChunker(chunk_tokens=1000)
    result = chunker.split(_BITACORA_MARKDOWN, kind=DocumentKind.bitacora)
    canine_chunks = [c for c in result.chunks if "canino" in c.species]
    assert canine_chunks, "el texto menciona perros, deberia detectar canino"


def test_chunker_fails_when_no_sections_detected():
    chunker = StructuredMarkdownChunker(chunk_tokens=1000)
    with pytest.raises(StructuredChunkerError):
        chunker.split(
            "Texto plano sin estructura conocida.",
            kind=DocumentKind.ficha_tecnica,
        )


def test_chunker_returns_empty_on_blank_markdown():
    chunker = StructuredMarkdownChunker(chunk_tokens=1000)
    result = chunker.split("   ", kind=DocumentKind.bitacora)
    assert result.sections == []
    assert result.chunks == []
