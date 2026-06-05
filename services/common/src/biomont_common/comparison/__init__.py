"""Utilidades del comparador comercial."""

from biomont_common.comparison.presenter import (
    build_redactor_input,
    detect_presentation_mode,
    format_comparison_diff_brief,
    format_comparison_diff_full,
    format_comparison_narrative_brief,
    format_focus_no_difference,
    normalize_summary_output,
    render_redactor_output,
)
from biomont_common.comparison.redactor_validate import validate_redactor_output

__all__ = [
    "build_redactor_input",
    "detect_presentation_mode",
    "format_comparison_diff_brief",
    "format_comparison_diff_full",
    "format_comparison_narrative_brief",
    "normalize_summary_output",
    "format_focus_no_difference",
    "render_redactor_output",
    "validate_redactor_output",
]
