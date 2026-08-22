import ast
from pathlib import Path

from finproof.core.settings import Settings
from finproof.planner.hcx_client import HcxClient


def test_runtime_network_boundary_is_fixed_to_hcx() -> None:
    assert HcxClient.API_ORIGIN == "https://clovastudio.stream.ntruss.com"
    assert "hcx_base_url" not in Settings.model_fields
    assert "hcx_structured_enabled" not in Settings.model_fields


def test_httpx_is_confined_to_the_hcx_transport_boundary() -> None:
    importers: list[Path] = []
    for path in Path("src/finproof").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            (isinstance(node, ast.Import) and any(alias.name == "httpx" for alias in node.names))
            or (isinstance(node, ast.ImportFrom) and node.module == "httpx")
            for node in ast.walk(tree)
        ):
            importers.append(path)

    assert importers == [Path("src/finproof/planner/hcx_client.py")]


def test_hcx_client_does_not_own_the_shared_http_client_lifecycle() -> None:
    assert not hasattr(HcxClient, "close")
    assert not hasattr(HcxClient, "aclose")
