"""Structured request completion logging."""

import json
import logging
from typing import Any, cast

from finproof.core.logging import log_request_complete


def test_request_log_is_structured_and_redacted(caplog: object) -> None:
    capture = cast(Any, caplog)
    capture.set_level(logging.INFO, logger="finproof")

    log_request_complete(
        correlation_id="corr-1",
        stage_latency_ms={"planner": 1, "database": 2, "evidence": 3, "render": 4},
        candidate_counts={"raw": 1, "eligible": 1, "returned": 1},
        policy_ids=("answer:1.0.0",),
        fallback="rule_fallback",
        error_category="timeout",
    )

    record = capture.records[-1]
    fields = cast(dict[str, object], record.__dict__)
    event = {
        key: fields[key]
        for key in fields
        if key
        in {
            "event",
            "correlation_id",
            "stage_latency_ms",
            "candidate_counts",
            "policy_ids",
            "fallback",
            "error_category",
        }
    }
    assert event["event"] == "request_complete"
    assert event["correlation_id"] == "corr-1"
    assert set(cast(dict[str, int], event["stage_latency_ms"])) == {
        "planner",
        "database",
        "evidence",
        "render",
    }
    serialized = json.dumps(event, ensure_ascii=False, default=str)
    assert "미국 ETF 총보수 알려줘" not in serialized
    assert "secret" not in serialized
    assert "/Users/" not in serialized
