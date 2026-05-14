"""Regresion: operador pg_trgm `%` no debe duplicarse como `%%` en el SQL."""

from pathlib import Path


def test_faq_search_sql_uses_single_percent_trigram_operator() -> None:
    repo = Path(__file__).resolve().parents[1] / "src" / "biomont_common" / "db" / "faq_repository.py"
    text = repo.read_text(encoding="utf-8")
    assert "normalized_question % $" in text
    assert "normalized_question %%" not in text
