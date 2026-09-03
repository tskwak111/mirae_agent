import json
from datetime import date
from hashlib import sha256

from finproof.planner import prompts
from finproof.planner.prompts import PROMPT_VERSION, build_system_prompt
from finproof.planner.provider_schema import build_hcx_query_plan_schema
from finproof.registry.loader import RegistryBundle


def test_system_prompt_is_versioned_and_self_checksummed() -> None:
    prompt = build_system_prompt(RegistryBundle.from_package(), snapshot_date=date(2026, 7, 11))

    assert prompt.version == PROMPT_VERSION == "phase4-planner-v19"
    assert prompt.checksum == sha256(prompt.text.encode("utf-8")).hexdigest()
    assert len(prompt.checksum) == 64


def test_system_prompt_contains_the_closed_planning_contract_and_compact_catalog() -> None:
    prompt = build_system_prompt(
        RegistryBundle.from_package(), snapshot_date=date(2026, 7, 11)
    ).text

    required_rules = (
        "interpret only; never answer",
        "snapshot_date=2026-07-11",
        "ETF excludes ETN",
        "D-027",
        "result_grain=product",
        "top_k_scope=per_product_type",
        "각각 N개",
        "metric_targets=[]",
        "explicitly assigns different metrics",
        "use intent=screen_rank and top_k_scope=per_product_type",
        'aggregation={"function":"none","field":"","group_by":[]}',
        "never emit SQL",
        "never calculate",
        "never invent identifiers",
        "never advise",
        "never forecast",
        "output only JSON",
        '"domestic_etf"',
        '"total_fee"',
        '"return_1y"',
    )
    assert all(rule in prompt for rule in required_rules)
    compact_schema = json.dumps(
        build_hcx_query_plan_schema(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    assert f"provider_schema={compact_schema}" in prompt
    assert len(prompt.encode("utf-8")) < 24_000


def test_system_prompt_maps_native_grains_and_quality_screens() -> None:
    prompt = build_system_prompt(RegistryBundle.from_package(), snapshot_date=date(2026, 7, 11))

    assert prompt.version == "phase4-planner-v19"
    assert "domestic_bond=instrument" in prompt.text
    assert "domestic_etf|domestic_etn|overseas_etf|overseas_etn=listed_product" in prompt.text
    assert "public_fund=fund_item" in prompt.text
    assert "국내채권 means product_types=[domestic_bond]" in prompt.text
    assert "filtering or exclusion request uses intent=screen" in prompt.text
    assert "display/warning does not change intent" in prompt.text
    assert "Never emit an entity with empty text" in prompt.text
    assert "field-bearing plan members use IDs from the fields catalog" in prompt.text
    assert "never emit namespaced metric registry IDs" in prompt.text
    assert "BUYABLE_QUANTITY" in prompt.text
    assert "never emit buyable_quantity" in prompt.text
    assert "holding_constituent" in prompt.text
    assert "one scalar eq" in prompt.text
    assert "at most once" in prompt.text
    assert "never combine" in prompt.text
    assert "domestic_bond" in prompt.text
    assert all(alias in prompt.text for alias in ("구성종목", "보유종목", "편입종목"))
    compact_catalog = json.loads(
        prompt.text.split("\ncompact_catalog=", 1)[1].split("\nprovider_schema=", 1)[0]
    )
    assert set(compact_catalog) == {"products", "fields", "aliases"}


def test_system_prompt_separates_qualitative_rank_from_explicit_filters() -> None:
    prompt = build_system_prompt(
        RegistryBundle.from_package(), snapshot_date=date(2026, 7, 11)
    ).text

    assert "낮은/높은 with top-k define sort direction, not a filter" in prompt
    assert "Without an explicit literal value, set, range, or missing-state condition" in prompt
    assert "emit filters=[]; never invent a threshold" in prompt


def test_system_prompt_ends_with_the_metric_target_intent_invariant() -> None:
    prompt = build_system_prompt(
        RegistryBundle.from_package(), snapshot_date=date(2026, 7, 11)
    ).text

    assert prompt.endswith(
        "final_constraints=If metric_targets is nonempty, intent must be screen_rank "
        "and top_k_scope must be per_product_type. "
        'For explicit "상품 유형별로 N개씩" or "유형별로 N개씩", '
        "top_k_scope must be per_product_type, never global. "
        "For any heterogeneous query containing "
        "현재 구매 가능한, saleable and mirae_saleable must not appear in filters, metrics, "
        "metric_targets, sort, or aggregation; organizer state policy handles purchaseability. "
        "Every non-aggregate "
        'intent must emit aggregation={"function":"none","field":"","group_by":[]}. '
        'Preserve explicit numeric-zero filters; AUM equal zero requires filters=[{"field":"aum",'
        '"operator":"eq","value":0}]. Treat product_id and product_name as display identity '
        "fields; exclude them from metrics unless the question explicitly asks for a product code, "
        "identifier, or name. For any heterogeneous AUM query, metrics must include aum then "
        "currency exactly once in that order. For intent=screen with a bounded top_k and no "
        'user-specified sort, emit sort=[{"field":"product_name","direction":"asc"}]. '
        "For intent=unsupported, emit product_types=[], "
        "entities=[], result_grain=product, filters=[], metrics=[], metric_targets=[], sort=[], "
        'aggregation={"function":"none","field":"","group_by":[]}, needs_clarification=false, '
        "and a nonempty clarification_reason. For exactly one product_type, use its native "
        "result_grain: domestic_bond=instrument; "
        "domestic_etf|domestic_etn|overseas_etf|overseas_etn=listed_product; "
        "public_fund=fund_item. Use result_grain=product only for heterogeneous native grains."
    )


def test_planning_user_prompt_preserves_question_then_repeats_final_constraints() -> None:
    question = "현재 구매 가능한 상품을 유형별 지표로 3개씩 알려줘."

    prompt = prompts.build_user_prompt(question)

    assert prompt.startswith(f"{question}\n")
    assert prompt.count(question) == 1
    assert prompt.endswith(
        "final_constraints=If metric_targets is nonempty, intent must be screen_rank "
        "and top_k_scope must be per_product_type. "
        'For explicit "상품 유형별로 N개씩" or "유형별로 N개씩", '
        "top_k_scope must be per_product_type, never global. "
        "For any heterogeneous query containing "
        "현재 구매 가능한, saleable and mirae_saleable must not appear in filters, metrics, "
        "metric_targets, sort, or aggregation; organizer state policy handles purchaseability. "
        "Every non-aggregate "
        'intent must emit aggregation={"function":"none","field":"","group_by":[]}. '
        'Preserve explicit numeric-zero filters; AUM equal zero requires filters=[{"field":"aum",'
        '"operator":"eq","value":0}]. Treat product_id and product_name as display identity '
        "fields; exclude them from metrics unless the question explicitly asks for a product code, "
        "identifier, or name. For any heterogeneous AUM query, metrics must include aum then "
        "currency exactly once in that order. For intent=screen with a bounded top_k and no "
        'user-specified sort, emit sort=[{"field":"product_name","direction":"asc"}]. '
        "For intent=unsupported, emit product_types=[], "
        "entities=[], result_grain=product, filters=[], metrics=[], metric_targets=[], sort=[], "
        'aggregation={"function":"none","field":"","group_by":[]}, needs_clarification=false, '
        "and a nonempty clarification_reason. For exactly one product_type, use its native "
        "result_grain: domestic_bond=instrument; "
        "domestic_etf|domestic_etn|overseas_etf|overseas_etn=listed_product; "
        "public_fund=fund_item. Use result_grain=product only for heterogeneous native grains."
    )


def test_planning_user_prompt_forces_per_product_scope_for_per_type_counts() -> None:
    prompt = prompts.build_user_prompt(
        "AUM이 0으로 기록된 국내 ETF, 해외 ETF와 공모펀드를 상품 유형별로 10개씩 알려줘."
    )

    assert (
        'For explicit "상품 유형별로 N개씩" or "유형별로 N개씩", '
        "top_k_scope must be per_product_type, never global."
    ) in prompt


def test_planning_user_prompt_ends_with_single_product_native_grain_constraint() -> None:
    prompt = prompts.build_user_prompt("국내 ETF 중 총보수가 낮은 상품 5개를 알려줘.")

    assert prompt.endswith(
        "For exactly one product_type, use its native result_grain: domestic_bond=instrument; "
        "domestic_etf|domestic_etn|overseas_etf|overseas_etn=listed_product; "
        "public_fund=fund_item. Use result_grain=product only for heterogeneous native grains."
    )


def test_planning_user_prompt_excludes_all_eligibility_fields_for_organizer_query() -> None:
    prompt = prompts.build_user_prompt(
        "현재 구매 가능한 국내채권과 국내 ETF, 공모펀드에서 지표별로 3개씩 알려줘."
    )

    assert (
        "For any heterogeneous query containing 현재 구매 가능한, saleable and "
        "mirae_saleable must not appear in filters, metrics, metric_targets, sort, or "
        "aggregation; organizer state policy handles purchaseability."
    ) in prompt


def test_system_prompt_cannot_include_source_rows_secrets_or_local_paths() -> None:
    prompt = build_system_prompt(
        RegistryBundle.from_package(), snapshot_date=date(2026, 7, 11)
    ).text

    assert "PREF01N001" not in prompt
    assert "Bearer " not in prompt
    assert "/Users/" not in prompt
