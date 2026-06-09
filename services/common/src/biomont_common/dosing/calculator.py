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
from biomont_common.whatsapp_format import wa_bold


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


_SPECIES_LABELS: dict[str, str] = {
    "canine": "perro",
    "feline": "gato",
    "bovine": "vaca",
    "porcine": "cerdo",
    "calf": "ternero",
    "equine": "equino",
    "ovine": "ovino",
}


def _species_article(species: str) -> str:
    label = _SPECIES_LABELS.get(species, species)
    if label == "vaca":
        return f"una {label}"
    return f"un {label}"


def _clean_rule_label(label: str | None) -> str | None:
    if not label:
        return None
    cleaned = label.split("—")[0].split(" - FT")[0].strip()
    if not cleaned:
        return None
    return cleaned.replace("comp/", "comprimido cada ").replace("comp", "comprimido")


def _formula_rate_text(result: DoseCalculationResult) -> str | None:
    from_label = _clean_rule_label(result.rule_label)
    if from_label:
        return from_label

    description = (result.formula_description or "").removesuffix(" de peso vivo")
    if not description:
        return None
    return (
        description.replace("tablets", "comprimidos")
        .replace("tablet", "comprimido")
        .replace("/", " por cada ")
    )


def _format_weight_kg(weight: Decimal) -> str:
    if weight == weight.to_integral_value():
        return str(int(weight))
    text = format(weight.normalize(), "f").rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _format_decimal_es(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    text = format(value.normalize(), "f").rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _weight_band_range_text(weight_band: str | None) -> str | None:
    if not weight_band:
        return None
    cleaned = weight_band.replace(" kg", "").replace("–", "-")
    parts = [p.strip() for p in cleaned.split("-", maxsplit=1)]
    if len(parts) != 2 or not all(parts):
        return None
    return f"indicado para pesos entre {parts[0]} y {parts[1]} kg"


def _format_tablets_human(value: Decimal) -> str:
    amount = value.quantize(Decimal("0.01"))
    whole = int(amount)
    fraction = amount - Decimal(whole)

    if fraction == Decimal("0.5"):
        if whole == 0:
            return "medio comprimido"
        if whole == 1:
            return "1 comprimido y medio"
        return f"{whole} comprimidos y medio"

    if fraction == Decimal("0"):
        if whole == 1:
            return "1 comprimido"
        return f"{whole} comprimidos"

    return f"{_format_decimal_es(amount)} comprimidos"


def _format_weight_band_response(result: DoseCalculationResult) -> str:
    subject = _species_article(result.species)
    weight = _format_weight_kg(result.weight_kg)
    product = result.product_name
    range_hint = _weight_band_range_text(result.weight_band)

    if result.output_unit == DosingOutputUnit.mg:
        strength = _format_decimal_es(result.output_value)
        presentation = result.rule_label or f"presentación de {strength} mg"
        main = (
            f"Para {subject} de {weight} kg, corresponde {wa_bold(product)} "
            f"en {wa_bold(presentation)}"
        )
        if range_hint:
            main += f" ({range_hint})"
        return f"{main}.\n\nSegún documentación validada Biomont."

    if result.output_unit == DosingOutputUnit.tablets:
        dose = _format_tablets_human(result.output_value)
        main = f"Para {subject} de {weight} kg, la dosis de {wa_bold(product)} es {wa_bold(dose)}"
        if range_hint:
            main += f" ({range_hint})"
        return f"{main}.\n\nSegún documentación validada Biomont."

    amount = _format_decimal_es(result.output_value)
    unit = result.output_unit.value
    main = (
        f"Para {subject} de {weight} kg, la dosis de {wa_bold(product)} "
        f"es {wa_bold(f'{amount} {unit}')}"
    )
    if range_hint:
        main += f" ({range_hint})"
    return f"{main}.\n\nSegún documentación validada Biomont."


def _format_formula_response(result: DoseCalculationResult) -> str:
    subject = _species_article(result.species)
    weight = _format_weight_kg(result.weight_kg)
    product = result.product_name
    rate = _formula_rate_text(result)

    if result.output_unit == DosingOutputUnit.tablets:
        dose = _format_tablets_human(result.output_value)
        main = f"Para {subject} de {weight} kg, la dosis de {wa_bold(product)} es {wa_bold(dose)}"
        if rate:
            main += f" ({rate})"
        return f"{main}.\n\nSegún documentación validada Biomont."

    if result.output_unit == DosingOutputUnit.ml:
        amount = _format_decimal_es(result.output_value)
        main = (
            f"Para {subject} de {weight} kg, administrar {wa_bold(f'{amount} ml')} "
            f"de {wa_bold(product)}"
        )
        if rate:
            main += f" ({rate})"
        return f"{main}.\n\nSegún documentación validada Biomont."

    amount = _format_decimal_es(result.output_value)
    main = (
        f"Para {subject} de {weight} kg, la dosis de {wa_bold(product)} "
        f"es {wa_bold(f'{amount} mg')}"
    )
    if rate:
        main += f" ({rate})"
    return f"{main}.\n\nSegún documentación validada Biomont."


def format_dose_response(result: DoseCalculationResult) -> str:
    """Plantilla legible para WhatsApp a partir del resultado determinista."""

    if result.rule_type == DosingRuleType.weight_band:
        return _format_weight_band_response(result)
    return _format_formula_response(result)
