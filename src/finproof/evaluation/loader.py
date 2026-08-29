"""JSONL loader for canonical, category-split golden cases."""

import json
from collections.abc import Sequence
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Self

from pydantic import model_validator

from finproof.domain.query_plan import Intent
from finproof.evaluation.models import EvaluationCategory, GoldenCase


class OrganizerDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    UNANSWERABLE = "unanswerable"


class OrganizerCase(GoldenCase):
    difficulty: OrganizerDifficulty
    coverage_tags: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_organizer_metadata(self) -> Self:
        if not self.coverage_tags or any(not tag.strip() for tag in self.coverage_tags):
            raise ValueError("organizer coverage tags cannot be empty")
        if len(set(self.coverage_tags)) != len(self.coverage_tags):
            raise ValueError("organizer coverage tags must be unique")
        terminal = self.expected_plan.intent in {Intent.CLARIFY, Intent.UNSUPPORTED}
        if (self.difficulty is OrganizerDifficulty.UNANSWERABLE) is not terminal:
            raise ValueError("unanswerable difficulty must match a terminal plan")
        return self


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


def load_suite(
    name: str,
    *,
    repository_root: Path | None = None,
) -> tuple[OrganizerCase, ...]:
    if name != "organizer_20260824":
        raise ValueError("unknown evaluation suite")
    root = repository_root or Path(__file__).resolve().parents[3]
    directory = root / "evaluation" / name
    paths = tuple(sorted(directory.glob("*.jsonl")))
    if tuple(path.name for path in paths) != (
        "easy.jsonl",
        "hard.jsonl",
        "medium.jsonl",
        "unanswerable.jsonl",
    ):
        raise ValueError("organizer suite files differ")
    cases: list[OrganizerCase] = []
    seen: set[str] = set()
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                case = OrganizerCase.model_validate_json(line)
            except ValueError as error:
                raise ValueError(f"invalid organizer case at {path}:{line_number}") from error
            if case.difficulty.value != path.stem:
                raise ValueError(f"organizer difficulty file differs: {path}:{line_number}")
            if case.review.reviewer == "AI-handoff-seed":
                raise ValueError(f"organizer case lacks human review: {path}:{line_number}")
            if case.case_id in seen:
                raise ValueError(f"duplicate organizer case id: {case.case_id}")
            seen.add(case.case_id)
            cases.append(case)
    if not cases:
        raise ValueError("organizer suite is empty")
    return tuple(cases)


def suite_checksum(cases: Sequence[GoldenCase]) -> str:
    payload = [
        case.model_dump(mode="json") for case in sorted(cases, key=lambda item: item.case_id)
    ]
    return sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
