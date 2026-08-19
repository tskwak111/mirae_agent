"""Closed one-pass bounds for exact-link candidate/evidence processing."""

from __future__ import annotations

from collections.abc import Iterator


def test_exact_link_candidate_and_evidence_pipeline_stays_within_closed_one_pass_bounds() -> None:
    from finproof.data.artifacts.links import _consume_candidate_batches
    from finproof.data.artifacts.staging import ExactLinkCandidateJoinRow
    from tests.unit.data.artifacts.test_exact_links import _candidate

    class OnePass:
        def __init__(self) -> None:
            self.iterations = 0

        def __iter__(self) -> Iterator[tuple[ExactLinkCandidateJoinRow, ...]]:
            self.iterations += 1
            if self.iterations > 1:
                raise AssertionError("candidate batches were iterated twice")
            for index in range(2_000):
                yield (
                    _candidate(
                        raw=f"RAW-{index:04d}",
                        left_id=f"L-{index:04d}",
                        right_id=f"R-{index:04d}",
                    ),
                )

    batches = OnePass()
    rows, maximum = _consume_candidate_batches(batches, expected_links=2_000)

    assert batches.iterations == 1
    assert len(rows) == 2_000
    assert maximum == 1
