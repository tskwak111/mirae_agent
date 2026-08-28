import json
from datetime import date
from hashlib import sha256

from finproof.planner.prompts import PROMPT_VERSION, build_system_prompt
from finproof.planner.provider_schema import build_hcx_query_plan_schema
from finproof.registry.loader import RegistryBundle


def test_system_prompt_is_versioned_and_self_checksummed() -> None:
    prompt = build_system_prompt(RegistryBundle.from_package(), snapshot_date=date(2026, 7, 11))

    assert prompt.version == PROMPT_VERSION == "phase4-planner-v2"
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

    assert prompt.version == "phase4-planner-v2"
    assert "domestic_bond=instrument" in prompt.text
    assert "domestic_etf|domestic_etn|overseas_etf|overseas_etn=listed_product" in prompt.text
    assert "public_fund=fund_item" in prompt.text
    assert "국내채권 means product_types=[domestic_bond]" in prompt.text
    assert "filtering or exclusion request uses intent=screen" in prompt.text
    assert "display/warning does not change intent" in prompt.text
    assert "Never emit an entity with empty text" in prompt.text
    assert "field-bearing plan members use IDs from the fields catalog" in prompt.text
    assert "never emit namespaced metric registry IDs" in prompt.text
    assert "매수가능수량=buyable_quantity" in prompt.text
    assert "buyable_quantity is not saleable" in prompt.text
    compact_catalog = json.loads(
        prompt.text.split("\ncompact_catalog=", 1)[1].split("\nprovider_schema=", 1)[0]
    )
    assert set(compact_catalog) == {"products", "fields", "aliases"}


def test_system_prompt_cannot_include_source_rows_secrets_or_local_paths() -> None:
    prompt = build_system_prompt(
        RegistryBundle.from_package(), snapshot_date=date(2026, 7, 11)
    ).text

    assert "PREF01N001" not in prompt
    assert "Bearer " not in prompt
    assert "/Users/" not in prompt
