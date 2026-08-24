"""JSONL loader for canonical, category-split golden cases."""

import json
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

from finproof.evaluation.models import EvaluationCategory, GoldenCase


def load_golden_cases(paths: Sequence[Path]) -> tuple[GoldenCase, ...]:
    if not paths:
        raise ValueError("at least one golden JSONL path is required")
    cases: list[GoldenCase] = []
    seen: set[str] = set()
    for path in paths:
        if path.suffix != ".jsonl" or not path.is_file():
            raise ValueError(f"golden case path is not a JSONL file: {path}")
        file_categories: set[EvaluationCategory] = set()
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                case = GoldenCase.model_validate_json(line)
            except ValueError as error:
                raise ValueError(f"invalid golden case at {path}:{line_number}") from error
            if case.review.reviewer == "AI-handoff-seed":
                raise ValueError(
                    f"AI-handoff-seed is not a canonical reviewer: {path}:{line_number}"
                )
            if case.case_id in seen:
                raise ValueError(f"duplicate golden case id: {case.case_id}")
            seen.add(case.case_id)
            file_categories.add(case.category)
            cases.append(case)
        if len(file_categories) > 1:
            raise ValueError(f"golden JSONL must contain one category: {path}")
    if not cases:
        raise ValueError("golden suite is empty")
    return tuple(cases)


def suite_checksum(cases: Sequence[GoldenCase]) -> str:
    payload = [
        case.model_dump(mode="json") for case in sorted(cases, key=lambda item: item.case_id)
    ]
    return sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
