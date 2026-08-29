"""Parity checks for Phase 2 canonical JSON schemas."""

import json
from datetime import date
from pathlib import Path, PurePosixPath

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from finproof.domain.query_plan import QueryPlan

ROOT = Path(__file__).resolve().parents[2]


def _base_plan() -> dict[str, object]:
    return {
        "intent": "screen",
        "product_types": ["domestic_bond"],
        "entities": [],
        "as_of_date": "2026-07-11",
        "result_grain": "instrument",
        "filters": [],
        "metrics": ["buy_yield"],
        "metric_targets": [],
        "sort": [],
        "aggregation": None,
        "top_k": 5,
        "top_k_scope": "global",
        "needs_clarification": False,
        "clarification_reason": "",
    }


@pytest.mark.parametrize(
    ("mutation", "accepted"),
    [
        pytest.param({}, True, id="screen"),
        pytest.param(
            {
                "filters": [
                    {"field": "rating", "operator": "eq", "value": "AA-"},
                    {"field": "market", "operator": "in", "value": ["KOSPI"]},
                    {"field": "yield", "operator": "between", "value": [1, 2]},
                    {"field": "fee", "operator": "is_missing"},
                ]
            },
            True,
            id="filter-variants",
        ),
        pytest.param(
            {
                "intent": "aggregate",
                "aggregation": {"function": "count", "field": None, "group_by": []},
            },
            True,
            id="aggregate",
        ),
        pytest.param(
            {
                "intent": "clarify",
                "product_types": [],
                "result_grain": "product",
                "metrics": [],
                "needs_clarification": True,
                "clarification_reason": "기간이 필요합니다.",
            },
            True,
            id="clarify",
        ),
        pytest.param(
            {
                "product_types": ["domestic_bond", "public_fund"],
                "result_grain": "product",
            },
            True,
            id="heterogeneous-envelope",
        ),
        pytest.param(
            {
                "intent": "screen_rank",
                "product_types": ["domestic_bond", "public_fund"],
                "result_grain": "product",
                "metrics": ["buy_yield", "return_1y"],
                "metric_targets": [
                    {"product_type": "domestic_bond", "metrics": ["buy_yield"]},
                    {"product_type": "public_fund", "metrics": ["return_1y"]},
                ],
                "top_k_scope": "per_product_type",
            },
            True,
            id="explicit-metric-targets",
        ),
        pytest.param({"sql": "select 1"}, False, id="extra"),
        pytest.param(
            {"product_types": ["domestic_bond", "domestic_bond"]},
            False,
            id="duplicate-products",
        ),
        pytest.param({"as_of_date": "2026-13-40"}, False, id="date"),
        pytest.param({"top_k": 0}, False, id="top-k-low"),
        pytest.param({"top_k": 51}, False, id="top-k-high"),
        pytest.param(
            {"filters": [{"field": "x", "operator": "eq"}]},
            False,
            id="scalar-value-missing",
        ),
        pytest.param(
            {"filters": [{"field": "x", "operator": "is_missing", "value": None}]},
            False,
            id="missing-value-present",
        ),
        pytest.param(
            {"filters": [{"field": "x", "operator": "between", "value": [1]}]},
            False,
            id="range-arity",
        ),
        pytest.param(
            {"intent": "aggregate", "aggregation": None},
            False,
            id="aggregate-missing",
        ),
        pytest.param(
            {
                "intent": "clarify",
                "product_types": [],
                "result_grain": "product",
                "metrics": [],
                "needs_clarification": True,
                "clarification_reason": "",
            },
            False,
            id="clarify-empty-reason",
        ),
        pytest.param({"result_grain": "product"}, False, id="single-product-envelope"),
        pytest.param(
            {
                "product_types": ["domestic_bond", "public_fund"],
                "result_grain": "instrument",
            },
            False,
            id="heterogeneous-native-grain",
        ),
    ],
)
def test_query_plan_json_schema_and_pydantic_accept_and_reject_the_same_fixture_family(
    mutation: dict[str, object],
    accepted: bool,
) -> None:
    """Canonical schema and runtime model have one acceptance boundary."""
    payload = _base_plan() | mutation
    schema = json.loads((ROOT / "schemas/query_plan.schema.json").read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    schema_valid = not tuple(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload)
    )
    try:
        QueryPlan.model_validate_json(json.dumps(payload))
    except ValidationError:
        model_valid = False
    else:
        model_valid = True
    assert schema_valid is accepted
    assert model_valid is accepted


