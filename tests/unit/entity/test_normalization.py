"""Focused conservative product-text normalization tests."""

import pytest


def test_entity_module_skeleton_exposes_exact_types() -> None:
    from finproof.entity import (
        EntityIndex,
        EntityResolver,
        ExactCrossSourceLinkRepository,
        ResolutionCandidate,
        ResolutionMatchKind,
        ResolutionResult,
        normalize_product_text,
    )

    assert callable(normalize_product_text)
    assert all(
        isinstance(value, type)
        for value in (
            EntityIndex,
            EntityResolver,
            ExactCrossSourceLinkRepository,
            ResolutionCandidate,
            ResolutionMatchKind,
            ResolutionResult,
        )
    )


def test_product_text_normalization_is_conservative_and_stable() -> None:
    from finproof.entity import normalize_product_text

    cases = {
        "  삼성\u3000ETF\t": "삼성 etf",
        "\uff21\uff22\uff23\uff11\uff12\uff13": "abc123",
        "KODEX-200(주식)": "kodex-200(주식)",
        "한  글": "한 글",
        "": "",
    }
    for source, expected in cases.items():
        normalized = normalize_product_text(source)
        assert normalized == expected
        assert normalize_product_text(normalized) == normalized

    with pytest.raises(TypeError):
        normalize_product_text(123)  # type: ignore[arg-type]
