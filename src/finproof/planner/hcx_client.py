"""Bounded async transport for CLOVA Studio Chat Completions v3."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from enum import StrEnum
from typing import Any, NoReturn, cast
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from finproof.core.errors import FinProofError
from finproof.core.logging import log_hcx_provider_failure
from finproof.planner.models import HcxRequest, HcxResponse, HcxUsage
from finproof.planner.rate_limits import HcxRateLimitSnapshot
from finproof.service.limits import RequestDeadline

type HcxHttpClientFactory = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]


def create_hcx_http_client() -> httpx.AsyncClient:
    """Create the owner-managed HTTP client used by runtime composition."""
    return httpx.AsyncClient()


class HcxClientError(FinProofError):
    """Base error for the HCX transport boundary."""


class HcxTimeoutKind(StrEnum):
    """Stable timeout categories independent of HTTPX exceptions."""

    CONNECT = "connect"
    READ = "read"
    WRITE = "write"
    POOL = "pool"


class HcxTransportError(HcxClientError):
    """The provider could not be reached or timed out."""

    def __init__(self, timeout_kind: HcxTimeoutKind | None = None) -> None:
        self.timeout_kind = timeout_kind
        category = timeout_kind.value if timeout_kind is not None else "network"
        super().__init__(f"HCX transport failure: {category}")


class HcxHttpError(HcxClientError):
    """The provider returned a non-success HTTP status."""

    def __init__(self, http_status: int) -> None:
        self.http_status = http_status
        super().__init__(f"HCX HTTP status: {http_status}")


class HcxApiStatusError(HcxClientError):
    """The provider envelope reported a non-success native status."""

    def __init__(self, status_code: str) -> None:
        self.status_code = status_code
        super().__init__(f"HCX API status: {status_code}")


class HcxNoContentError(HcxApiStatusError):
    """The provider completed successfully without usable content."""


class HcxRateLimitError(HcxApiStatusError):
    """The provider rejected a request due to a rate limit."""

    def __init__(self, status_code: str, rate_limits: HcxRateLimitSnapshot) -> None:
        self.rate_limits = rate_limits
        super().__init__(status_code)


class HcxMalformedResponseError(HcxClientError):
    """The bounded provider response did not satisfy the envelope contract."""

    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(f"malformed HCX response: {category}")


class HcxResponseTooLargeError(HcxClientError):
    """The provider response exceeded the configured hard cap."""

    def __init__(self, maximum_bytes: int) -> None:
        self.maximum_bytes = maximum_bytes
        super().__init__(f"HCX response exceeds {maximum_bytes} bytes")


def _log_hcx_client_error(error: HcxClientError, request_id: str) -> None:
    if isinstance(error, HcxTransportError):
        kind = "transport"
        detail = error.timeout_kind.value if error.timeout_kind is not None else "network"
    elif isinstance(error, HcxRateLimitError):
        kind, detail = "rate_limit", "429"
    elif isinstance(error, HcxHttpError):
        kind, detail = "http", f"{error.http_status // 100}xx"
    elif isinstance(error, HcxNoContentError):
        kind, detail = "no_content", "204"
    elif isinstance(error, HcxApiStatusError):
        kind, detail = "api_status", "non_success"
    elif isinstance(error, HcxMalformedResponseError):
        kind, detail = "malformed_response", error.category
    elif isinstance(error, HcxResponseTooLargeError):
        kind, detail = "response_too_large", "bounded"
    else:
        kind, detail = "client", "unknown"
    log_hcx_provider_failure(
        provider_request_id=request_id,
        provider_error_kind=kind,
        provider_error_detail=detail,
    )


class HcxClient:
    """Low-level, non-retrying HCX client over an owner-managed HTTP client."""

    API_ORIGIN = "https://clovastudio.stream.ntruss.com"
    MAX_RESPONSE_BYTES = 256_000
    _TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)

    def __init__(self, *, http_client: httpx.AsyncClient, api_key: SecretStr) -> None:
        if not api_key.get_secret_value().strip():
            raise ValueError("HCX API key must not be empty")
        self._http_client = http_client
        self._api_key = api_key

    async def generate(
        self,
        request: HcxRequest,
        request_id: str,
        *,
        deadline: RequestDeadline,
    ) -> HcxResponse:
        """Send one bounded request and validate the native response envelope."""
        remaining = deadline.remaining_work_seconds()
        if remaining <= 0:
            raise TimeoutError("HCX work cutoff exceeded")
        url = f"{self.API_ORIGIN}/v3/chat-completions/{quote(request.model_name, safe='')}"
        headers = {
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-NCP-CLOVASTUDIO-REQUEST-ID": request_id,
        }
        try:
            async with self._http_client.stream(
                "POST",
                url,
                json=request.to_payload(),
                headers=headers,
                timeout=httpx.Timeout(
                    timeout=remaining,
                    connect=min(remaining, cast(float, self._TIMEOUT.connect)),
                    read=min(remaining, cast(float, self._TIMEOUT.read)),
                    write=min(remaining, cast(float, self._TIMEOUT.write)),
                    pool=min(remaining, cast(float, self._TIMEOUT.pool)),
                ),
            ) as response:
                body = await self._read_bounded(response)
                return self._parse_response(response, body)
        except HcxClientError as error:
            _log_hcx_client_error(error, request_id)
            raise
        except httpx.ConnectTimeout as error:
            mapped = HcxTransportError(HcxTimeoutKind.CONNECT)
            _log_hcx_client_error(mapped, request_id)
            raise mapped from error
        except httpx.ReadTimeout as error:
            mapped = HcxTransportError(HcxTimeoutKind.READ)
            _log_hcx_client_error(mapped, request_id)
            raise mapped from error
        except httpx.WriteTimeout as error:
            mapped = HcxTransportError(HcxTimeoutKind.WRITE)
            _log_hcx_client_error(mapped, request_id)
            raise mapped from error
        except httpx.PoolTimeout as error:
            mapped = HcxTransportError(HcxTimeoutKind.POOL)
            _log_hcx_client_error(mapped, request_id)
            raise mapped from error
        except httpx.RequestError as error:
            mapped = HcxTransportError()
            _log_hcx_client_error(mapped, request_id)
            raise mapped from error

    async def _read_bounded(self, response: httpx.Response) -> bytes:
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.MAX_RESPONSE_BYTES:
                    raise HcxResponseTooLargeError(self.MAX_RESPONSE_BYTES)
            except ValueError:
                pass

        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self.MAX_RESPONSE_BYTES:
                raise HcxResponseTooLargeError(self.MAX_RESPONSE_BYTES)
            chunks.append(chunk)
        return b"".join(chunks)

    def _parse_response(self, response: httpx.Response, body: bytes) -> HcxResponse:
        rate_limits = HcxRateLimitSnapshot.from_headers(response.headers)
        if response.status_code == 204:
            raise HcxNoContentError("20400")
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            if not response.is_success:
                raise HcxHttpError(response.status_code) from None
            raise HcxMalformedResponseError("invalid_json") from None
        if not isinstance(payload, dict):
            self._raise_malformed_or_http(response, "root_not_object")

        status = payload.get("status")
        if not isinstance(status, dict) or not isinstance(status.get("code"), str):
            self._raise_malformed_or_http(response, "missing_status")
        status_code = status["code"]
        if status_code in {"42900", "42901", "42902"}:
            raise HcxRateLimitError(status_code, rate_limits)
        if not response.is_success:
            raise HcxHttpError(response.status_code)
        if status_code == "20400":
            raise HcxNoContentError(status_code)
        if status_code != "20000":
            raise HcxApiStatusError(status_code)

        result = payload.get("result")
        if not isinstance(result, dict):
            raise HcxMalformedResponseError("missing_result")
        message = result.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise HcxMalformedResponseError("missing_message_content")
        usage = result.get("usage")
        if not isinstance(usage, dict):
            raise HcxMalformedResponseError("missing_usage")

        status_message = status.get("message")
        if not isinstance(status_message, str):
            raise HcxMalformedResponseError("missing_status_message")
        return HcxResponse(
            status_code=status_code,
            status_message=status_message,
            message_content=message["content"],
            usage=HcxUsage(
                prompt_tokens=_required_int(usage, "promptTokens"),
                completion_tokens=_required_int(usage, "completionTokens"),
                total_tokens=_required_int(usage, "totalTokens"),
            ),
            rate_limits=rate_limits,
            created=_optional_int(result, "created"),
            seed=_optional_int(result, "seed"),
            finish_reason=_optional_str(result, "finishReason"),
        )

    @staticmethod
    def _raise_malformed_or_http(response: httpx.Response, category: str) -> NoReturn:
        if not response.is_success:
            raise HcxHttpError(response.status_code)
        raise HcxMalformedResponseError(category)


def _required_int(values: dict[str, Any], field: str) -> int:
    value = values.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise HcxMalformedResponseError(f"invalid_{field}")
    return value


def _optional_int(values: dict[str, Any], field: str) -> int | None:
    value = values.get(field)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise HcxMalformedResponseError(f"invalid_{field}")
    return value


def _optional_str(values: dict[str, Any], field: str) -> str | None:
    value = values.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise HcxMalformedResponseError(f"invalid_{field}")
    return value