def test_evidence_record_schema_matches_exact_domain_model_family() -> None:
    """The canonical schema accepts exactly direct, derived, and summary evidence."""
    from finproof.domain.evidence import (
        DerivedEvidence,
        DirectEvidence,
        EvidenceSummary,
        EvidenceSummaryKind,
    )
    from finproof.domain.locators import SourceCellLocator
    from finproof.domain.quality import QualityStatus
    from finproof.domain.query_plan import ProductType
    from finproof.domain.values import DerivedValue, NormalizedValue

    source = SourceCellLocator(
        source_table="PREF01N001",
        source_file=PurePosixPath("domestic.xlsx"),
        source_sheet="datarows",
        source_row_number=2,
        source_column_name="pd_itm_no",
        source_column_number=1,
        source_column_letter="A",
        source_checksum="a" * 64,
        source_snapshot_date=date(2026, 7, 11),
        source_applicable_date=None,
    )
    direct = DirectEvidence[str](
        evidence_id="direct-1",
        product_type=ProductType.DOMESTIC_ETF,
        product_id="KR1",
        field_id="product_id",
        value=NormalizedValue[str](
            raw_value="KR1",
            normalized_value="KR1",
            quality_status=QualityStatus.VALID,
            rule_id="domestic.product_id",
            rule_version="1.0.0",
            source=source,
        ),
    )
    derived = DerivedEvidence[int](
        evidence_id="derived-1",
        product_type=ProductType.DOMESTIC_ETF,
        product_id=None,
        field_id="eligible_count",
        value=DerivedValue[int](
            value=1,
            quality_status=QualityStatus.VALID,
            rule_id="eligible.count",
            rule_version="1.0.0",
            as_of_date=date(2026, 7, 11),
            inputs=(source,),
        ),
    )
    summary = EvidenceSummary(
        summary_id="summary-1",
        kind=EvidenceSummaryKind.COUNT,
        included_count=1,
        excluded_count=0,
        evidence_ids=("direct-1", "derived-1"),
        policy_versions=("eligible@1.0.0",),
        validated_plan_sha256="b" * 64,
        version_bundle_sha256="c" * 64,
        artifact_manifest_hash="d" * 64,
    )
    schema = json.loads((ROOT / "schemas/evidence_record.schema.json").read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payloads = tuple(value.model_dump(mode="json") for value in (direct, derived, summary))
    assert all(not tuple(validator.iter_errors(payload)) for payload in payloads)

    malformed = dict(payloads[0])
    malformed["value"] = dict(malformed["value"]) | {"parallel_locator": {}}
    assert tuple(validator.iter_errors(malformed))


def test_execution_trace_schema_matches_exact_domain_model() -> None:
    from finproof.domain.execution import (
        ExecutionTrace,
        ExecutionTraceSegment,
        TraceValidation,
    )
    from finproof.domain.query_plan import (
        Intent,
        ProductType,
        ResultGrain,
        TopKScope,
    )

    trace = ExecutionTrace(
        correlation_id="trace-q1",
        intent=Intent.SCREEN,
        product_types=(ProductType.DOMESTIC_BOND,),
        as_of_date=date(2026, 7, 11),
        result_grain=ResultGrain.INSTRUMENT,
        top_k_scope=TopKScope.GLOBAL,
        segments=(
            ExecutionTraceSegment(
                product_type=ProductType.DOMESTIC_BOND,
                native_result_grain=ResultGrain.INSTRUMENT,
                partition_key="domestic_bond",
                candidate_counts={"raw": 1, "eligible": 1},
                returned=1,
            ),
        ),
        candidate_counts={"raw": 1, "eligible": 1, "returned": 1},
        tools=("entity_resolver", "query_executor", "claim_verifier"),
        policy_ids=("state:1.0.0", "metric:1.0.0"),
        validation=TraceValidation.PASSED,
        versions={"dataset_version": "2026-07-11"},
        latency_ms={},
    )
    schema = json.loads((ROOT / "schemas/execution_trace.schema.json").read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = trace.model_dump(mode="json")

    assert not tuple(validator.iter_errors(payload))
    assert set(schema["properties"]) == set(ExecutionTrace.model_fields)
    malformed = payload | {"sql": "SELECT *"}
    assert tuple(validator.iter_errors(malformed))
    with pytest.raises(ValidationError):
        ExecutionTrace.model_validate(malformed)
