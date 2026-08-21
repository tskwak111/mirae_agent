"""Focused operation-specific metric policies."""

from decimal import Decimal


def test_overseas_fee_zero_has_recorded_and_comparison_valid_views() -> None:
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
    assert result.comparison_valid_values == ()
    assert result.excluded_count == 1


def test_dual_lens_labels_appear_only_when_policy_difference_is_material() -> None:
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

    assert DualLensPolicy().labels(zero) == ("recorded", "comparison_valid")
    assert DualLensPolicy().labels(nonzero) == ()
