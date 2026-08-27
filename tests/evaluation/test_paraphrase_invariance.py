from pathlib import Path

import pytest

from finproof.evaluation.loader import load_golden_cases
from finproof.evaluation.paraphrases import (
    ParaphraseRule,
    ParaphraseRules,
    generate_rule_paraphrases,
)


def test_condition_order_paraphrase_preserves_reviewed_expectations() -> None:
    case = next(
        case
        for case in load_golden_cases((Path("evaluation/canonical/screen.jsonl"),))
        if case.case_id == "CQ-003-007"
    )
    rules = ParaphraseRules.load(Path("evaluation/paraphrase_rules.yaml"))

    variant = next(
        derived
        for derived in generate_rule_paraphrases(case, rules)
        if derived.transformation_id == "condition-order-two-filters"
    )

    assert variant.question == (
        "총보수가 0.15% 이하이고 투자지역이 미국인 해외 ETF를 ETN을 제외하고 찾아주세요."
    )
    assert variant.base_case_id == case.case_id
    assert variant.expected_plan == case.expected_plan
    assert variant.expected_result == case.expected_result
    assert variant.expected_answer == case.expected_answer


@pytest.mark.parametrize(
    ("transformation_id", "question", "expected"),
    [
        ("honorific", "미국 ETF 5개 알려주세요", "미국 ETF 5개 알려줘"),
        ("top-k-wording", "미국 ETF 상위 5개", "미국 ETF 5개"),
        ("descending-synonym", "AUM이 가장 높은 5개", "AUM이 내림차순인 5개"),
        ("ascending-synonym", "총보수가 가장 낮은 5개", "총보수가 오름차순인 5개"),
        ("exact-voo-name", "VOO AUM 알려줘", "Vanguard S&P 500 ETF VOO AUM 알려줘"),
        ("whitespace", "미국 ETF 5개", "미국  ETF 5개"),
        ("reviewed-typo", "1년 수익률 높은 ETF", "1년 수익율 높은 ETF"),
    ],
)
def test_reviewed_rule_families_preserve_semantic_expectations(
    transformation_id: str,
    question: str,
    expected: str,
) -> None:
    base = load_golden_cases((Path("evaluation/canonical/screen.jsonl"),))[0]
    case = base.model_copy(update={"question": question})

    variant = next(
        derived
        for derived in generate_rule_paraphrases(
            case,
            ParaphraseRules.load(Path("evaluation/paraphrase_rules.yaml")),
        )
        if derived.transformation_id == transformation_id
    )

    assert variant.question == expected
    assert variant.expected_plan == case.expected_plan


def test_rule_cannot_change_numeric_semantic_values() -> None:
    base = load_golden_cases((Path("evaluation/canonical/screen.jsonl"),))[0]
    case = base.model_copy(update={"question": "총보수 0.15% 이하 ETF 5개"})
    unsafe = ParaphraseRules(
        version="test",
        rules=(
            ParaphraseRule(
                rule_id="unsafe-threshold",
                pattern="0.15",
                replacement="0.25",
            ),
        ),
    )

    with pytest.raises(ValueError, match="semantic values"):
        generate_rule_paraphrases(case, unsafe)


@pytest.mark.asyncio
async def test_condition_order_variant_produces_same_validated_fallback_plan() -> None:
    from tests.unit.planner.test_rule_fallback import _planner, _request

    base = load_golden_cases((Path("evaluation/canonical/rank.jsonl"),))[0]
    case = base.model_copy(update={"question": "수익률이 좋고 AUM이 큰 국내 ETF 5개를 알려주세요"})
    variant = next(
        derived
        for derived in generate_rule_paraphrases(
            case,
            ParaphraseRules.load(Path("evaluation/paraphrase_rules.yaml")),
        )
        if derived.transformation_id == "condition-order-rank-filter"
    )
    planner = _planner()

    base_plan = (await planner.plan(_request(case.question))).plan
    variant_plan = (await planner.plan(_request(variant.question))).plan

    assert variant_plan == base_plan
