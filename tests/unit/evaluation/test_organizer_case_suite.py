"""Official 2026-08-24 organizer-suite shape contracts."""

import json
from collections import Counter
from datetime import date
from pathlib import Path

import pytest
from tools import promote_organizer_reference_packet as promotion

from finproof.evaluation import loader

_ROOT = Path(__file__).resolve().parents[3]
_REVIEW = _ROOT / "evaluation/organizer_20260824/review"


def _promotion_workspace(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repository = tmp_path / "repository"
    review = repository / "evaluation/organizer_20260824/review"
    review.mkdir(parents=True)
    reference = review / "expected-review-v3.json"
    approval = review / "expected-approval-v3.json"
    reference.write_bytes((_REVIEW / reference.name).read_bytes())
    approval.write_bytes((_REVIEW / approval.name).read_bytes())
    return repository, reference, approval, review.parent


def test_promotes_only_the_exact_human_approved_organizer_reference(
    tmp_path: Path,
) -> None:
    repository, reference, approval, output = _promotion_workspace(tmp_path)

    promotion.promote_organizer_reference_packet(
        reference,
        approval,
        output,
        repository_root=repository,
    )

    cases = loader.load_suite("organizer_20260824", repository_root=repository)
    assert len(cases) == 35
    assert {path.name for path in output.glob("*.jsonl")} == {
        "easy.jsonl",
        "medium.jsonl",
        "hard.jsonl",
        "unanswerable.jsonl",
    }
    assert {case.review.reviewer for case in cases} == {"곽태성"}
    assert all("sha256:859602d7" in case.review.source for case in cases)
    holding = next(case for case in cases if case.case_id == "ORG-20260824-H-001")
    assert [segment.product_type.value for segment in holding.expected_plan.native_segments] == [
        "domestic_etf",
        "public_fund",
    ]


def test_rejects_an_unapproved_organizer_reference_without_partial_output(
    tmp_path: Path,
) -> None:
    repository, reference, approval, output = _promotion_workspace(tmp_path)
    record = json.loads(approval.read_text(encoding="utf-8"))
    record["expected_reference_packet_sha256"] = "0" * 64
    approval.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="approval status or checksum differs"):
        promotion.promote_organizer_reference_packet(
            reference,
            approval,
            output,
            repository_root=repository,
        )

    assert not tuple(output.glob("*.jsonl"))


def test_organizer_suite_has_exact_announced_shape_and_required_boundaries() -> None:
    cases = loader.load_suite("organizer_20260824")

    assert Counter(case.difficulty for case in cases) == {
        "easy": 10,
        "medium": 10,
        "hard": 10,
        "unanswerable": 5,
    }
    assert len(cases) == 35
    assert all(case.expected_plan.as_of_date == date(2026, 8, 24) for case in cases)
    assert {
        "constituent_cross_product",
        "holding_coverage_unavailable",
        "code_table_unsupported",
        "overseas_return_1y_pruned",
        "missing_zero_policy",
        "buyable_quantity_ignored",
    } <= {tag for case in cases for tag in case.coverage_tags}
    assert all(
        "buyable_quantity"
        not in {
            *(clause.field for clause in case.expected_plan.filters or ()),
            *(case.expected_plan.metrics or ()),
            *(item.field for item in case.expected_plan.sort or ()),
            *(
                (case.expected_plan.aggregation.field,)
                if case.expected_plan.aggregation is not None
                and case.expected_plan.aggregation.field is not None
                else ()
            ),
        }
        for case in cases
    )
