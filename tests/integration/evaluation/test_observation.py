import json
from datetime import date
from decimal import Decimal

from finproof.cli.evaluate import _observed_aggregates, _observed_products
from finproof.domain.evidence import (
    EvidenceBundle,
    EvidenceSummary,
    EvidenceSummaryKind,
    EvidenceSummaryValue,
)
from finproof.domain.query_plan import (
    AggregationFunction,
    AggregationSpec,
    Intent,
    ProductType,
    QueryPlan,
    ResultGrain,
    TopKScope,
)
from finproof.evaluation.models import ExpectedAggregate
from finproof.evidence.serializer import serialize_evidence_context


def _plan(
    *,
    intent: Intent,
    products: tuple[ProductType, ...],
    grain: ResultGrain,
    aggregation: AggregationSpec | None = None,
) -> QueryPlan:
    return QueryPlan(
        intent=intent,
        product_types=products,
        entities=(),
        as_of_date=date(2026, 7, 11),
        result_grain=grain,
        filters=(),
        metrics=("return_1y",) if aggregation is not None else (),
        sort=(),
        aggregation=aggregation,
        top_k=2,
        top_k_scope=TopKScope.GLOBAL,
        needs_clarification=False,
        clarification_reason="",
    )


def _summary(**updates: object) -> EvidenceSummary:
    values: dict[str, object] = {
        "summary_id": "summary:rank:0",
        "kind": EvidenceSummaryKind.RANK,
        "included_count": 1,
        "excluded_count": 0,
        "evidence_ids": (),
        "policy_versions": ("return_1y:rank",),
        "validated_plan_sha256": "a" * 64,
        "version_bundle_sha256": "b" * 64,
        "artifact_manifest_hash": "c" * 64,
        "product_types": (ProductType.DOMESTIC_ETF,),
        "native_result_grains": (ResultGrain.LISTED_PRODUCT,),
        "partition_key": "return_1y:KRW",
        "product_id": "SAME",
        "metric_id": "return_1y",
        "rank": 1,
        "tie_count": 1,
        "value": Decimal("3.10"),
    }
    values.update(updates)
    return EvidenceSummary.model_validate(values)


def test_serialized_rank_summaries_preserve_compatible_multi_product_order() -> None:
    summaries = (
        _summary(product_types=(ProductType.OVERSEAS_ETF,)),
        _summary(summary_id="summary:rank:1", rank=2),
    )
    payload = json.loads(
        serialize_evidence_context(
            EvidenceBundle(
                direct=(), derived=(), summaries=summaries, material_policy_limitations=()
            )
        )
    )
    plan = _plan(
        intent=Intent.SCREEN_RANK,
        products=(ProductType.DOMESTIC_ETF, ProductType.OVERSEAS_ETF),
        grain=ResultGrain.LISTED_PRODUCT,
    )

    products = _observed_products(plan, (), payload["summaries"])

    assert tuple(item.product_type for item in products) == (
        ProductType.OVERSEAS_ETF,
        ProductType.DOMESTIC_ETF,
    )
    assert tuple(item.product_id for item in products) == ("SAME", "SAME")


def test_serialized_aggregate_summary_is_typed_and_has_no_product_results() -> None:
    aggregation = AggregationSpec(
        function=AggregationFunction.AVG,
        field="return_1y",
        group_by=("currency",),
    )
    plan = _plan(
        intent=Intent.AGGREGATE,
        products=(ProductType.DOMESTIC_ETF,),
        grain=ResultGrain.LISTED_PRODUCT,
        aggregation=aggregation,
    )
    summary = _summary(
        summary_id="summary:aggregate:0",
        kind=EvidenceSummaryKind.AGGREGATE,
        policy_versions=("return_1y:avg",),
        rank=None,
        tie_count=None,
        product_id=None,
        group_values=(EvidenceSummaryValue(field_id="currency", value="KRW"),),
    )
    payload = json.loads(
        serialize_evidence_context(
            EvidenceBundle(
                direct=(), derived=(), summaries=(summary,), material_policy_limitations=()
            )
        )
    )
    expected = (
        ExpectedAggregate.model_validate(
            {
                "function": "avg",
                "field_id": "return_1y",
                "product_type": "domestic_etf",
                "native_result_grain": "listed_product",
                "partition_key": "return_1y:KRW",
                "group_values": [{"field_id": "currency", "value_type": "text", "value": "KRW"}],
                "value_type": "decimal",
                "value": "3.10",
            }
        ),
    )

    products = _observed_products(
        plan,
        ({"product_type": "domestic_etf", "product_id": "SELECTED"},),
        payload["summaries"],
    )
    aggregates = _observed_aggregates(expected, payload["summaries"])

    assert products == ()
    assert aggregates[0].value == Decimal("3.10")
