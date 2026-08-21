"""Focused metric compatibility partitioning."""

from decimal import Decimal

import pytest


def test_krw_and_usd_aum_form_separate_compatibility_partitions() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import CompatibilityPartitioner, MetricValue

    values = (
        MetricValue(
            metric_id="domestic_etf.aum",
            product_type=ProductType.DOMESTIC_ETF,
            product_id="K1",
            value=Decimal("100"),
            quality_status="valid",
            currency="KRW",
            period="snapshot",
        ),
        MetricValue(
            metric_id="overseas_etf.aum",
            product_type=ProductType.OVERSEAS_ETF,
            product_id="U1",
            value=Decimal("100"),
            quality_status="valid",
            currency="USD",
            period="source_as_of",
        ),
    )

    partitions = CompatibilityPartitioner().partition(values)

    assert tuple(partition.currency for partition in partitions) == ("KRW", "USD")
    assert tuple(partition.values for partition in partitions) == ((values[0],), (values[1],))


def test_bond_yield_and_historical_return_cannot_share_one_rank() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import CompatibilityPartitioner, MetricValue

    values = (
        MetricValue(
            metric_id="bond.buy_yield",
            product_type=ProductType.DOMESTIC_BOND,
            product_id="B1",
            value=Decimal("3"),
            quality_status="valid",
        ),
        MetricValue(
            metric_id="public_fund.return_1m",
            product_type=ProductType.PUBLIC_FUND,
            product_id="F1",
            value=Decimal("3"),
            quality_status="valid",
        ),
    )

    partitions = CompatibilityPartitioner().partition(values)

    assert len(partitions) == 2
    assert partitions[0].compatibility_key != partitions[1].compatibility_key


def test_missing_return_period_requires_clarification() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import CompatibilityPartitioner, MetricValue

    values = (
        MetricValue(
            metric_id="domestic_etf.return_1m",
            product_type=ProductType.DOMESTIC_ETF,
            product_id="E1",
            value=Decimal("1"),
            quality_status="valid",
        ),
        MetricValue(
            metric_id="public_fund.return_1m",
            product_type=ProductType.PUBLIC_FUND,
            product_id="F1",
            value=Decimal("2"),
            quality_status="valid",
        ),
    )

    with pytest.raises(ValueError, match="clarification"):
        CompatibilityPartitioner().partition(values)


def test_same_period_etf_and_fund_return_is_caveated_compatible() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import CompatibilityPartitioner, MetricValue

    values = (
        MetricValue(
            metric_id="domestic_etf.return_1m",
            product_type=ProductType.DOMESTIC_ETF,
            product_id="E1",
            value=Decimal("1"),
            quality_status="valid",
        ),
        MetricValue(
            metric_id="public_fund.return_1m",
            product_type=ProductType.PUBLIC_FUND,
            product_id="F1",
            value=Decimal("2"),
            quality_status="valid",
        ),
    )

    partitions = CompatibilityPartitioner().partition(values, requested_period="1m")

    assert len(partitions) == 1
    assert partitions[0].values == values
    assert partitions[0].caveats == ("cross-product source semantics differ",)
