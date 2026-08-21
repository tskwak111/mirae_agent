"""Focused deterministic tie behavior."""

from decimal import Decimal


def test_constant_tracking_error_preserves_joint_primary_rank() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import MetricValue, TiePolicy

    values = tuple(
        MetricValue(
            metric_id="domestic_etf.tracking_error",
            product_type=ProductType.DOMESTIC_ETF,
            product_id=product_id,
            value=Decimal("0"),
            quality_status="valid",
        )
        for product_id in ("E2", "E1", "E3")
    )

    ranked = TiePolicy().rank(values, descending=False)

    assert tuple(item.value.product_id for item in ranked) == ("E1", "E2", "E3")
    assert tuple((item.rank, item.tie_count) for item in ranked) == (
        (1, 3),
        (1, 3),
        (1, 3),
    )
