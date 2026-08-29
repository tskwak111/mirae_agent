"""Strict HCX wording parser and exact application-surface contract."""

import json

import pytest

from finproof.answer.hcx_verbalizer import (
    HcxVerbalizer,
    ProviderWordingError,
    build_hcx_answer_schema,
    parse_provider_wording,
)
from finproof.domain.answers import (
    ClaimKind,
    ClaimSignature,
    FactPack,
    ProviderWording,
    SurfacePart,
)
from finproof.planner.models import HcxRequest, HcxResponse, HcxUsage
from finproof.planner.rate_limits import HcxRateLimitSnapshot
from finproof.service.limits import RequestDeadline


def _fact_pack() -> FactPack:
    return FactPack(
        surface_parts=(
            SurfacePart(
                part_id="surface:answer",
                text="2026-08-24 기준 수익률은 3.10%입니다.",
                claim_ids=("claim:return",),
                limitation_codes=("snapshot_assumption",),
            ),
        ),
        claim_signatures=(
            ClaimSignature(
                claim_id="claim:return",
                kind=ClaimKind.NUMERIC,
                surface_text="수익률은 3.10%입니다.",
                entities=(),
                values=(),
                rank=None,
                tie_count=None,
                partition=None,
                comparison=None,
                evidence_ids=(),
                limitation_codes=("snapshot_assumption",),
            ),
        ),
        required_claim_ids=("claim:return",),
        required_limitation_codes=("snapshot_assumption",),
        evidence_context_sha256="a" * 64,
    )


def test_provider_wording_accepts_only_the_exact_issued_tuple() -> None:
    pack = _fact_pack()
    wording = parse_provider_wording(
        json.dumps(
            {
                "answer": pack.surface_parts[0].text,
                "surface_part_ids": ["surface:answer"],
                "claim_ids": ["claim:return"],
                "limitation_codes": ["snapshot_assumption"],
            },
            ensure_ascii=False,
        )
    )

    assert wording == ProviderWording(
        answer=pack.surface_parts[0].text,
        surface_part_ids=("surface:answer",),
        claim_ids=("claim:return",),
        limitation_codes=("snapshot_assumption",),
    )


@pytest.mark.parametrize(
    "change",
    [
        {"extra": "no"},
        {"surface_part_ids": []},
        {"claim_ids": ["claim:return", "claim:return"]},
    ],
)
def test_provider_wording_rejects_schema_extras_and_invalid_ids(
    change: dict[str, object],
) -> None:
    payload: dict[str, object] = {
        "answer": _fact_pack().surface_parts[0].text,
        "surface_part_ids": ["surface:answer"],
        "claim_ids": ["claim:return"],
        "limitation_codes": ["snapshot_assumption"],
    }
    payload.update(change)

    with pytest.raises(ProviderWordingError):
        parse_provider_wording(json.dumps(payload, ensure_ascii=False))


@pytest.mark.asyncio
async def test_verbalizer_emits_the_exact_structured_answer_schema() -> None:
    class RecordingGenerator:
        request: HcxRequest | None = None

        async def generate(
            self,
            request: HcxRequest,
            request_id: str,
            *,
            deadline: RequestDeadline,
        ) -> HcxResponse:
            del request_id, deadline
            self.request = request
            pack = _fact_pack()
            return HcxResponse(
                status_code="20000",
                status_message="OK",
                message_content=json.dumps(
                    {
                        "answer": pack.surface_parts[0].text,
                        "surface_part_ids": ["surface:answer"],
                        "claim_ids": ["claim:return"],
                        "limitation_codes": ["snapshot_assumption"],
                    },
                    ensure_ascii=False,
                ),
                usage=HcxUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
                rate_limits=HcxRateLimitSnapshot(),
            )

    generator = RecordingGenerator()
    await HcxVerbalizer(generator=generator, model_name="HCX-007").verbalize(
        _fact_pack(), request_id="wording-test", deadline=RequestDeadline.start()
    )

    assert generator.request is not None
    assert json.loads(generator.request.response_schema_json or "null") == (
        build_hcx_answer_schema()
    )
    assert generator.request.to_payload()["responseFormat"] == {
        "type": "json",
        "schema": build_hcx_answer_schema(),
    }
    assert generator.request.to_payload()["thinking"] == {"effort": "none"}
