"""Focused trust-boundary tests for reviewed reference promotion."""

import importlib
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from finproof.domain.query_plan import QueryPlan
from finproof.evaluation.loader import load_golden_cases
from finproof.evaluation.scoring import score_filters

_ROOT = Path(__file__).resolve().parents[3]
_REFERENCE = _ROOT / "evaluation/review_batches/batch-001-reference-review.json"
_APPROVAL = _ROOT / "evaluation/review_batches/batch-001-reference-approval.json"
_BATCH_TWO_REFERENCE = _ROOT / "evaluation/review_batches/batch-002-reference-review.json"
_BATCH_TWO_APPROVAL = _ROOT / "evaluation/review_batches/batch-002-reference-approval.json"
_BATCH_THREE_REFERENCE = _ROOT / "evaluation/review_batches/batch-003-reference-review.json"
_BATCH_THREE_APPROVAL = _ROOT / "evaluation/review_batches/batch-003-reference-approval.json"
_BATCH_FOUR_REFERENCE = _ROOT / "evaluation/review_batches/batch-004-reference-review.json"
_BATCH_FOUR_APPROVAL = _ROOT / "evaluation/review_batches/batch-004-reference-approval.json"
_BATCH_FIVE_REFERENCE = _ROOT / "evaluation/review_batches/batch-005-reference-review.json"
_BATCH_FIVE_APPROVAL = _ROOT / "evaluation/review_batches/batch-005-reference-approval.json"
_OFFICIAL = _ROOT / "evaluation/canonical/clarification.jsonl"


def _promotion() -> object:
    return importlib.import_module("tools.promote_canonical_reference_packet")


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repository = tmp_path / "repository"
    review = repository / "evaluation/review_batches"
    canonical = repository / "evaluation/canonical"
    review.mkdir(parents=True)
    canonical.mkdir(parents=True)
    reference = review / _REFERENCE.name
    approval = review / _APPROVAL.name
    reference.write_bytes(_REFERENCE.read_bytes())
    approval.write_bytes(_APPROVAL.read_bytes())
    (canonical / "clarification.jsonl").write_bytes(
        _OFFICIAL.read_bytes().splitlines(keepends=True)[0]
    )
    return repository, reference, approval, canonical


def _promote(repository: Path, reference: Path, approval: Path, canonical: Path) -> None:
    module = _promotion()
    module.promote_reference_packet(  # type: ignore[attr-defined]
        reference,
        approval,
        canonical,
        repository_root=repository,
    )


