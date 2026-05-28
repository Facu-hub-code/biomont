"""Tests de ensamblado de prompt del clasificador (spec 008)."""

from biomont_common.agent_config_prompt import (
    IntentPromptLine,
    build_classifier_system_prompt,
)


def test_build_classifier_includes_enabled_intents_only() -> None:
    prompt = build_classifier_system_prompt(
        preamble="Intro test.",
        intents=[
            IntentPromptLine("dosage_question", "dosis", True, 10),
            IntentPromptLine("chitchat", "hola", False, 20),
        ],
    )
    assert "Intro test." in prompt
    assert "dosage_question" in prompt
    assert "- chitchat:" not in prompt
    assert "Reglas obligatorias" in prompt
