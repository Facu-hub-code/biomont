"""Splitter para el ETL: markdown -> chunks aptos para embeddings.

Convive el chunker viejo (`MarkdownChunker`, basado en headers H1/H2/H3 +
tokens) con el nuevo `StructuredMarkdownChunker` (spec 003), guiado por la
estructura conocida de los PDFs reales (ficha tecnica, bitacora,
balotario). El primero se mantiene para el camino flag-off; el segundo
alimenta `knowledge_chunks` con metadata enriquecida.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import tiktoken
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from biomont_common.schemas.knowledge import DocumentKind


@dataclass(slots=True)
class TextChunk:
    index: int
    content: str
    token_count: int
    metadata: dict


@dataclass(slots=True)
class StructuredSection:
    """Seccion detectada por `StructuredMarkdownChunker`."""

    index: int
    number: str | None
    title: str | None
    kind: str
    raw_text: str
    parent_index: int | None = None


@dataclass(slots=True)
class StructuredChunk:
    """Chunk asociado a una `StructuredSection`."""

    index: int
    section_index: int
    content: str
    token_count: int
    section_type: str | None
    subsection_type: str | None = None
    topic: str | None = None
    contains_table: bool = False
    contains_dose: bool = False
    species: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class StructuredChunkingResult:
    sections: list[StructuredSection]
    chunks: list[StructuredChunk]


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


# ---------------------------------------------------------------------------
# StructuredMarkdownChunker (spec 003)
# ---------------------------------------------------------------------------

# Regex de seccionado por tipo de documento.
# Las cabeceras del PDF llegan en mayusculas o con numeracion mixta; estos
# patrones cubren los layouts observados en los PDFs reales del corpus.
# Docling suele anteponer `## ` — ver `_line_for_structure_match`.
_MARKDOWN_HEADING_PREFIX_RE = re.compile(r"^\s*#{1,6}\s+")
_FT_SECTION_RE = re.compile(
    r"^\s*(?P<num>\d{1,2})\.\s+(?P<title>[A-Z][A-ZÁÉÍÓÚÑ0-9 ,\.\-/]+)\s*$"
)
_BITACORA_MACRO_RE = re.compile(
    r"^\s*(?P<num>\d{1,2})\s*[°º]\s+(?P<title>.+?)\s*$"
)
# Macro "1. Generalidades..."; filtro `_accept_bitacora_macro_dot`.
_BITACORA_MACRO_DOT_RE = re.compile(
    r"^\s*(?P<num>\d{1,2})\.\s+(?P<title>.+)\s*$"
)
_BITACORA_SUB_RE = re.compile(
    r"^\s*(?P<num>\d{1,2}\.\d{1,2})\.?\s+(?P<title>.+?)\s*$"
)
# Docling suele emitir `## · ¿...?` (punto medio U+00B7), no siempre `•` (U+2022).
_BALOTARIO_BULLET_CHARS = "•·\\*\\-"
_BALOTARIO_Q_RE = re.compile(
    rf"^\s*[{_BALOTARIO_BULLET_CHARS}]\s*¿(?P<question>.+?)\?\s*$"
)
_BALOTARIO_NUMBERED_DOT_Q_RE = re.compile(
    r"^\s*(?P<num>\d{1,2})\s*\.\s*(?P<question>¿.+?\?)\s*$",
)
_BALOTARIO_NUMBERED_SPACE_Q_RE = re.compile(
    r"^\s*(?P<num>\d{1,2})\s+(?P<question>¿.+?\?)\s*$",
)
_PAGE_BREAK_RE = re.compile(r"^-{2,}\s*\d+\s*of\s*\d+\s*-{2,}$")

_DOSE_PATTERNS = [
    re.compile(r"\d+\s*(?:-\s*\d+\s*)?mg\s*/\s*kg", re.IGNORECASE),
    re.compile(r"\bc\s*/\s*\d+\s*h\b", re.IGNORECASE),
    re.compile(r"\bcada\s+\d+\s*(?:h|horas|d[ií]as|semanas|meses)\b", re.IGNORECASE),
    re.compile(r"\b\d+\s*(?:mg|ml)\s*/\s*(?:kg|d[ií]a)\b", re.IGNORECASE),
]

_TABLE_HEURISTIC_TOKENS = (
    "peso corporal",
    "kg verde",
    "kg morado",
    "kg rojo",
    "kg celeste",
    "kg amarillo",
    "dosis vía",
    "vía de administración",
)

# Especies que reconocemos a nivel chunk para metadata.species.
_SPECIES_HINTS: dict[str, str] = {
    "perro": "canino",
    "perros": "canino",
    "canino": "canino",
    "caninos": "canino",
    "gato": "felino",
    "gatos": "felino",
    "felino": "felino",
    "felinos": "felino",
    "bovino": "bovino",
    "bovinos": "bovino",
    "vacuno": "bovino",
    "porcino": "porcino",
    "porcinos": "porcino",
    "cerdo": "porcino",
    "ovino": "ovino",
    "ovinos": "ovino",
    "alpaca": "alpaca",
    "alpacas": "alpaca",
    "conejo": "conejo",
    "conejos": "conejo",
    "erizo": "erizo",
    "erizos": "erizo",
}


def _detect_section_type(kind: DocumentKind, title: str | None) -> str | None:
    """Mapea el titulo de seccion a una etiqueta semantica acotada."""

    if not title:
        return None
    t = title.lower()
    if kind == DocumentKind.ficha_tecnica:
        if "dosificac" in t:
            return "dosing_table"
        if "contraindic" in t:
            return "contraindications"
        if "indicac" in t:
            return "indications"
        if "reacciones" in t or "adversas" in t:
            return "adverse_reactions"
        if "farmacodinamia" in t:
            return "pharmacodynamics"
        if "farmacocin" in t:
            return "pharmacokinetics"
        if "precauci" in t:
            return "precautions"
        if "presentaciones" in t:
            return "presentations"
        if "conservaci" in t:
            return "storage"
        if "vía" in t and "administraci" in t:
            return "administration"
        if "composici" in t:
            return "composition"
        if "especies" in t:
            return "species"
        if "interacciones" in t:
            return "drug_interactions"
        if "margen" in t and "seguridad" in t:
            return "safety_margin"
        if "informaci" in t and "adicional" in t:
            return "additional_info"
        return "ficha_other"
    if kind == DocumentKind.bitacora:
        if "general" in t and "principio" in t:
            return "active_principle_overview"
        if "mecanismo" in t and "acción" in t.replace("a\u0301", "á"):
            return "mechanism_of_action"
        if "mecanismo" in t and "accion" in t:
            return "mechanism_of_action"
        if "precaucion" in t:
            return "precautions"
        if "interacciones" in t:
            return "drug_interactions"
        if "efectos adversos" in t or "efectos colaterales" in t:
            return "adverse_effects"
        if "protocolo" in t:
            return "protocol"
        if "extra" in t and "etiqueta" in t:
            return "off_label"
        if "formulaciones" in t and "externos" in t:
            return "external_formulations"
        if "competidor" in t or "argumentos" in t:
            return "competitive_arguments"
        if "objeciones" in t:
            return "objections"
        if "bibliograf" in t or "referenc" in t:
            return "bibliography"
        if "salud pública" in t or "salud publica" in t:
            return "public_health"
        return "bitacora_other"
    if kind == DocumentKind.balotario:
        return "faq_item"
    return None


def _contains_dose(text: str) -> bool:
    return any(p.search(text) for p in _DOSE_PATTERNS)


def _contains_table(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in _TABLE_HEURISTIC_TOKENS)


def _detect_species(text: str) -> list[str]:
    lowered = text.lower()
    found: set[str] = set()
    for word, canonical in _SPECIES_HINTS.items():
        # Match palabra completa para evitar falsos positivos (`gata` vs `gatos`).
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            found.add(canonical)
    return sorted(found)


def _line_for_structure_match(line: str) -> str:
    """Quita prefijo Markdown (`# `–`###### `) que Docling/antiguos conversores ponen."""

    stripped = line.strip("\r")
    stripped = _MARKDOWN_HEADING_PREFIX_RE.sub("", stripped, count=1)
    return stripped.strip()


def _accept_bitacora_macro_dot(title: str) -> bool:
    """Heuristica sobre titulos macro `N.` (Familia B) segun corpus real."""

    t = title.strip()
    if not t or len(t) > 92:
        return False
    tl = t.lower()
    if " mediante " in tl:
        return False
    # Enumeraciones microbiologicas sueltas dentro de capitulos (MARVO).
    if re.match(
        r"(?i)^bacterias\s+(gram|[a-z]+)|^strepto|^pasteur|^pseudo|^sapro",
        t,
    ):
        return False
    if re.match(r"(?i)^otros\s+microorganism", t):
        return False
    hints = (
        "generalidades",
        "principio activo",
        "protocol",
        "precaucion",
        "interaccion",
        "efecto advers",
        "efecto colateral",
        "formulacion",
        "argumentos",
        "bloque",
        "mecanismo",
        "farmaco",
        "qué sí",
        "que sí",
        "enfermedad",
        "aplicaci",
        "momentos estr",
        "integral del manejo",
        "uso en",
        "externos",
        "competidor",
        "terapeutic",
        "comparativ",
        "uso on-label",
        "dosis según",
    )
    return any(h in tl for h in hints)


class StructuredChunkerError(RuntimeError):
    """Error explicito cuando el parser no detecta secciones en un kind."""


class StructuredMarkdownChunker:
    """Chunkifica markdown guiado por la estructura del PDF (spec 003).

    No usa LLM. Devuelve la jerarquia de secciones detectada y los chunks
    resultantes (un chunk por seccion si entra en `chunk_tokens`, o varios
    refinados por `RecursiveCharacterTextSplitter` cuando es muy larga).

    Si el `kind` declarado no produce ninguna seccion (por ej. PDF mal
    parseado), lanza `StructuredChunkerError` para que el documento quede
    `failed` con razon legible. Esto evita degradar el retrieval en
    silencio.
    """

    def __init__(
        self,
        *,
        chunk_tokens: int = 500,
        overlap_tokens: int = 50,
        model_for_tokenizer: str = "gpt-4o-mini",
    ) -> None:
        token_length = _token_length_factory(model_for_tokenizer)
        self._token_length = token_length
        self._token_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_tokens,
            chunk_overlap=overlap_tokens,
            length_function=token_length,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def split(
        self, markdown: str, *, kind: DocumentKind
    ) -> StructuredChunkingResult:
        if not markdown.strip():
            return StructuredChunkingResult(sections=[], chunks=[])

        cleaned_lines = [
            line for line in markdown.splitlines() if not _PAGE_BREAK_RE.match(line)
        ]
        cleaned = "\n".join(cleaned_lines)

        if kind == DocumentKind.ficha_tecnica:
            sections = self._split_ficha_tecnica(cleaned)
        elif kind == DocumentKind.bitacora:
            sections = self._split_bitacora(cleaned)
        elif kind == DocumentKind.balotario:
            sections = self._split_balotario(cleaned)
        else:  # pragma: no cover - enum cerrado, defensive
            raise StructuredChunkerError(f"kind desconocido: {kind}")

        if not sections:
            raise StructuredChunkerError(
                f"etl_no_sections_detected:{kind.value}"
            )

        chunks = self._chunkify_sections(sections, kind=kind)
        return StructuredChunkingResult(sections=sections, chunks=chunks)

    # -- parsers por kind -------------------------------------------------

    def _split_ficha_tecnica(self, text: str) -> list[StructuredSection]:
        """Detecta 18 secciones numeradas `N. TITULO`."""

        sections: list[StructuredSection] = []
        current_lines: list[str] = []
        current_num: str | None = None
        current_title: str | None = None

        def flush() -> None:
            if current_num is None and not sections and not current_lines:
                return
            if current_num is None and not sections:
                # Preambulo antes de la primera seccion: lo descartamos.
                return
            sections.append(
                StructuredSection(
                    index=len(sections),
                    number=current_num,
                    title=current_title,
                    kind="ficha_tecnica",
                    raw_text="\n".join(current_lines).strip(),
                )
            )

        for line in text.splitlines():
            probe = _line_for_structure_match(line)
            match = _FT_SECTION_RE.match(probe)
            if match:
                if current_num is not None or current_lines:
                    flush()
                current_num = match.group("num")
                current_title = match.group("title").strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_num is not None:
            flush()

        return sections

    def _split_bitacora(self, text: str) -> list[StructuredSection]:
        """Detecta macro-secciones (`N°` o `N.` filtrado) y subsecciones `N.M`."""

        sections: list[StructuredSection] = []
        macro_stack: dict[str, int] = {}
        current_macro_index: int | None = None
        current_num: str | None = None
        current_title: str | None = None
        current_kind = "bitacora_macro"
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_macro_index
            if current_num is None and not current_lines and not sections:
                return
            if current_num is None and not sections:
                return
            parent_index = None
            if current_kind == "bitacora_sub" and current_macro_index is not None:
                parent_index = current_macro_index
            sections.append(
                StructuredSection(
                    index=len(sections),
                    number=current_num,
                    title=current_title,
                    kind=current_kind,
                    raw_text="\n".join(current_lines).strip(),
                    parent_index=parent_index,
                )
            )
            if current_kind == "bitacora_macro" and current_num is not None:
                macro_stack[current_num.split(".")[0]] = len(sections) - 1
                current_macro_index = len(sections) - 1

        for line in text.splitlines():
            probe = _line_for_structure_match(line)
            sub = _BITACORA_SUB_RE.match(probe)
            macro_deg = None if sub else _BITACORA_MACRO_RE.match(probe)
            macro_dot = None
            if sub is None and macro_deg is None:
                md = _BITACORA_MACRO_DOT_RE.match(probe)
                if md and _accept_bitacora_macro_dot(md.group("title")):
                    macro_dot = md
            if sub:
                if current_num is not None or current_lines:
                    flush()
                current_num = sub.group("num")
                current_title = sub.group("title").strip()
                current_kind = "bitacora_sub"
                macro_num = current_num.split(".")[0]
                current_macro_index = macro_stack.get(macro_num)
                current_lines = [line]
            elif macro_deg:
                if current_num is not None or current_lines:
                    flush()
                current_num = macro_deg.group("num")
                current_title = macro_deg.group("title").strip()
                current_kind = "bitacora_macro"
                current_lines = [line]
            elif macro_dot:
                if current_num is not None or current_lines:
                    flush()
                current_num = macro_dot.group("num")
                current_title = macro_dot.group("title").strip()
                current_kind = "bitacora_macro"
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_num is not None:
            flush()

        return sections

    def _split_balotario(self, text: str) -> list[StructuredSection]:
        """Pares pregunta-respuesta: viñeta `•/·/-/* ¿...?`, `N. ¿...?`, `N ¿...?`."""

        sections: list[StructuredSection] = []
        current_question: str | None = None
        current_number: str | None = None
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_number
            if current_question is None:
                return
            num_out = current_number if current_number is not None else str(len(sections) + 1)
            sections.append(
                StructuredSection(
                    index=len(sections),
                    number=num_out,
                    title=current_question,
                    kind="balotario",
                    raw_text="\n".join(current_lines).strip(),
                )
            )
            current_number = None

        for line in text.splitlines():
            probe = _line_for_structure_match(line)
            m_bullet = _BALOTARIO_Q_RE.match(probe)
            m_num_dot = None if m_bullet else _BALOTARIO_NUMBERED_DOT_Q_RE.match(probe)
            m_num_sp = (
                None
                if m_bullet or m_num_dot
                else _BALOTARIO_NUMBERED_SPACE_Q_RE.match(probe)
            )
            matched = m_bullet or m_num_dot or m_num_sp
            if matched:
                if current_question is not None:
                    flush()
                if m_bullet:
                    current_number = None
                    current_question = m_bullet.group("question").strip()
                elif m_num_dot:
                    current_number = m_num_dot.group("num")
                    current_question = m_num_dot.group("question").strip()
                elif m_num_sp:
                    current_number = m_num_sp.group("num")
                    current_question = m_num_sp.group("question").strip()
                current_lines = [line]
            else:
                if current_question is not None:
                    current_lines.append(line)

        if current_question is not None:
            flush()

        return sections

    # -- chunkificacion ---------------------------------------------------

    def _chunkify_sections(
        self,
        sections: list[StructuredSection],
        *,
        kind: DocumentKind,
    ) -> list[StructuredChunk]:
        chunks: list[StructuredChunk] = []
        chunk_index = 0
        for section in sections:
            content = section.raw_text.strip()
            if not content:
                continue
            section_type = _detect_section_type(kind, section.title)
            tokens = self._token_length(content)
            if tokens <= self._token_splitter._chunk_size:  # type: ignore[attr-defined]
                pieces = [content]
            else:
                pieces = self._token_splitter.split_text(content)
            for piece in pieces:
                cleaned = piece.strip()
                if not cleaned:
                    continue
                chunks.append(
                    StructuredChunk(
                        index=chunk_index,
                        section_index=section.index,
                        content=cleaned,
                        token_count=self._token_length(cleaned),
                        section_type=section_type,
                        subsection_type=(
                            "subsection" if section.kind == "bitacora_sub" else None
                        ),
                        topic=section.title,
                        contains_table=_contains_table(cleaned),
                        contains_dose=_contains_dose(cleaned),
                        species=_detect_species(cleaned),
                        metadata={
                            "section_number": section.number,
                            "section_title": section.title,
                            "section_kind_raw": section.kind,
                        },
                    )
                )
                chunk_index += 1
        return chunks