def _write_packet(reference: Path, approval: Path, payload: dict[str, object]) -> None:
    raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    reference.write_bytes(raw)
    approval_payload = json.loads(approval.read_text(encoding="utf-8"))
    approval_payload["reference_packet_sha256"] = sha256(raw).hexdigest()
    approval.write_text(
        json.dumps(approval_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_promotes_exact_approved_packet_and_preserves_existing_case(tmp_path: Path) -> None:
    repository, reference, approval, canonical = _workspace(tmp_path)
    official = (canonical / "clarification.jsonl").read_bytes()

    _promote(repository, reference, approval, canonical)

    paths = tuple(sorted(canonical.glob("*.jsonl")))
    cases = load_golden_cases(paths)
    assert len(cases) == 25
    assert len({case.case_id for case in cases}) == 25
    assert (canonical / "clarification.jsonl").read_bytes().startswith(official)
    assert {path.stem for path in paths} == {
        "aggregate",
        "clarification",
        "compare",
        "cross_product",
        "lookup",
        "quality",
        "rank",
        "screen",
    }
    assert all(
        {case.category.value for case in load_golden_cases((path,))} == {path.stem}
        for path in paths
    )

    by_id = {case.case_id: case for case in cases}
    rank = by_id["CQ-001-RANK-001"]
    assert tuple(product.product_id for product in rank.expected_result.products) == (
        "KR7243880002",
        "KR7494310006",
        "KR7488080003",
    )
    assert rank.expected_result.order_matters is True
    assert [value.model_dump(mode="json") for value in rank.expected_result.values[:2]] == [
        {
            "product_id": "KR7243880002",
            "field_id": "return_ytd",
            "value_type": "decimal",
            "value": "701.69",
            "display_tolerance": "0",
        },
        {
            "product_id": "KR7494310006",
            "field_id": "return_ytd",
            "value_type": "decimal",
            "value": "508.10",
            "display_tolerance": "0",
        },
    ]
    assert rank.expected_result.required_evidence_ids[:2] == (
        "domestic_etf:KR7243880002:product_id",
        "domestic_etf:KR7243880002:return_ytd",
    )
    assert rank.expected_answer.required_concepts == (
        "2026-07-11 제공 스냅샷 기준",
        "일부 지표값은 비교 가능 기준에서 제외했습니다.",
    )
    assert rank.expected_answer.forbidden_concepts == ("실시간",)

    aggregate = by_id["CQ-001-AGGREGATE-001"]
    assert aggregate.expected_result.products == ()
    assert aggregate.expected_result.aggregates[0].model_dump(mode="json") == {
        "function": "count",
        "field_id": None,
        "product_type": "domestic_etf",
        "native_result_grain": "listed_product",
        "partition_key": "count:listed_product:domestic_etf",
        "group_values": [],
        "value_type": "integer",
        "value": 1139,
    }

    cross_product = by_id["CQ-001-CROSS_PRODUCT-001"]
    assert len(cross_product.expected_plan.native_segments) == 2
    assert cross_product.expected_result.assembled_envelope is True
    assert cross_product.expected_result.required_compatibility_partitions == (
        "historical_total_return:None:1m:same_period_and_compatible_source_semantics",
    )

    clarification = by_id["CQ-001-CLARIFICATION-001"]
    assert (
        clarification.expected_plan.clarification_reason
        == clarification.expected_answer.required_concepts[0]
    )
    assert clarification.expected_answer.expect_clarification is True
    assert clarification.expected_answer.expect_limitation is True
    source = rank.review.source
    assert "sha256:4db47c4dfcb0ea63a32c70cd5883e4d6e695f0219bffba9a67c336876d2655d8" in source
    assert "artifact_set_id=finproof-data-artifacts/v1" in source
    assert (
        "manifest_logical_hash=59d8b566b7f3e8986b5c46ae2bebfe2325e7ae12d29ba5d663299fb5ebded236"
        in source
    )


def test_promotes_later_canonical_reference_approval_date(tmp_path: Path) -> None:
    repository, reference, approval, canonical = _workspace(tmp_path)
    payload = json.loads(approval.read_text(encoding="utf-8"))
    payload["reviewed_at"] = "2026-08-25"
    approval.write_text(json.dumps(payload), encoding="utf-8")

    _promote(repository, reference, approval, canonical)

    cases = load_golden_cases(tuple(sorted(canonical.glob("*.jsonl"))))
    promoted = [case for case in cases if case.case_id.startswith("CQ-001-")]
    assert len(promoted) == 24
    assert {case.review.reviewed_at.isoformat() for case in promoted} == {"2026-08-25"}


def test_accepts_repeated_compatibility_segments_but_rejects_reordered_products(
    tmp_path: Path,
) -> None:
    repository, reference, approval, canonical = _workspace(tmp_path)
    payload = json.loads(reference.read_text(encoding="utf-8"))
    cases = cast(list[dict[str, object]], payload["cases"])
    cross_product = next(case for case in cases if case["case_id"] == "CQ-001-CROSS_PRODUCT-001")
    trace = cast(dict[str, object], cross_product["trace"])
    segments = cast(list[dict[str, object]], trace["segments"])
    segments.append(dict(segments[0]))
    _write_packet(reference, approval, payload)

    _promote(repository, reference, approval, canonical)

    before = {path.name: path.read_bytes() for path in canonical.iterdir()}
    segments[:] = [segments[1], segments[0], segments[2]]
    _write_packet(reference, approval, payload)
    with pytest.raises(ValueError, match="segment assignment"):
        _promote(repository, reference, approval, canonical)
    assert {path.name: path.read_bytes() for path in canonical.iterdir()} == before


def test_promotes_decimal_filters_with_stable_scoring_keys(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    review = repository / "evaluation/review_batches"
    canonical = repository / "evaluation/canonical"
    review.mkdir(parents=True)
    reference = review / _BATCH_TWO_REFERENCE.name
    approval = review / _BATCH_TWO_APPROVAL.name
    reference.write_bytes(_BATCH_TWO_REFERENCE.read_bytes())
    approval.write_bytes(_BATCH_TWO_APPROVAL.read_bytes())

    _promote(repository, reference, approval, canonical)

    cases = load_golden_cases(tuple(sorted(canonical.glob("*.jsonl"))))
    promoted = next(case for case in cases if case.case_id == "CQ-002-SCREEN-003")
    source = next(
        case
        for case in json.loads(_BATCH_TWO_REFERENCE.read_text(encoding="utf-8"))["cases"]
        if case["case_id"] == promoted.case_id
    )
    observed_plan = QueryPlan.model_validate_json(json.dumps(source["plan"]))
    assert score_filters(promoted.expected_plan.filters or (), observed_plan.filters).value == 1


def test_promotes_dual_count_answer_claims(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    review = repository / "evaluation/review_batches"
    canonical = repository / "evaluation/canonical"
    review.mkdir(parents=True)
    reference = review / _BATCH_THREE_REFERENCE.name
    approval = review / _BATCH_THREE_APPROVAL.name
    reference.write_bytes(_BATCH_THREE_REFERENCE.read_bytes())
    approval.write_bytes(_BATCH_THREE_APPROVAL.read_bytes())

    _promote(repository, reference, approval, canonical)

    promoted = next(
        case
        for case in load_golden_cases(tuple(sorted(canonical.glob("*.jsonl"))))
        if case.case_id == "CQ-003-022"
    )
    assert {
        "원천 기록 기준 상품 개수: 325",
        "domestic_bond/instrument [count:instrument:domestic_bond] 상태 검증 후 상품 개수: 254",
    } <= set(promoted.expected_answer.required_concepts)


def test_promotes_approved_synthetic_integer_evidence(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    review = repository / "evaluation/review_batches"
    canonical = repository / "evaluation/canonical"
    review.mkdir(parents=True)
    reference = review / _BATCH_FOUR_REFERENCE.name
    approval = review / _BATCH_FOUR_APPROVAL.name
    reference.write_bytes(_BATCH_FOUR_REFERENCE.read_bytes())
    approval.write_bytes(_BATCH_FOUR_APPROVAL.read_bytes())

    _promote(repository, reference, approval, canonical)

    promoted = next(
        case
        for case in load_golden_cases(tuple(sorted(canonical.glob("*.jsonl"))))
        if case.case_id == "CQ-004-014"
    )
    difference = next(
        value
        for value in promoted.expected_result.values
        if value.field_id == "remaining_days_difference"
    )
    assert difference.value_type.value == "integer"
    assert difference.value == 90


def test_promotes_batch_five_approved_boundaries(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    review = repository / "evaluation/review_batches"
    canonical = repository / "evaluation/canonical"
    review.mkdir(parents=True)
    canonical.mkdir(parents=True)
    reference = review / _BATCH_FIVE_REFERENCE.name
    approval = review / _BATCH_FIVE_APPROVAL.name
    reference.write_bytes(_BATCH_FIVE_REFERENCE.read_bytes())
    approval.write_bytes(_BATCH_FIVE_APPROVAL.read_bytes())

    _promote(repository, reference, approval, canonical)

    cases = load_golden_cases(tuple(sorted(canonical.glob("*.jsonl"))))
    assert len(cases) == len({case.case_id for case in cases}) == 24
    assert Counter(case.category.value for case in cases) == {
        "aggregate": 2,
        "clarification": 1,
        "compare": 3,
        "cross_product": 2,
        "lookup": 4,
        "quality": 3,
        "rank": 4,
        "screen": 5,
    }
    assert {case.review.reviewer for case in cases} == {"곽태성"}
    assert {case.review.reviewed_at.isoformat() for case in cases} == {"2026-08-26"}
    assert all(
        "batch-005-reference-review.json "
        "sha256:dce110eed040f0fda0c26ced2ba5726d8f0a0c3e0584c63ff6ceb99d1eb04e3d"
        in case.review.source
        for case in cases
    )

    by_id = {case.case_id: case for case in cases}
    lookup_values = {
        (value.field_id, str(value.value)) for value in by_id["CQ-005-001"].expected_result.values
    }
    assert {("credit_rating", "AAA"), ("maturity_date", "2031-07-21")} <= lookup_values

    comparison = by_id["CQ-005-014"]
    assert [
        (value.product_id, value.value)
        for value in comparison.expected_result.values
        if value.field_id == "credit_rating"
    ] == [("KR350105G9C6", "AAA"), ("KR350901G671", "AAA")]
    assert {
        "domestic_bond:KR350105G9C6:credit_rating",
        "domestic_bond:KR350901G671:credit_rating",
    } <= set(comparison.expected_result.required_evidence_ids)

    cross_product = by_id["CQ-005-020"]
    assert {
        segment.product_type.value for segment in cross_product.expected_plan.native_segments
    } == {
        "domestic_etn",
        "overseas_etn",
    }
    assert [
        (product.product_type.value, product.product_id)
        for product in cross_product.expected_result.products
    ] == [
        ("overseas_etn", "VYLD.K"),
        ("overseas_etn", "AIQD.K"),
        ("overseas_etn", "AIQU.K"),
    ]

    missing_returns = by_id["CQ-005-024"]
    assert missing_returns.expected_plan.result_grain.value == "fund_item"
    assert len(missing_returns.expected_result.aggregates) == 1
    assert missing_returns.expected_result.aggregates[0].value == 4259
    assert missing_returns.expected_result.aggregates[0].native_result_grain.value == "fund_item"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reference_packet_sha256", "0" * 64),
        ("review_status", "pending_human_review"),
        ("reviewer", "someone-else"),
        ("batch_id", "002"),
    ],
)
def test_rejects_wrong_approval_binding_before_writing(
    field: str,
    value: str,
    tmp_path: Path,
) -> None:
    repository, reference, approval, canonical = _workspace(tmp_path)
    payload = json.loads(approval.read_text(encoding="utf-8"))
    payload[field] = value
    approval.write_text(json.dumps(payload), encoding="utf-8")
    before = {path.name: path.read_bytes() for path in canonical.iterdir()}

    with pytest.raises(ValueError, match=r"approval|checksum"):
        _promote(repository, reference, approval, canonical)

    assert {path.name: path.read_bytes() for path in canonical.iterdir()} == before


@pytest.mark.parametrize("invalid", ["missing-field", "malformed", "duplicate-key"])
def test_rejects_inexact_json_before_writing(invalid: str, tmp_path: Path) -> None:
    repository, reference, approval, canonical = _workspace(tmp_path)
    if invalid == "missing-field":
        payload = json.loads(approval.read_text(encoding="utf-8"))
        del payload["reviewer"]
        approval.write_text(json.dumps(payload), encoding="utf-8")
    else:
        raw = (
            b"{"
            if invalid == "malformed"
            else reference.read_bytes().replace(
                b'"batch_id": "001",',
                b'"batch_id": "001",\n  "batch_id": "001",',
                1,
            )
        )
        reference.write_bytes(raw)
        approval_payload = json.loads(approval.read_text(encoding="utf-8"))
        approval_payload["reference_packet_sha256"] = sha256(raw).hexdigest()
        approval.write_text(json.dumps(approval_payload), encoding="utf-8")
    before = {path.name: path.read_bytes() for path in canonical.iterdir()}

    with pytest.raises(ValueError, match=r"approval|JSON"):
        _promote(repository, reference, approval, canonical)

    assert {path.name: path.read_bytes() for path in canonical.iterdir()} == before


def test_rejects_duplicate_packet_or_canonical_case_id_before_writing(tmp_path: Path) -> None:
    repository, reference, approval, canonical = _workspace(tmp_path)
    payload = json.loads(reference.read_text(encoding="utf-8"))
    cases = cast(list[dict[str, object]], payload["cases"])
    cases[1]["case_id"] = cases[0]["case_id"]
    _write_packet(reference, approval, payload)
    before = {path.name: path.read_bytes() for path in canonical.iterdir()}

    with pytest.raises(ValueError, match="duplicate"):
        _promote(repository, reference, approval, canonical)

    assert {path.name: path.read_bytes() for path in canonical.iterdir()} == before

    reference.write_bytes(_REFERENCE.read_bytes())
    approval.write_bytes(_APPROVAL.read_bytes())
    duplicate = json.loads(_OFFICIAL.read_text(encoding="utf-8").splitlines()[0])
    duplicate["case_id"] = "CQ-001-RANK-001"
    (canonical / "rank.jsonl").write_text(json.dumps(duplicate) + "\n", encoding="utf-8")
    before = {path.name: path.read_bytes() for path in canonical.iterdir()}
    with pytest.raises(ValueError, match="duplicate"):
        _promote(repository, reference, approval, canonical)
    assert {path.name: path.read_bytes() for path in canonical.iterdir()} == before


def test_rejects_reference_outside_review_batch_before_writing(tmp_path: Path) -> None:
    repository, reference, approval, canonical = _workspace(tmp_path)
    unsafe = repository / reference.name
    unsafe.write_bytes(reference.read_bytes())

    with pytest.raises(ValueError, match="review_batches"):
        _promote(repository, unsafe, approval, canonical)

    assert tuple(canonical.glob("*.jsonl")) == (canonical / "clarification.jsonl",)
