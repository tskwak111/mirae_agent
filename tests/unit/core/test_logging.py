"""Structured request completion logging."""

import json
import logging
from typing import Any, cast

from finproof.api.app import create_app
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


def test_runtime_app_emits_one_redacted_structured_request_event(capsys: object) -> None:
    logger = logging.getLogger("finproof")
    original_handlers = logger.handlers[:]
    original_level = logger.level
    original_propagate = logger.propagate
    try:
        logger.handlers.clear()
        create_app()
        create_app()

        log_request_complete(
            correlation_id="corr-runtime",
            stage_latency_ms={"planner": 15_000, "wording": 15_000},
            candidate_counts={"raw": 0, "eligible": 0, "returned": 0},
            policy_ids=(),
            fallback="safe_failure",
            error_category="planner_retry_provider_failure",
        )

        captured = cast(Any, capsys).readouterr()
        lines = captured.err.splitlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event == {
            "candidate_counts": {"eligible": 0, "raw": 0, "returned": 0},
            "correlation_id": "corr-runtime",
            "error_category": "planner_retry_provider_failure",
            "event": "request_complete",
            "fallback": "safe_failure",
            "policy_ids": [],
            "stage_latency_ms": {"planner": 15_000, "wording": 15_000},
        }
        assert "question" not in captured.err
        assert "secret" not in captured.err
        assert "/Users/" not in captured.err
    finally:
        for handler in logger.handlers:
            if handler not in original_handlers:
                handler.close()
        logger.handlers[:] = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate
