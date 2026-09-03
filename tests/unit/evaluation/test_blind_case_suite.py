"""Blind-suite loading and isolation contracts."""

import json
from pathlib import Path

import pytest

from finproof.evaluation.loader import load_blind_suite

_ROOT = Path(__file__).resolve().parents[3]
_CASE = json.loads(
    (_ROOT / "evaluation/canonical/rank.jsonl").read_text(encoding="utf-8").splitlines()[0]
)


def _write_cases(root: Path, suite: str, batches: range) -> None:
    path = root / "evaluation" / suite / "rank.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    cases = []
    for batch in batches:
        for number in range(1, 25):
            cases.append(
                {
                    **_CASE,
                    "case_id": f"CQ-{batch:03d}-{number:03d}",
                    "question": f"{suite} {batch:03d} {number:03d}",
                }
            )
    path.write_text(
        "\n".join(json.dumps(case, ensure_ascii=False) for case in cases) + "\n",
        encoding="utf-8",
    )


def test_blind_suite_rejects_wrong_count_or_batch_range(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="blind development suite"):
        load_blind_suite("blind_development", repository_root=tmp_path)


def test_blind_development_accepts_only_the_exact_batch_shape(tmp_path: Path) -> None:
    _write_cases(tmp_path, "blind_development", range(12, 18))

    cases = load_blind_suite("blind_development", repository_root=tmp_path)

    assert len(cases) == 144
    assert {case.case_id.split("-")[1] for case in cases} == {
        "012",
        "013",
        "014",
        "015",
        "016",
        "017",
    }


def test_blind_holdout_accepts_only_the_exact_batch_shape(tmp_path: Path) -> None:
    _write_cases(tmp_path, "blind_holdout", range(18, 20))

    cases = load_blind_suite("blind_holdout", repository_root=tmp_path)

    assert len(cases) == 48
    assert {case.case_id.split("-")[1] for case in cases} == {"018", "019"}


def test_blind_suite_rejects_malformed_case_id_before_batch_comparison(tmp_path: Path) -> None:
    _write_cases(tmp_path, "blind_development", range(12, 18))
    path = tmp_path / "evaluation/blind_development/rank.jsonl"
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    cases[0]["case_id"] = "CQ-012-not-a-case"
    path.write_text(
        "\n".join(json.dumps(case, ensure_ascii=False) for case in cases) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="case ID"):
        load_blind_suite("blind_development", repository_root=tmp_path)


def test_blind_suite_rejects_normalized_question_collision_with_canonical(tmp_path: Path) -> None:
    _write_cases(tmp_path, "blind_development", range(12, 18))
    canonical = tmp_path / "evaluation/canonical/rank.jsonl"
    canonical.parent.mkdir(parents=True)
    duplicate = {**_CASE, "case_id": "CANONICAL-001", "question": "동일   질문"}
    canonical.write_text(json.dumps(duplicate, ensure_ascii=False) + "\n", encoding="utf-8")
    path = tmp_path / "evaluation/blind_development/rank.jsonl"
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    cases[0]["question"] = "동일\n질문"
    path.write_text(
        "\n".join(json.dumps(case, ensure_ascii=False) for case in cases) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="normalized question"):
        load_blind_suite("blind_development", repository_root=tmp_path)


def test_blind_suite_rejects_semantic_plan_collision_with_organizer(tmp_path: Path) -> None:
    _write_cases(tmp_path, "blind_development", range(12, 18))
    organizer = tmp_path / "evaluation/organizer_20260824"
    organizer.mkdir(parents=True)
    for difficulty in ("easy", "medium", "hard", "unanswerable"):
        case = {
            **_CASE,
            "case_id": f"ORGANIZER-{difficulty}",
            "question": f"organizer {difficulty}",
            "difficulty": difficulty,
            "coverage_tags": ["boundary"],
        }
        if difficulty == "unanswerable":
            case["expected_plan"] = {
                **case["expected_plan"],
                "intent": "unsupported",
                "product_types": [],
                "filters": None,
                "metrics": None,
                "sort": None,
                "top_k": None,
                "needs_clarification": False,
                "clarification_reason": "지원하지 않는 요청입니다.",
                "native_segments": [],
            }
        (organizer / f"{difficulty}.jsonl").write_text(
            json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    with pytest.raises(ValueError, match="semantic plan"):
        load_blind_suite("blind_development", repository_root=tmp_path)
