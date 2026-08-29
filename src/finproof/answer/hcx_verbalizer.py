"""Strict HCX answer wording over one application-issued fact surface."""

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError as PydanticValidationError

from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.domain.answers import FactPack, ProviderWording
from finproof.planner.models import HcxMessage, HcxRequest
from finproof.planner.service import HcxGenerator
from finproof.service.limits import RequestDeadline

ANSWER_PROMPT_VERSION = "phase4-answer-v1"
_SCHEMA_PATH = Path(__file__).parents[3] / "schemas/hcx_answer.schema.json"
_RULES = (
    "Return JSON only. Copy the application-issued answer and every ordered ID tuple "
    "exactly. Do not add, remove, reorder, translate, summarize, or change any byte."
)
ANSWER_PROMPT_SHA256 = sha256(_RULES.encode()).hexdigest()


class ProviderWordingError(ValueError):
    """HCX wording failed strict parsing without exposing provider content."""

    def __init__(self, invalid_content: str) -> None:
        self.invalid_content = invalid_content
        super().__init__("provider wording validation failed")


def build_hcx_answer_schema() -> dict[str, Any]:
    value = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("HCX answer schema root must be an object")
    return cast(dict[str, Any], value)


def answer_schema_sha256() -> str:
    return sha256(_SCHEMA_PATH.read_bytes()).hexdigest()


def parse_provider_wording(content: str) -> ProviderWording:
    try:
        payload = json.loads(content, parse_constant=_reject_json_constant)
        if not isinstance(payload, dict):
            raise ValueError
        Draft202012Validator(build_hcx_answer_schema()).validate(payload)
        return ProviderWording.model_validate_json(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        )
    except (
        json.JSONDecodeError,
        JsonSchemaValidationError,
        PydanticValidationError,
        TypeError,
        ValueError,
    ):
        raise ProviderWordingError(content) from None


class HcxVerbalizer:
    """One-call adapter; orchestration owns the single optional wording repair."""

    def __init__(self, *, generator: HcxGenerator, model_name: str) -> None:
        self._generator = generator
        self._model_name = model_name

    async def verbalize(
        self,
        fact_pack: FactPack,
        *,
        request_id: str,
        deadline: RequestDeadline,
    ) -> ProviderWording:
        return await self._attempt(
            fact_pack, request_id=request_id, deadline=deadline, invalid_content=None
        )

    async def repair(
        self,
        fact_pack: FactPack,
        *,
        invalid_content: str,
        request_id: str,
        deadline: RequestDeadline,
    ) -> ProviderWording:
        return await self._attempt(
            fact_pack,
            request_id=request_id,
            deadline=deadline,
            invalid_content=invalid_content,
        )

    async def _attempt(
        self,
        fact_pack: FactPack,
        *,
        request_id: str,
        deadline: RequestDeadline,
        invalid_content: str | None,
    ) -> ProviderWording:
        messages = [HcxMessage(role="system", content=_RULES)]
        messages.append(
            HcxMessage(
                role="user",
                content=canonical_json_bytes(
                    fact_pack.model_dump(mode="json"), terminal_newline=False
                ).decode(),
            )
        )
        if invalid_content is not None:
            messages.extend(
                (
                    HcxMessage(role="assistant", content=invalid_content),
                    HcxMessage(
                        role="user",
                        content="Correct only the JSON or exact-tuple error. Return JSON only.",
                    ),
                )
            )
        request = HcxRequest.structured(
            model_name=self._model_name,
            messages=tuple(messages),
            schema=build_hcx_answer_schema(),
            max_completion_tokens=4_096,
            temperature=0.0,
            seed=17,
        )
        response = await self._generator.generate(
            request,
            request_id=f"{request_id}-wording{'-repair' if invalid_content is not None else ''}",
            deadline=deadline,
        )
        return parse_provider_wording(response.message_content)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")
