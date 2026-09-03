"""JSONL loader for canonical, category-split golden cases."""

import json
import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Self

from pydantic import model_validator

from finproof.domain.query_plan import Intent, QueryPlan
from finproof.evaluation.models import EvaluationCategory, GoldenCase

_BLIND_SUITES = {
    "blind_development": (frozenset(f"{number:03d}" for number in range(12, 18)), 144),
    "blind_holdout": (frozenset({"018", "019"}), 48),
}
_BLIND_CASE_ID = re.compile(r"^CQ-(\d{3})-\d{3}$")


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


def load_blind_suite(
    name: str,
    *,
    repository_root: Path | None = None,
) -> tuple[GoldenCase, ...]:
    """Load one reviewed blind suite with its fixed batch and case-count contract."""
    try:
        allowed_batches, expected_count = _BLIND_SUITES[name]
    except KeyError as exc:
        raise ValueError("unknown blind evaluation suite") from exc
    root = repository_root or Path(__file__).resolve().parents[3]
    try:
        cases = load_golden_cases(tuple(sorted((root / "evaluation" / name).glob("*.jsonl"))))
    except ValueError as exc:
        raise ValueError(f"{name.replace('_', ' ')} suite shape differs") from exc
    batches: set[str] = set()
    for case in cases:
        match = _BLIND_CASE_ID.fullmatch(case.case_id)
        if match is None:
            raise ValueError(f"{name.replace('_', ' ')} case ID differs")
        batches.add(match.group(1))
    if len(cases) != expected_count or batches != allowed_batches:
        raise ValueError(f"{name.replace('_', ' ')} suite shape differs")
    _reject_cross_suite_collisions(root, name, cases)
    return cases


def reject_draft_case_collisions(
    cases: Sequence[tuple[str, QueryPlan]],
    *,
    repository_root: Path,
) -> None:
    """Reject reviewed-suite question or declared-plan collisions before execution."""
    existing = _reviewed_suite_cases(repository_root)
    question_keys = {
        _normalized_question(case.question)
        for suite_cases in existing.values()
        for case in suite_cases
    }
    plan_keys = {
        _plan_signature(case.expected_plan.model_dump(mode="json", exclude_none=True))
        for suite_cases in existing.values()
        for case in suite_cases
    }
    for question, plan in cases:
        if _normalized_question(question) in question_keys:
            raise ValueError("draft case duplicates a reviewed normalized question")
        if _plan_signature(plan.model_dump(mode="json", exclude_none=True)) in plan_keys:
            raise ValueError("draft case duplicates a reviewed semantic plan")


def reject_promoted_case_collisions(
    cases: Sequence[GoldenCase],
    *,
    repository_root: Path,
    destination: str,
) -> None:
    """Reject cross-suite duplicates while allowing existing canonical review history."""
    _reject_cross_suite_collisions(repository_root, destination, cases)


def _reject_cross_suite_collisions(
    root: Path,
    destination: str,
    incoming: Sequence[GoldenCase],
) -> None:
    suites = _reviewed_suite_cases(root)
    suites[destination] = (*suites.get(destination, ()), *incoming)
    seen_questions: dict[str, str] = {}
    seen_plans: dict[str, str] = {}
    for name, cases in suites.items():
        for case in cases:
            label = f"{name}:{case.case_id}"
            question = _normalized_question(case.question)
            signature = _plan_signature(
                case.expected_plan.model_dump(mode="json", exclude_none=True)
            )
            if question in seen_questions and seen_questions[question].split(":", 1)[0] != name:
                raise ValueError("reviewed suites contain a duplicate normalized question")
            if signature in seen_plans and seen_plans[signature].split(":", 1)[0] != name:
                raise ValueError("reviewed suites contain a duplicate semantic plan")
            seen_questions[question] = label
            seen_plans[signature] = label


def _reviewed_suite_cases(root: Path) -> dict[str, tuple[GoldenCase, ...]]:
    suites: dict[str, tuple[GoldenCase, ...]] = {}
    canonical_paths = tuple(sorted((root / "evaluation/canonical").glob("*.jsonl")))
    if canonical_paths:
        suites["canonical"] = load_golden_cases(canonical_paths)
    organizer_dir = root / "evaluation/organizer_20260824"
    if tuple(sorted(path.name for path in organizer_dir.glob("*.jsonl"))) == (
        "easy.jsonl",
        "hard.jsonl",
        "medium.jsonl",
        "unanswerable.jsonl",
    ):
        suites["organizer_20260824"] = load_suite("organizer_20260824", repository_root=root)
    for name in _BLIND_SUITES:
        paths = tuple(sorted((root / "evaluation" / name).glob("*.jsonl")))
        if paths:
            suites[name] = load_golden_cases(paths)
    return suites


def _normalized_question(question: str) -> str:
    return " ".join(question.split()).casefold()


def _plan_signature(plan: Mapping[str, object]) -> str:
    normalized = {
        key: value for key, value in plan.items() if key not in {"entities", "native_segments"}
    }
    payload = json.dumps(
        normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return sha256(payload).hexdigest()


def suite_checksum(cases: Sequence[GoldenCase]) -> str:
    payload = [
        case.model_dump(mode="json") for case in sorted(cases, key=lambda item: item.case_id)
    ]
    return sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
