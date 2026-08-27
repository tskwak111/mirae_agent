import pytest

from finproof.evaluation.latency import LatencySample, LatencySummary


def test_latency_summary_computes_nearest_rank_p95() -> None:
    summary = LatencySummary.from_milliseconds(list(range(1, 101)))

    assert summary.p95_ms == 95
    assert summary.count == 100


def test_latency_sample_rejects_stage_larger_than_total() -> None:
    with pytest.raises(ValueError, match="stage latency cannot exceed total latency"):
        LatencySample(total_ms=10, stage_ms={"planner": 11})


def test_latency_sample_rejects_non_finite_measurements() -> None:
    with pytest.raises(ValueError, match="finite number"):
        LatencySample(total_ms=float("inf"))


def test_latency_summary_counts_failed_requests_separately() -> None:
    summary = LatencySummary.from_samples(
        (
            LatencySample(total_ms=10, stage_ms={"planner": 4}, succeeded=True),
            LatencySample(total_ms=20, stage_ms={"planner": 8}, succeeded=False),
        )
    )

    assert summary.count == 2
    assert summary.success_count == 1
    assert summary.failure_count == 1
    assert summary.mean_ms == 15
    assert summary.stage_mean_ms == {"planner": 6}
