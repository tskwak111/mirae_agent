"""Release-facing aliases for the 17 frozen critical regressions."""

# Ruff sees the long aliases as unused; pytest collects them as the release-facing suite.
# ruff: noqa: E501, F401

from decimal import Decimal

from tests.security.test_query_injection import (
    test_query_injection_family_never_reaches_identifier_expression_or_statement_surface as test_critical_13_sql_injection,
)
from tests.security.test_runtime_provider_policy import (
    test_httpx_is_confined_to_the_hcx_transport_boundary as test_critical_17_hcx_only,
)
from tests.unit.api.test_response_model import (
    test_evaluation_response_has_exact_five_string_fields as test_critical_16_five_fields,
)
from tests.unit.data.normalization.test_public_fund_collapse import (
    test_noncontiguous_rows_group_globally_to_one_complete_item_and_two_attributes as test_critical_03_fund_item_grain,
)
from tests.unit.data.normalization.test_public_funds import (
    test_literal_null_is_special_only_for_risk_fields as test_critical_04_null_risk_missing,
)
from tests.unit.data.normalization.test_public_funds import (
    test_malformed_item_quarantines_before_shifted_payload_is_parsed as test_critical_05_fund_quarantine,
)
from tests.unit.entity.test_resolver import (
    test_fuzzy_candidates_are_top_five_deterministic_and_never_selected as test_critical_14_no_fuzzy_merge,
)
from tests.unit.evidence.test_claim_verifier import (
    test_claim_verifier_rejects_numeric_claim_without_evidence as test_critical_15_claim_evidence,
)
from tests.unit.planner.test_rule_fallback import (
    test_rule_fallback_plain_etf_top_k_excludes_etn as test_critical_02_etf_excludes_etn,
)
from tests.unit.quality.test_comparability import (
    test_krw_and_usd_aum_form_separate_compatibility_partitions as test_critical_06_currency_partition,
)
from tests.unit.quality.test_metric_operation_policy import (
    test_overseas_fee_zero_is_intentional_and_comparison_valid as test_critical_07_fee_zero_policy,
)
from tests.unit.quality.test_state_policy import (
    test_domestic_listed_zero_suspension_flag_is_not_suspended as test_critical_01_not_suspended,
)
from tests.unit.quality.test_state_policy import (
    test_ended_bond_is_not_purchasable_even_with_irrelevant_positive_quantity as test_critical_10_expired_bond,
)
from tests.unit.quality.test_ties import (
    test_constant_tracking_error_preserves_joint_primary_rank as test_critical_08_tracking_tie,
)
from tests.unit.registry.test_rating_registry import (
    registry,
)
from tests.unit.registry.test_rating_registry import (
    test_agency_tokens_are_resolved_independently_in_source_order as test_critical_12_agency_disagreement,
)
from tests.unit.registry.test_rating_registry import (
    test_unregistered_grades_stay_out_of_domain_and_noncomparable as test_critical_11_missing_not_aaa,
)


def test_critical_09_overseas_one_day_return_preserves_tie() -> None:
    from finproof.domain.query_plan import ProductType
    from finproof.quality import MetricValue, TiePolicy

    ranked = TiePolicy().rank(
        tuple(
            MetricValue(
                metric_id="overseas_etf.return_1d",
                product_type=ProductType.OVERSEAS_ETF,
                product_id=product_id,
                value=Decimal("0"),
                quality_status="valid",
            )
            for product_id in ("O2", "O1")
        ),
        descending=True,
    )

    assert tuple((item.value.product_id, item.rank, item.tie_count) for item in ranked) == (
        ("O1", 1, 2),
        ("O2", 1, 2),
    )
