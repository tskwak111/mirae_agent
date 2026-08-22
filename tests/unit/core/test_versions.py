from datetime import date

import pytest
from pydantic import ValidationError

from finproof.core.versions import VersionBundle


def test_version_bundle_defaults_match_checked_in_contracts() -> None:
    bundle = VersionBundle()

    assert bundle.model_dump(mode="json") == {
        "answer_policy_version": "1.0.0",
        "dataset_version": "2026-07-11",
        "metric_registry_version": "1.0.0",
        "planner_version": "1.0.0",
        "quality_rule_version": "1.0.0",
        "rating_rule_version": "1.0.0",
        "state_rule_version": "1.1.0",
    }


def test_version_bundle_is_immutable() -> None:
    bundle = VersionBundle()

    with pytest.raises(ValidationError):
        bundle.dataset_version = date(2026, 7, 12)
