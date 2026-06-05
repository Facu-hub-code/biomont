"""ComparisonRedactor: redaccion LLM sobre diff determinista (spec 013 + 014)."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from biomont_common.comparison.presenter import (
    build_redactor_input,
    format_comparison_diff_brief,
    format_comparison_diff_full,
    format_comparison_narrative_brief,
    format_focus_no_difference,
    redactor_user_payload,
    render_redactor_output,
)
from biomont_common.comparison.redactor_validate import validate_redactor_output
from biomont_common.logging import get_logger
from biomont_common.schemas.comparison import (
    ComparisonDiffResult,
    ComparisonRedactorOutput,
)

from app.agent.graph.nodes._helpers import trace_node
from app.agent.prompts.comparison_redactor import COMPARISON_REDACTOR_SYSTEM_PROMPT

_logger = get_logger("agent.graph.comparison_redactor")


@dataclass
class ComparisonRedactorNode:
    chat_model: BaseChatModel
    llm_enabled: bool = True

    async def __call__(self, state: dict) -> dict:
        updates: dict = {}
        with trace_node(updates, node="ComparisonRedactor") as result:
            raw_diff = state.get("comparison_diff")
            if not raw_diff:
                result["outcome"] = "skipped_no_diff"
                return updates

            diff = (
                raw_diff
                if isinstance(raw_diff, ComparisonDiffResult)
                else ComparisonDiffResult.model_validate(raw_diff)
            )
            query = state.get("query") or ""
            redactor_input = build_redactor_input(diff, query)

            result["payload"] = {
                "presentation_mode": redactor_input.presentation_mode,
                "focus_column_key": redactor_input.focus_column_key,
                "items_sent": len(redactor_input.items),
                "similarity_items_sent": len(redactor_input.similarity_items),
                "other_items_count": redactor_input.other_items_count,
                "llm_used": False,
            }

            if (
                redactor_input.presentation_mode == "focus"
                and redactor_input.focus_column_key
                and not redactor_input.items
            ):
                label = None
                for s in diff.similarities:
                    if s.column_key == redactor_input.focus_column_key:
                        label = s.header_label
                        break
                if label is None:
                    for d in diff.differences:
                        if d.column_key == redactor_input.focus_column_key:
                            label = d.header_label
                            break
                updates["answer_text"] = format_focus_no_difference(
                    subject_name=diff.subject_name,
                    competitor_name=diff.competitor_name,
                    column_key=redactor_input.focus_column_key,
                    header_label=label,
                )
                updates["structured_response"] = True
                result["outcome"] = "focus_no_difference"
                return updates

            if not diff.differences and not diff.similarities:
                updates["answer_text"] = format_comparison_narrative_brief(
                    redactor_input
                )
                updates["structured_response"] = True
                result["outcome"] = "empty_diff"
                return updates

            if not self.llm_enabled:
                text = _deterministic_format(diff, redactor_input)
                updates["answer_text"] = text
                updates["structured_response"] = True
                result["outcome"] = "deterministic_flag_off"
                return updates

            llm_out = await self._invoke_llm(redactor_input, query)
            if llm_out is not None:
                ok, reason = validate_redactor_output(llm_out, redactor_input)
                if ok:
                    updates["answer_text"] = render_redactor_output(llm_out)
                    updates["structured_response"] = True
                    result["payload"]["llm_used"] = True
                    result["payload"]["validation_passed"] = True
                    result["outcome"] = "redacted"
                    return updates
                _logger.info(
                    "comparison_redactor_validation_failed",
                    action="validate",
                    reason=reason,
                )
                result["payload"]["validation_passed"] = False
                result["payload"]["validation_reason"] = reason

            updates["answer_text"] = _deterministic_format(diff, redactor_input)
            updates["structured_response"] = True
            result["outcome"] = "fallback_deterministic"
        return updates

    async def _invoke_llm(
        self, redactor_input, query: str
    ) -> ComparisonRedactorOutput | None:
        structured = self.chat_model.with_structured_output(ComparisonRedactorOutput)
        user_content = redactor_user_payload(redactor_input, query)
        for attempt in range(2):
            try:
                response = await structured.ainvoke(
                    [
                        SystemMessage(content=COMPARISON_REDACTOR_SYSTEM_PROMPT),
                        HumanMessage(content=user_content),
                    ]
                )
            except Exception as exc:
                _logger.warning(
                    "comparison_redactor_llm_failed",
                    action="invoke",
                    attempt=attempt,
                    error=str(exc)[:200],
                )
                return None
            if isinstance(response, ComparisonRedactorOutput):
                ok, _ = validate_redactor_output(response, redactor_input)
                if ok or attempt == 1:
                    return response if ok else None
            elif isinstance(response, dict):
                try:
                    parsed = ComparisonRedactorOutput.model_validate(response)
                    ok, _ = validate_redactor_output(parsed, redactor_input)
                    if ok or attempt == 1:
                        return parsed if ok else None
                except Exception:
                    pass
        return None


def _deterministic_format(diff: ComparisonDiffResult, redactor_input) -> str:
    if redactor_input.presentation_mode == "full":
        return format_comparison_diff_full(diff)
    if redactor_input.presentation_mode == "summary":
        return format_comparison_narrative_brief(redactor_input)
    return format_comparison_diff_brief(redactor_input)
