"""Motor de calculo de dosis determinista (spec 011)."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from biomont_common.schemas.dosing import (
    CompletenessStatus,
    DoseCalculationError,
    DoseCalculationResult,
    DosingOutputUnit,
    DosingProfile,
    DosingRule,
    DosingRuleType,
)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _weight_in_band(
    weight: Decimal,
    rule: DosingRule,
) -> bool:
    if rule.weight_min_kg is None or rule.weight_max_kg is None:
        return False
    if rule.weight_min_inclusive:
        if weight < rule.weight_min_kg:
            return False
    elif weight <= rule.weight_min_kg:
        return False
    if rule.weight_max_inclusive:
        if weight > rule.weight_max_kg:
            return False
    elif weight >= rule.weight_max_kg:
        return False
    return True


def _apply_limits(value: Decimal, rule: DosingRule) -> Decimal:
    out = value
    if rule.min_output is not None and out < rule.min_output:
        out = rule.min_output
    if rule.max_output is not None and out > rule.max_output:
        out = rule.max_output
    return _quantize(out)


def _formula_description(rule: DosingRule) -> str:
    num = rule.formula_numerator or Decimal("0")
    den = rule.formula_denominator or Decimal("1")
    unit = rule.output_unit.value
    if rule.formula_per_kg:
        return f"{num}/{den} {unit} por kg de peso vivo"
    return f"{num}/{den} {unit}"


def calculate_dose(
    *,
    profile: DosingProfile,
    rules: list[DosingRule],
    product_id,
    product_name: str,
    weight_kg: Decimal,
    species: str,
    age_weeks: int | None = None,
) -> DoseCalculationResult | DoseCalculationError:
    """Calcula dosis sin LLM."""

    if not profile.supports_dose_calculation:
        return DoseCalculationError(
            code="not_supported",
            message="Este producto no tiene calculo de dosis habilitado.",
        )

    if profile.completeness_status != CompletenessStatus.complete:
        return DoseCalculationError(
            code="incomplete_catalog",
            message=(
                "No puedo calcular la dosis porque faltan datos en el catalogo. "
                "El equipo tecnico debe completarlos en el backoffice."
            ),
        )

    if profile.species != species:
        return DoseCalculationError(
            code="species_mismatch",
            message=f"No hay reglas de dosis publicadas para la especie '{species}'.",
        )

    if profile.min_weight_kg is not None and weight_kg < profile.min_weight_kg:
        return DoseCalculationError(
            code="out_of_range",
            message=f"El peso {weight_kg} kg esta por debajo del minimo documentado.",
        )
    if profile.max_weight_kg is not None and weight_kg > profile.max_weight_kg:
        return DoseCalculationError(
            code="out_of_range",
            message=f"El peso {weight_kg} kg supera el maximo documentado.",
        )

    if profile.min_age_weeks is not None and age_weeks is not None:
        if age_weeks < profile.min_age_weeks:
            return DoseCalculationError(
                code="age_restriction",
                message="La edad indicada esta por debajo del minimo permitido.",
            )
    if profile.max_age_weeks is not None and age_weeks is not None:
        if age_weeks > profile.max_age_weeks:
            return DoseCalculationError(
                code="age_restriction",
                message="La edad indicada supera el maximo permitido.",
            )

    active = [
        r
        for r in rules
        if r.is_active and r.published_version == profile.published_version
    ]
    if not active:
        return DoseCalculationError(
            code="no_rules",
            message="No hay reglas de dosis publicadas para este producto.",
        )

    formula_rules = [r for r in active if r.rule_type == DosingRuleType.formula]
    band_rules = sorted(
        [r for r in active if r.rule_type == DosingRuleType.weight_band],
        key=lambda r: (r.sort_order, r.weight_min_kg or Decimal("0")),
    )

    if formula_rules:
        rule = formula_rules[0]
        num = rule.formula_numerator or Decimal("0")
        den = rule.formula_denominator or Decimal("1")
        if rule.formula_per_kg:
            raw = weight_kg * num / den
        else:
            raw = num / den
        if rule.output_value is not None:
            raw = rule.output_value
        output = _apply_limits(raw, rule)
        return DoseCalculationResult(
            product_id=product_id,
            product_name=product_name,
            species=species,
            weight_kg=weight_kg,
            rule_type=DosingRuleType.formula,
            rule_label=rule.label,
            formula_description=_formula_description(rule),
            output_value=output,
            output_unit=rule.output_unit,
            published_version=profile.published_version,
            profile_id=profile.id,
        )

    for rule in band_rules:
        if _weight_in_band(weight_kg, rule):
            output_val = rule.output_value or Decimal("0")
            output = _apply_limits(output_val, rule)
            band = f"{rule.weight_min_kg}–{rule.weight_max_kg} kg"
            return DoseCalculationResult(
                product_id=product_id,
                product_name=product_name,
                species=species,
                weight_kg=weight_kg,
                rule_type=DosingRuleType.weight_band,
                rule_label=rule.label,
                formula_description=f"banda de peso {band}",
                output_value=output,
                output_unit=rule.output_unit,
                weight_band=band,
                published_version=profile.published_version,
                profile_id=profile.id,
            )

    return DoseCalculationError(
        code="no_matching_band",
        message=f"No hay banda de dosis publicada para {weight_kg} kg.",
    )


def format_dose_response(result: DoseCalculationResult) -> str:
    """Plantilla fija de respuesta con formula y valores usados."""

    unit = result.output_unit.value
    lines = [
        f"Para un/a {result.species} de **{result.weight_kg} kg** y el producto "
        f"**{result.product_name}**:",
        f"- Regla aplicada: {result.formula_description}",
    ]
    if result.rule_label:
        lines.append(f"- Presentacion/indicacion: **{result.rule_label}**")
    if result.weight_band:
        lines.append(f"- Banda de peso: {result.weight_band}")
    lines.append(
        f"- Resultado: **{result.output_value} {unit}**"
    )
    lines.append(
        f"Fuente: datos validados del backoffice (version {result.published_version})."
    )
    return "\n".join(lines)
