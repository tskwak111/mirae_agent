"""Recorded-versus-comparison-valid views."""

from finproof.quality.metric_policy import MetricPolicyResult


class DualLensPolicy:
    def labels(self, result: MetricPolicyResult) -> tuple[str, ...]:
        if type(result) is not MetricPolicyResult:
            raise TypeError("dual-lens input differs")
        if result.recorded_values == result.comparison_valid_values:
            return ()
        return ("recorded", "comparison_valid")
