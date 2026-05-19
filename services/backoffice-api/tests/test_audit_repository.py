from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import pytest

from app.db.audit_repository import audit_json_default, dumps_audit_payload


@dataclass(slots=True)
class _SampleRow:
    id: uuid.UUID
    created_at: datetime
    label: str


def test_dumps_audit_payload_serializes_datetime_and_uuid() -> None:
    now = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
    row = _SampleRow(id=uuid.uuid4(), created_at=now, label="x")
    raw = dumps_audit_payload(asdict(row))
    assert raw is not None
    parsed = json.loads(raw)
    assert parsed["label"] == "x"
    assert parsed["created_at"] == now.isoformat()
    assert parsed["id"] == str(row.id)


def test_audit_json_default_rejects_unknown_types() -> None:
    with pytest.raises(TypeError):
        audit_json_default(object())
