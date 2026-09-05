"""Safe structured runtime events."""

import json
import logging
from collections.abc import Mapping

_LOGGER = logging.getLogger("finproof")
_HANDLER_NAME = "finproof-structured"
_EVENT_FIELDS = (
    "event",
    "correlation_id",
    "stage_latency_ms",
    "candidate_counts",
    "policy_ids",
    "fallback",
    "error_category",
    "exception_type",
    "provider_request_id",
    "provider_error_kind",
    "provider_error_detail",
    "validation_stage",
    "canonical_substage",
    "canonical_path",
    "canonical_keyword",
    "semantic_reason_code",
    "semantic_detail",
    "registry_field_id",
)


class _StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = {field: getattr(record, field) for field in _EVENT_FIELDS if hasattr(record, field)}
        event.setdefault("event", record.getMessage())
        return json.dumps(
            event,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


def configure_runtime_logging() -> None:
    """Attach one redacted structured handler for Docker/Uvicorn runtime logs."""
    if any(handler.get_name() == _HANDLER_NAME for handler in _LOGGER.handlers):
        return
    handler = logging.StreamHandler()
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(_StructuredFormatter())
    _LOGGER.addHandler(handler)
    _LOGGER.setLevel(logging.INFO)


def log_hcx_provider_failure(
    *, provider_request_id: str, provider_error_kind: str, provider_error_detail: str
) -> None:
    """Record only allowlisted provider-boundary failure metadata."""
    _LOGGER.info(
        "hcx_provider_failure",
        extra={
            "event": "hcx_provider_failure",
            "provider_request_id": provider_request_id,
            "provider_error_kind": provider_error_kind,
            "provider_error_detail": provider_error_detail,
        },
    )


def log_hcx_output_invalid(
    *,
    provider_request_id: str,
    validation_stage: str,
    canonical_substage: str | None = None,
    canonical_path: str | None = None,
    canonical_keyword: str | None = None,
    semantic_reason_code: str | None = None,
    semantic_detail: str | None = None,
    registry_field_id: str | None = None,
) -> None:
    """Record the local validation stage without provider content."""
    _LOGGER.info(
        "hcx_output_invalid",
        extra={
            "event": "hcx_output_invalid",
            "provider_request_id": provider_request_id,
            "validation_stage": validation_stage,
            "canonical_substage": canonical_substage,
            "canonical_path": canonical_path,
            "canonical_keyword": canonical_keyword,
            "semantic_reason_code": semantic_reason_code,
            "semantic_detail": semantic_detail,
            "registry_field_id": registry_field_id,
        },
    )


def log_request_complete(
    *,
    correlation_id: str,
    stage_latency_ms: Mapping[str, int],
    candidate_counts: Mapping[str, int],
    policy_ids: tuple[str, ...],
    fallback: str | None,
    error_category: str | None,
) -> None:
    """Emit only reviewed request metadata; callers never supply raw request data."""
    _LOGGER.info(
        "request_complete",
        extra={
            "event": "request_complete",
            "correlation_id": correlation_id,
            "stage_latency_ms": dict(stage_latency_ms),
            "candidate_counts": dict(candidate_counts),
            "policy_ids": policy_ids,
            "fallback": fallback,
            "error_category": error_category,
        },
    )
