"""Fresh-process official artifact generation shared by CP8 acceptance tests."""

from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from finproof.core.settings import Settings
from finproof.core.versions import VersionBundle
from finproof.data.artifacts.builder import (
    ArtifactBuildOutcome,
    _build_evaluation_artifacts_with_outcome,
)
from finproof.data.artifacts.config import ArtifactBuildOptions
from finproof.data.artifacts.manifest import ArtifactManifest

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_ROOT = Path("/private/tmp/finproof-task5-official-published")
OUTCOME_PATH = Path("/private/tmp/finproof-task5-official-outcome.json")
MEASUREMENTS_PATH = Path("/private/tmp/finproof-task5-official-measurements.json")
TIMESTAMP = "2026-08-14T00:00:02.123456Z"


@dataclass(frozen=True)
class OfficialArtifactSession:
    root: Path
    outcome: ArtifactBuildOutcome
    wall_seconds: float
    peak_rss_bytes: int
    platform: str


def _normalize_peak_rss(value: int, platform: str) -> int:
    return value if platform == "darwin" else value * 1024


def official_artifact_session() -> OfficialArtifactSession:
    """Build once, then reuse only after complete current-code verification."""
    if OFFICIAL_ROOT.exists() or OUTCOME_PATH.exists() or MEASUREMENTS_PATH.exists():
        if not (OFFICIAL_ROOT.is_dir() and OUTCOME_PATH.is_file() and MEASUREMENTS_PATH.is_file()):
            raise RuntimeError("partial official artifact cache exists")
        outcome = ArtifactBuildOutcome.model_validate_json(OUTCOME_PATH.read_bytes(), strict=True)
        manifest = ArtifactManifest.load(OFFICIAL_ROOT / "manifest.json")
        if (
            manifest.verify(OFFICIAL_ROOT).logical_contract != outcome.logical_contract
            or manifest != outcome.manifest
        ):
            raise RuntimeError("official artifact cache failed current-code verification")
        measured = json.loads(MEASUREMENTS_PATH.read_bytes())
        return OfficialArtifactSession(
            root=OFFICIAL_ROOT,
            outcome=outcome,
            wall_seconds=float(measured["wall_seconds"]),
            peak_rss_bytes=int(measured["peak_rss_bytes"]),
            platform=str(measured["platform"]),
        )

    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    started = time.monotonic()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.helpers.official_artifact_subprocess",
            "--child",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wall_seconds = time.monotonic() - started
    stdout = completed.stdout.encode("utf-8")
    if stdout.count(b"\n") != 1:
        raise RuntimeError("official artifact child emitted noncanonical stdout")
    outcome = ArtifactBuildOutcome.model_validate_json(stdout, strict=True)
    manifest = ArtifactManifest.load(OFFICIAL_ROOT / "manifest.json")
    if (
        manifest.verify(OFFICIAL_ROOT).logical_contract != outcome.logical_contract
        or manifest != outcome.manifest
    ):
        raise RuntimeError("official artifact child failed parent verification")
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    peak_rss_bytes = _normalize_peak_rss(int(rss), sys.platform)
    if rss < before:
        raise RuntimeError("child RSS high-water mark moved backwards")
    OUTCOME_PATH.write_bytes(stdout)
    MEASUREMENTS_PATH.write_text(
        json.dumps(
            {
                "wall_seconds": wall_seconds,
                "peak_rss_bytes": peak_rss_bytes,
                "platform": sys.platform,
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return OfficialArtifactSession(
        root=OFFICIAL_ROOT,
        outcome=outcome,
        wall_seconds=wall_seconds,
        peak_rss_bytes=peak_rss_bytes,
        platform=sys.platform,
    )


def _child() -> None:
    from datetime import datetime

    source_root = ROOT / "source_material"
    settings = Settings(
        repository_root=ROOT,
        source_root=source_root,
        data_dir=source_root / "data",
        artifact_dir=OFFICIAL_ROOT,
        database_path=OFFICIAL_ROOT / "finproof.duckdb",
        artifact_build_config_path=ROOT / "config/artifact_build.yaml",
        expected_artifact_contract_path=ROOT / "config/expected_phase1_artifacts.json",
    )
    outcome = _build_evaluation_artifacts_with_outcome(
        settings,
        VersionBundle(),
        options=ArtifactBuildOptions(
            persistence_timestamp=datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00"))
        ),
    )
    sys.stdout.write(outcome.model_dump_json() + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true", required=True)
    parser.parse_args()
    _child()
