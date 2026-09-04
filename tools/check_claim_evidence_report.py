"""Validate an immutable reviewed-suite claim/evidence score report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_AXES = {
    "aggregate_values",
    "answer_semantics",
    "assembled_envelope",
    "compatibility_partitions",
    "evidence_coverage",
    "filter_slots",
    "numeric_values",
    "plan_fields",
    "product_order",
    "product_set",
    "repeat_stability",
    "segment_assignment",
    "top_k_scope",
}
_BLIND_DEVELOPMENT_IDS = frozenset(
    f"CQ-{batch:03d}-{index:03d}" for batch in range(12, 18) for index in range(1, 25)
)


def _complete(score: Any) -> bool:
    return bool(
        isinstance(score, dict)
        and score.get("value") == 1.0
        and score.get("failures") == []
        and score.get("numerator") == score.get("denominator")
    )


def validate_report(path: Path) -> list[str]:
    try:
        report = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        return [f"report is unreadable: {type(error).__name__}"]
    if not isinstance(report, dict):
        return ["report root must be an object"]

    errors: list[str] = []
    aggregates = report.get("aggregates")
    if not isinstance(aggregates, dict) or set(aggregates) != _AXES:
        return ["aggregate score inventory differs"]
    for axis in sorted(_AXES):
        if not _complete(aggregates[axis]):
            errors.append(f"aggregate {axis} is incomplete")

    cases = report.get("case_scores")
    ids = (
        [case.get("case_id") for case in cases if isinstance(case, dict)]
        if isinstance(cases, list)
        else []
    )
    blind_development = (
        len(ids) == len(_BLIND_DEVELOPMENT_IDS)
        and all(type(case_id) is str for case_id in ids)
        and frozenset(ids) == _BLIND_DEVELOPMENT_IDS
    )
    suite_name = "blind development" if blind_development else "organizer"
    expected_count = len(_BLIND_DEVELOPMENT_IDS) if blind_development else 35
    if not isinstance(cases, list) or len(cases) != expected_count:
        errors.append(f"{suite_name} report must contain exactly {expected_count} case scores")
    else:
        if len(ids) != expected_count or len(set(ids)) != expected_count:
            errors.append(f"{suite_name} case IDs must be {expected_count} unique strings")
        for case in cases:
            if not isinstance(case, dict) or case.get("failures") != []:
                errors.append(f"{suite_name} case contains failures")
                break
            for axis in _AXES:
                if not _complete(case.get(axis)):
                    errors.append(f"case {case.get('case_id')} has incomplete {axis}")
                    break

    latency = report.get("latency")
    if not isinstance(latency, dict) or (
        latency.get("count"),
        latency.get("success_count"),
        latency.get("failure_count"),
    ) != (expected_count, expected_count, 0):
        errors.append(f"{suite_name} report must record {expected_count} successful executions")
    replay = report.get("replay")
    if not isinstance(replay, dict) or (
        replay.get("mode") != "deterministic-core"
        or replay.get("config_versions", {}).get("dataset_version") != "2026-08-24"
        or not isinstance(replay.get("artifact_version"), str)
        or len(replay["artifact_version"]) != 64
    ):
        errors.append(f"{suite_name} replay identity differs")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    errors = validate_report(args.report)
    sys.stdout.write(
        json.dumps({"errors": errors, "status": "passed" if not errors else "failed"}) + "\n"
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
