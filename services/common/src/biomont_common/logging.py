"""Configuracion de logging estructurado con structlog.

Cumple `.cursor/rules/logging-policy-observability.mdc`:
- formato JSON por defecto,
- nunca loguear secrets ni PII (responsabilidad del caller),
- `component`, `event` y `request_id` como keys minimas.
"""

from __future__ import annotations

import logging
import sys

import structlog

from biomont_common.settings import get_logging_settings

_CONFIGURED = False


def configure_logging(service_name: str) -> None:
    """Configura structlog y el logging stdlib para un servicio.

    Llamar una sola vez en el arranque del servicio.
    """

    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_logging_settings()
    level = logging.getLevelNamesMapping().get(
        settings.level.upper(), logging.INFO
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[
            *shared_processors,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.bind_contextvars(service=service_name)
    _CONFIGURED = True


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    """Devuelve un logger ya bound al `component`."""

    return structlog.get_logger().bind(component=component)
