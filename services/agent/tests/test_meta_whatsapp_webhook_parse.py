"""Tests del parser de webhook Meta WhatsApp Cloud API."""

from __future__ import annotations

from app.services.meta_whatsapp_webhook_parse import (
    parse_whatsapp_cloud_inbound_messages,
)


def test_parse_text_message() -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"display_phone_number": "5491122334455"},
                            "messages": [
                                {
                                    "from": "51999000111",
                                    "id": "wamid.test",
                                    "type": "text",
                                    "text": {"body": "Hola agente"},
                                }
                            ],
                        },
                    }
                ]
            }
        ],
    }
    messages = parse_whatsapp_cloud_inbound_messages(payload)
    assert len(messages) == 1
    assert messages[0].provider == "meta"
    assert messages[0].from_user_id == "+51999000111"
    assert messages[0].to_business_phone == "+5491122334455"
    assert messages[0].text == "Hola agente"
    assert messages[0].provider_message_id == "wamid.test"


def test_parse_status_only_payload_returns_empty() -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "statuses": [{"id": "wamid.test", "status": "delivered"}]
                        },
                    }
                ]
            }
        ],
    }
    assert parse_whatsapp_cloud_inbound_messages(payload) == []


def test_parse_unknown_object_returns_empty() -> None:
    assert parse_whatsapp_cloud_inbound_messages({"object": "page"}) == []
