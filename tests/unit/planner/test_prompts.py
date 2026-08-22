from datetime import date
from hashlib import sha256

from finproof.planner.prompts import PROMPT_VERSION, build_system_prompt
from finproof.registry.loader import RegistryBundle


def test_system_prompt_is_versioned_and_self_checksummed() -> None:
    prompt = build_system_prompt(RegistryBundle.from_package(), snapshot_date=date(2026, 7, 11))

    assert prompt.version == PROMPT_VERSION == "phase3-planner-v1"
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
    assert len(prompt.encode("utf-8")) < 24_000


def test_system_prompt_cannot_include_source_rows_secrets_or_local_paths() -> None:
    prompt = build_system_prompt(
        RegistryBundle.from_package(), snapshot_date=date(2026, 7, 11)
    ).text

    assert "PREF01N001" not in prompt
    assert "Bearer " not in prompt
    assert "/Users/" not in prompt
