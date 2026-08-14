"""Shared listed-product vocabulary used by domestic and overseas records."""

from enum import StrEnum


class ListedProductType(StrEnum):
    """Exact official listed-product groups kept distinct by the source."""

    ETF = "ETF"
    ETN = "ETN"
