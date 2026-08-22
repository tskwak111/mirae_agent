import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import httpx
import pytest
import pytest_asyncio
import respx
from pydantic import SecretStr

from finproof.planner.hcx_client import (
    HcxApiStatusError,
    HcxClient,
    HcxHttpError,
    HcxMalformedResponseError,
    HcxNoContentError,
    HcxRateLimitError,
    HcxResponseTooLargeError,
    HcxTimeoutKind,
    HcxTransportError,
)
from finproof.planner.models import HcxMessage, HcxRequest

_URL = "https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-007"
_RATE_HEADERS = {
    "x-ratelimit-limit-requests": "60",
    "x-ratelimit-remaining-requests": "59",
    "x-ratelimit-reset-requests": "23s",
    "x-ratelimit-limit-tokens": "60000",
    "x-ratelimit-remaining-tokens": "58700",
    "x-ratelimit-reset-tokens": "41s",
}


class _OversizedChunkedStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"{" + b"x" * HcxClient.MAX_RESPONSE_BYTES


def _fixture(name: str) -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(Path(f"tests/fixtures/hcx/{name}.json").read_text(encoding="utf-8")),
    )


def _valid_request() -> HcxRequest:
    return HcxRequest.strict_json(
        model_name="HCX-007",
        messages=(HcxMessage(role="user", content="question"),),
        max_completion_tokens=1200,
        temperature=0.0,
        seed=17,
    )


@pytest_asyncio.fixture
async def hcx_client() -> AsyncIterator[HcxClient]:
    async with httpx.AsyncClient() as http_client:
        yield HcxClient(http_client=http_client, api_key=SecretStr("secret"))


@pytest.mark.asyncio
async def test_hcx_client_posts_headers_and_parses_message(
    hcx_client: HcxClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.post(_URL).respond(
        200,
        json=_fixture("structured_success"),
        headers=_RATE_HEADERS,
    )

    response = await hcx_client.generate(_valid_request(), request_id="req-1")

    assert route.called
    sent = route.calls[0].request
    assert sent.headers["Authorization"] == "Bearer secret"
    assert sent.headers["X-NCP-CLOVASTUDIO-REQUEST-ID"] == "req-1"
    assert sent.headers["Content-Type"] == "application/json"
    assert set(sent.extensions["timeout"]) == {"connect", "read", "write", "pool"}
    assert all(value is not None for value in sent.extensions["timeout"].values())
    assert response.status_code == "20000"
    assert response.message_content == '{"intent":"lookup"}'
    assert response.usage.prompt_tokens == 843
    assert response.usage.completion_tokens == 80
    assert response.usage.total_tokens == 923
    assert response.rate_limits.limit_requests == 60
    assert response.rate_limits.remaining_requests == 59
    assert response.rate_limits.reset_requests_seconds == 23.0
    assert response.rate_limits.limit_tokens == 60000
    assert response.rate_limits.remaining_tokens == 58700
    assert response.rate_limits.reset_tokens_seconds == 41.0


@pytest.mark.asyncio
async def test_non_20000_api_status_is_typed_error(
    hcx_client: HcxClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(_URL).respond(
        200,
        json={"status": {"code": "40000", "message": "Bad request"}},
    )

    with pytest.raises(HcxApiStatusError) as caught:
        await hcx_client.generate(_valid_request(), request_id="req-1")

    assert caught.value.status_code == "40000"


@pytest.mark.asyncio
async def test_20400_without_message_is_no_content_error(
    hcx_client: HcxClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(_URL).respond(200, json=_fixture("no_content_20400"))

    with pytest.raises(HcxNoContentError):
        await hcx_client.generate(_valid_request(), request_id="req-1")


@pytest.mark.asyncio
async def test_empty_http_204_is_no_content_error(
    hcx_client: HcxClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(_URL).respond(204)

    with pytest.raises(HcxNoContentError):
        await hcx_client.generate(_valid_request(), request_id="req-1")


@pytest.mark.asyncio
async def test_malformed_body_is_typed_error(
    hcx_client: HcxClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(_URL).respond(200, json=_fixture("malformed_success"))

    with pytest.raises(HcxMalformedResponseError):
        await hcx_client.generate(_valid_request(), request_id="req-1")


@pytest.mark.asyncio
async def test_oversized_stream_stops_before_json_parse(
    hcx_client: HcxClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(_URL).mock(httpx.Response(200, stream=_OversizedChunkedStream()))

    with pytest.raises(HcxResponseTooLargeError):
        await hcx_client.generate(_valid_request(), request_id="req-1")


@pytest.mark.parametrize("api_status", ["42900", "42901", "42902"])
@pytest.mark.asyncio
async def test_429_api_status_is_rate_limit_error(
    api_status: str, hcx_client: HcxClient, respx_mock: respx.MockRouter
) -> None:
    body = _fixture("error_429")
    status = body["status"]
    assert isinstance(status, dict)
    status["code"] = api_status
    respx_mock.post(_URL).respond(429, json=body, headers=_RATE_HEADERS)

    with pytest.raises(HcxRateLimitError) as caught:
        await hcx_client.generate(_valid_request(), request_id="req-1")

    assert caught.value.status_code == api_status
    assert caught.value.rate_limits.reset_requests_seconds == 23.0


@pytest.mark.parametrize(
    ("timeout_type", "expected_kind"),
    [
        (httpx.ConnectTimeout, HcxTimeoutKind.CONNECT),
        (httpx.ReadTimeout, HcxTimeoutKind.READ),
        (httpx.WriteTimeout, HcxTimeoutKind.WRITE),
        (httpx.PoolTimeout, HcxTimeoutKind.POOL),
    ],
)
@pytest.mark.asyncio
async def test_timeout_is_mapped_to_stable_transport_category(
    timeout_type: type[httpx.TimeoutException],
    expected_kind: HcxTimeoutKind,
    hcx_client: HcxClient,
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(_URL).mock(side_effect=timeout_type("provider timeout"))

    with pytest.raises(HcxTransportError) as caught:
        await hcx_client.generate(_valid_request(), request_id="req-1")

    assert caught.value.timeout_kind is expected_kind


@pytest.mark.asyncio
async def test_non_success_http_status_is_typed_error(
    hcx_client: HcxClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(_URL).respond(503, content=b"unavailable")

    with pytest.raises(HcxHttpError) as caught:
        await hcx_client.generate(_valid_request(), request_id="req-1")

    assert caught.value.http_status == 503


@pytest.mark.asyncio
async def test_error_surface_redacts_key_and_raw_body(
    hcx_client: HcxClient, respx_mock: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    sensitive_body = "raw-provider-value"
    respx_mock.post(_URL).respond(200, content=sensitive_body)

    with pytest.raises(HcxMalformedResponseError) as caught:
        await hcx_client.generate(_valid_request(), request_id="req-1")

    exposed = f"{caught.value!r}\n{caplog.text}"
    assert "secret" not in exposed
    assert sensitive_body not in exposed
