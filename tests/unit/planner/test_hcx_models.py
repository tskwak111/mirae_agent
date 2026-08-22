import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from finproof.planner.models import HcxMessage, HcxRequest


def _query_plan_schema() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(Path("schemas/hcx_query_plan.schema.json").read_text(encoding="utf-8")),
    )


def _messages() -> tuple[HcxMessage, ...]:
    return (
        HcxMessage(role="system", content="Return a query plan."),
        HcxMessage(role="user", content="미국 ETF 5개"),
    )


def test_structured_request_uses_v3_camel_case_fields() -> None:
    schema = _query_plan_schema()

    request = HcxRequest.structured(
        model_name="HCX-007",
        messages=_messages(),
        schema=schema,
        max_completion_tokens=1200,
        temperature=0.0,
        seed=17,
    )

    payload = request.to_payload()
    assert payload["responseFormat"] == {"type": "json", "schema": schema}
    assert payload["maxCompletionTokens"] == 1200
    assert payload["messages"] == [
        {"role": "system", "content": "Return a query plan."},
        {"role": "user", "content": "미국 ETF 5개"},
    ]
    assert "tools" not in payload
    assert "thinking" not in payload


def test_structured_schema_and_emitted_payload_cannot_mutate_the_request() -> None:
    schema = _query_plan_schema()
    request = HcxRequest.structured(
        model_name="HCX-007",
        messages=_messages(),
        schema=schema,
        max_completion_tokens=1200,
        temperature=0.0,
        seed=17,
    )

    schema["properties"]["poison"] = {"type": "string"}
    first_payload = request.to_payload()
    first_payload["responseFormat"]["schema"]["properties"]["other"] = {"type": "string"}

    stored_properties = request.to_payload()["responseFormat"]["schema"]["properties"]
    assert "poison" not in stored_properties
    assert "other" not in stored_properties


def test_structured_request_rejects_every_model_except_hcx_007() -> None:
    with pytest.raises(ValidationError, match="HCX-007"):
        HcxRequest.structured(
            model_name="HCX-DASH-002",
            messages=_messages(),
            schema=_query_plan_schema(),
            max_completion_tokens=1200,
            temperature=0.0,
            seed=17,
        )


@pytest.mark.parametrize("model_name", ["", "CLOVA-X", "gpt-5"])
def test_strict_json_request_accepts_only_hcx_model_names(model_name: str) -> None:
    with pytest.raises(ValidationError, match="HCX-"):
        HcxRequest.strict_json(
            model_name=model_name,
            messages=_messages(),
            max_completion_tokens=1200,
            temperature=0.0,
            seed=17,
        )


def test_request_rejects_multiple_system_messages() -> None:
    with pytest.raises(ValidationError, match="system"):
        HcxRequest.strict_json(
            model_name="HCX-007",
            messages=(
                HcxMessage(role="system", content="first"),
                HcxMessage(role="system", content="second"),
                HcxMessage(role="user", content="question"),
            ),
            max_completion_tokens=1200,
            temperature=0.0,
            seed=17,
        )


@pytest.mark.parametrize("max_completion_tokens", [0, 32769])
def test_request_rejects_completion_tokens_outside_provider_bounds(
    max_completion_tokens: int,
) -> None:
    with pytest.raises(ValidationError, match="max_completion_tokens"):
        HcxRequest.strict_json(
            model_name="HCX-007",
            messages=_messages(),
            max_completion_tokens=max_completion_tokens,
            temperature=0.0,
            seed=17,
        )


def test_request_rejects_conservative_context_budget_overflow() -> None:
    with pytest.raises(ValidationError, match="128000"):
        HcxRequest.strict_json(
            model_name="HCX-007",
            messages=(HcxMessage(role="user", content="가" * 43_000),),
            max_completion_tokens=1,
            temperature=0.0,
            seed=17,
        )


@pytest.mark.parametrize("forbidden_field", ["tools", "thinking"])
def test_request_rejects_tool_and_thinking_fields(forbidden_field: str) -> None:
    values: dict[str, object] = {
        "model_name": "HCX-007",
        "messages": _messages(),
        "max_completion_tokens": 1200,
        "temperature": 0.0,
        "seed": 17,
        forbidden_field: [],
    }

    with pytest.raises(ValidationError, match="Extra inputs"):
        HcxRequest.model_validate(values)
