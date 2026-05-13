"""Coercion de metadata JSON en filas RAG (asyncpg dict vs str)."""

from biomont_common.db.rag_repository import _metadata_row_to_dict


def test_metadata_none_is_empty_dict() -> None:
    assert _metadata_row_to_dict(None) == {}


def test_metadata_dict_passthrough() -> None:
    assert _metadata_row_to_dict({"a": 1}) == {"a": 1}


def test_metadata_json_string_becomes_dict() -> None:
    assert _metadata_row_to_dict('{"source": "pdf", "page": 2}') == {
        "source": "pdf",
        "page": 2,
    }


def test_metadata_empty_string_is_empty_dict() -> None:
    assert _metadata_row_to_dict("") == {}
    assert _metadata_row_to_dict("   ") == {}


def test_metadata_non_object_json_is_empty_dict() -> None:
    assert _metadata_row_to_dict("[1, 2]") == {}


def test_metadata_bytes_decoded() -> None:
    raw = b'{"k": "v"}'
    assert _metadata_row_to_dict(raw) == {"k": "v"}
