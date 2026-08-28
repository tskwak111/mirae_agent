"""Independent exact-untrimmed official ETF/fund intersection profile."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.source_contract


def test_official_exact_untrimmed_pair_scan_is_217_etf_only_and_one_to_one() -> None:
    from tests.helpers.official_artifact_subprocess import scan_official_exact_pairs

    repository_root = Path(__file__).resolve().parents[2]
    source_root = repository_root / "source_material"
    pairs = scan_official_exact_pairs(source_root)

    assert len(pairs) == 217
    assert len({left for left, _right in pairs}) == len(pairs)
    assert len({right for _left, right in pairs}) == len(pairs)
