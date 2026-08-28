"""Focused operation-specific metric policies."""

from decimal import Decimal

import pytest


def test_overseas_fee_zero_is_intentional_and_comparison_valid() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import MetricPolicy, MetricValue, Operation

    value = MetricValue(
        metric_id="overseas_etf.total_fee",
        product_type=ProductType.OVERSEAS_ETF,
        product_id="O1",
        value=Decimal("0"),
        quality_status="valid",
    )

    result = MetricPolicy().apply(Operation.RANK, (value,))

    assert result.recorded_values == (value,)
    assert result.comparison_valid_values == (value,)
    assert result.excluded_count == 0


def test_intentional_fee_zero_does_not_create_dual_lens_labels() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import DualLensPolicy, MetricPolicy, MetricValue, Operation

    zero = MetricPolicy().apply(
        Operation.RANK,
        (
            MetricValue(
                metric_id="overseas_etf.total_fee",
                product_type=ProductType.OVERSEAS_ETF,
                product_id="O1",
                value=Decimal("0"),
                quality_status="valid",
            ),
        ),
    )
    nonzero = MetricPolicy().apply(
        Operation.RANK,
        (
            MetricValue(
                metric_id="domestic_etf.total_fee",
                product_type=ProductType.DOMESTIC_ETF,
                product_id="D1",
                value=Decimal("0.1"),
                quality_status="valid",
            ),
        ),
    )

    assert DualLensPolicy().labels(zero) == ()
    assert DualLensPolicy().labels(nonzero) == ()


def test_overseas_aum_zero_is_rank_excluded_but_aggregate_included() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import MetricPolicy, MetricValue, Operation

    zero = MetricValue(
        metric_id="overseas_etf.aum",
        product_type=ProductType.OVERSEAS_ETF,
        product_id="ZERO",
        value=Decimal("0"),
        quality_status="recorded_zero",
        currency="USD",
    )

    ranked = MetricPolicy().apply(Operation.RANK, (zero,))
    aggregated = MetricPolicy().apply(Operation.AGGREGATE, (zero,))

    assert ranked.recorded_values == (zero,)
    assert ranked.comparison_valid_values == ()
    assert aggregated.comparison_valid_values == (zero,)


@pytest.mark.parametrize(
    ("metric_id", "product_type"),
    [
        ("domestic_etf.tracking_error", "domestic_etf"),
        ("domestic_etf.return_1y", "domestic_etf"),
        ("overseas_etf.return_1d", "overseas_etf"),
    ],
)
@pytest.mark.parametrize("operation", ["display", "filter", "rank", "aggregate"])
def test_refreshed_varying_metrics_exclude_missing_without_imputing_zero(
    metric_id: str,
    product_type: str,
    operation: str,
) -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import DualLensPolicy, MetricPolicy, MetricValue, Operation

    missing = MetricValue(
        metric_id=metric_id,
        product_type=ProductType(product_type),
        product_id="MISSING",
        value=None,
        quality_status="missing_blank",
    )
    zero = MetricValue(
        metric_id=metric_id,
        product_type=ProductType(product_type),
        product_id="ZERO",
        value=Decimal("0"),
        quality_status="recorded_zero",
    )

    result = MetricPolicy().apply(Operation(operation), (missing, zero))

    assert result.recorded_values == (zero,)
    assert result.comparison_valid_values == (zero,)
    assert result.excluded_count == 1
    assert result.warnings == ("metric values excluded from comparison",)
    assert DualLensPolicy().labels(result) == ()


def test_refreshed_varying_metrics_remove_snapshot_constant_zero_rules() -> None:
    from finproof.registry.loader import RegistryBundle

    registries = RegistryBundle.from_package()

    assert not any(
        rule.get("field") in {"du_chas_errt", "du_er_1d"} and "dataset_assertion" in rule
        for rule in registries.quality.entries.values()
    )
    for metric_id in (
        "domestic_etf.total_fee",
        "domestic_etf.tracking_error",
        "overseas_etf.total_fee",
        "overseas_etf.return_1d",
    ):
        metric = registries.metrics.entries[metric_id]
        assert "constant" not in metric.ranking_policy
        assert "constant" not in metric.aggregation_policy
        assert "dataset_distribution" not in metric.evidence_rule
        assert "unverified" not in metric.zero_policy
        assert "dual" not in metric.ranking_policy
    assert not any(
        rule.get("field") == "cu_charge_rt" and rule.get("status") == "recorded_zero_unverified"
        for rule in registries.quality.entries.values()
    )
