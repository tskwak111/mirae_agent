import json
import os

import httpx
import pytest
from pydantic import SecretStr

from finproof.planner.hcx_client import HcxClient
from finproof.planner.models import HcxMessage, HcxRequest

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("FINPROOF_RUN_LIVE_HCX") != "1"
        or not os.environ.get("FINPROOF_HCX_API_KEY"),
        reason="live HCX smoke requires explicit opt-in and credentials",
    ),
]


@pytest.mark.asyncio
async def test_live_hcx_007_strict_json_authentication() -> None:
    api_key = SecretStr(os.environ["FINPROOF_HCX_API_KEY"])
    request = HcxRequest.strict_json(
        model_name="HCX-007",
        messages=(
            HcxMessage(role="system", content="Return only valid JSON."),
            HcxMessage(role="user", content='Return {"ok": true}.'),
        ),
        max_completion_tokens=2_048,
        temperature=0.0,
        seed=17,
    )

    async with httpx.AsyncClient() as http_client:
        response = await HcxClient(http_client=http_client, api_key=api_key).generate(
            request, request_id="finproof-live-auth-smoke"
        )

    assert response.status_code == "20000"
    assert response.message_content


@pytest.mark.asyncio
async def test_live_hcx_007_structured_outputs_capability() -> None:
    api_key = SecretStr(os.environ["FINPROOF_HCX_API_KEY"])
    request = HcxRequest.structured(
        model_name="HCX-007",
        messages=(HcxMessage(role="user", content="Return an object with ok=true."),),
        schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        max_completion_tokens=32,
        temperature=0.0,
        seed=17,
    )

    async with httpx.AsyncClient() as http_client:
        response = await HcxClient(http_client=http_client, api_key=api_key).generate(
            request, request_id="finproof-live-smoke"
        )

    assert response.status_code == "20000"
    assert json.loads(response.message_content) == {"ok": True}
