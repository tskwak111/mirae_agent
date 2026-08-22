"""Safe structured runtime events."""

import logging
from collections.abc import Mapping

_LOGGER = logging.getLogger("finproof")


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
