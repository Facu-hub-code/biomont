"""Tests de formato WhatsApp."""

from biomont_common.whatsapp_format import normalize_whatsapp_markdown, wa_bold


def test_wa_bold_wraps_with_single_asterisk() -> None:
    assert wa_bold("Protego 3M") == "*Protego 3M*"


def test_normalize_whatsapp_markdown_converts_double_asterisk() -> None:
    assert normalize_whatsapp_markdown("**formula** vs **dosis**") == "*formula* vs *dosis*"


def test_normalize_whatsapp_markdown_leaves_single_asterisk() -> None:
    assert normalize_whatsapp_markdown("*ya correcto*") == "*ya correcto*"
