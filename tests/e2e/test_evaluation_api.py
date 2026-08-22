"""Production-factory evaluation path over one small verified runtime session."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import duckdb
import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from finproof.api.app import create_app
from finproof.api.dependencies import ApiDependencies
from finproof.core.settings import ExecutionMode, Settings
from finproof.core.versions import VersionBundle
from finproof.data.artifacts.serialization import serialize_table_row
from finproof.data.artifacts.table_specs import TABLE_SPEC_BY_NAME
from finproof.data.normalization.domestic_listed import normalize_domestic_listed
from finproof.registry.loader import RegistryBundle
from finproof.runtime.session import RuntimeArtifactSession
from tests.helpers.artifacts import write_database_artifact_tree
from tests.helpers.query_runtime import verified_artifacts
from tests.helpers.source_rows import source_row


def _recorded_hcx(_: httpx.Request) -> httpx.Response:
    plan = {
        "intent": "screen_rank",
        "product_types": ["domestic_etf"],
        "entities": [],
        "as_of_date": "2026-07-11",
        "result_grain": "listed_product",
        "filters": [],
        "metrics": ["tracking_error"],
        "sort": [{"field": "tracking_error", "direction": "asc"}],
        "aggregation": {"function": "none", "field": "", "group_by": []},
        "top_k": 5,
        "top_k_scope": "global",
        "needs_clarification": False,
        "clarification_reason": "",
    }
    return httpx.Response(
        200,
        json={
            "status": {"code": "20000", "message": "OK"},
            "result": {
                "message": {"role": "assistant", "content": json.dumps(plan)},
                "usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15},
                "finishReason": "stop",
                "seed": 17,
            },
        },
    )


def evaluation_app(
    root: Path,
    handler: httpx.MockTransport,
    *,
    hcx_enabled: bool = True,
) -> FastAPI:
    settings = Settings(
        repository_root=Path.cwd(),
        hcx_enabled=hcx_enabled,
        hcx_api_key=SecretStr("recorded-key") if hcx_enabled else None,
    )
    return create_app(
        settings,
        dependencies=ApiDependencies(
            open_session=lambda _: _small_runtime_session(root),
            http_client_factory=lambda: httpx.AsyncClient(transport=handler),
        ),
    )


@contextmanager
def _small_runtime_session(root: Path) -> Iterator[RuntimeArtifactSession]:
    records = []
    for index in range(5):
        result = normalize_domestic_listed(
            source_row(
                "PREF01N001",
                {
                    "pd_itm_no": f"KR700000000{index}",
                    "pd_itm_no_ma": f"A00000{index}",
                    "pd_nm": f"공동순위 ETF {index}",
                    "pd_abrv_nm": f"공동 {index}",
                    "du_chas_errt": "0",
                },
                excel_row=index + 2,
            ),
            date(2026, 7, 11),
        )
        assert result.record is not None
        records.append(
            dict(
                serialize_table_row(
                    TABLE_SPEC_BY_NAME["silver_domestic_listed_product"], result.record
                )
            )
        )
    artifact_root = root / "artifacts"
    write_database_artifact_tree(
        artifact_root,
        {"silver_domestic_listed_product": tuple(records)},
    )
    connection = duckdb.connect(str(artifact_root / "finproof.duckdb"), read_only=True)
    verified = verified_artifacts()
    registries = RegistryBundle.from_package()
    session = RuntimeArtifactSession._issue(
        connection=connection,
        verified=verified,
        registries=registries,
        versions=VersionBundle.from_runtime(
            verified=verified,
            registries=registries,
            execution_mode=ExecutionMode.EVALUATION,
        ),
    )
    try:
        yield session
    finally:
        session._close()


@pytest.mark.asyncio
async def test_full_question_path_returns_verified_contract(tmp_path: Path) -> None:
    app = evaluation_app(tmp_path, httpx.MockTransport(_recorded_hcx))
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get(
            "/answer",
            params={"question_id": "E2E-1", "question": "국내 ETF 중 추적오차가 낮은 5개"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "question_id",
        "question",
        "retrieved_context",
        "think_trace",
        "answer",
    }
    assert all(type(value) is str for value in payload.values())
    assert "공동" in payload["answer"]
    assert "PREF01N001" in payload["retrieved_context"]
