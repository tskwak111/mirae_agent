"""Fresh-process official artifact generation shared by CP8 acceptance tests."""

from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
import tempfile
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


def _official_cache_parent(preferred: Path = Path("/private/tmp")) -> Path:
    return preferred if preferred.is_dir() else Path(tempfile.gettempdir())


_CACHE_PARENT = _official_cache_parent()
OFFICIAL_ROOT = _CACHE_PARENT / "finproof-task7-official-published"
OUTCOME_PATH = _CACHE_PARENT / "finproof-task7-official-outcome.json"
MEASUREMENTS_PATH = _CACHE_PARENT / "finproof-task7-official-measurements.json"
TASK7_CANDIDATE_A_ROOT = _CACHE_PARENT / "finproof-task7-candidate-a"
TASK7_CANDIDATE_PACKET = _CACHE_PARENT / "finproof-task7-candidate-pair.json"
TASK7_TIMESTAMP_A = "2026-08-29T00:00:00.000001Z"
TASK7_TIMESTAMP_B = "2026-08-29T00:00:01.999999Z"
TIMESTAMP = TASK7_TIMESTAMP_B


@dataclass(frozen=True)
class OfficialArtifactSession:
    root: Path
    outcome: ArtifactBuildOutcome
    wall_seconds: float
    peak_rss_bytes: int
    platform: str


def scan_official_exact_pairs(source_root: Path) -> frozenset[tuple[str, str]]:
    """Independently scan the sealed official workbooks for exact ETF/fund pairs."""
    from finproof.data.source_manifest import SourceFileManifest
    from finproof.data.xlsx_stream import iter_xlsx_rows

    verified = SourceFileManifest.load(
        source_root / "input_manifest.json",
        source_root / "schema_catalog.json",
    ).verify(source_root)
    domestic_ids: dict[str, set[str]] = {}
    for row in iter_xlsx_rows(verified.data_file("PREF01N001")):
        domestic_ids.setdefault(row.cell("pd_itm_no").raw_value, set()).add(
            row.cell("pd_grp_no").raw_value
        )
    fund_ids: dict[str, set[str]] = {}
    for row in iter_xlsx_rows(verified.data_file("PRFD01N001")):
        identifier = row.cell("ksd_itm_no").raw_value
        if identifier != "":
            fund_ids.setdefault(identifier, set()).add(row.cell("itm_no").raw_value)
    pairs = frozenset(
        (identifier, next(iter(fund_ids[identifier])))
        for identifier, product_types in domestic_ids.items()
        if product_types == {"ETF"} and identifier in fund_ids
    )
    if (
        len(pairs) != 217
        or any(domestic_ids[left] != {"ETF"} for left, _right in pairs)
        or any(len(fund_ids[left]) != 1 for left, _right in pairs)
    ):
        raise RuntimeError("independent official exact-pair scan changed")
    return pairs


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


def _candidate_pair_child() -> None:
    from datetime import datetime
    from importlib import metadata as importlib_metadata

    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    from finproof.data.artifacts.builder import (
        _build_private_live_candidate,
        _discard_live_candidate_to_core_outcome,
        require_exact_link_pair_conservation,
    )
    from finproof.data.artifacts.expected_contract import ExpectedPhase1ArtifactContract

    if any(
        path.exists()
        for path in (
            TASK7_CANDIDATE_A_ROOT,
            OFFICIAL_ROOT,
            OUTCOME_PATH,
            MEASUREMENTS_PATH,
            TASK7_CANDIDATE_PACKET,
        )
    ):
        raise RuntimeError("Task 7 candidate output already exists")
    source_root = ROOT / "source_material"
    pairs = scan_official_exact_pairs(source_root)
    settings_a = Settings(
        repository_root=ROOT,
        source_root=source_root,
        data_dir=source_root / "data",
        artifact_dir=TASK7_CANDIDATE_A_ROOT,
        database_path=TASK7_CANDIDATE_A_ROOT / "finproof.duckdb",
        artifact_build_config_path=ROOT / "config/artifact_build.yaml",
        expected_artifact_contract_path=ROOT / "config/expected_phase1_artifacts.json",
    )
    carrier_a = _build_private_live_candidate(
        settings_a,
        VersionBundle(),
        ArtifactBuildOptions(
            persistence_timestamp=datetime.fromisoformat(TASK7_TIMESTAMP_A.replace("Z", "+00:00"))
        ),
        expected_exact_link_pairs=pairs,
    )
    outcome_a = _discard_live_candidate_to_core_outcome(carrier_a)
    if TASK7_CANDIDATE_A_ROOT.exists():
        raise RuntimeError("Task 7 candidate A did not clean its output root")
    expected = ExpectedPhase1ArtifactContract.model_validate(
        outcome_a.logical_contract.model_dump(mode="python"),
        strict=True,
    )
    provisional = expected.model_dump_json().encode("utf-8") + b"\n"
    distribution = importlib_metadata.distribution("finproof")
    editable_root = Path(str(distribution.locate_file("")))
    editable_expected = Path(
        str(distribution.locate_file("finproof/resources/contracts/expected_phase1_artifacts.json"))
    )
    if not editable_expected.is_relative_to(editable_root):
        raise RuntimeError("editable expected-contract destination escaped its root")
    editable_expected.parent.mkdir(parents=True, exist_ok=True)
    editable_expected.write_bytes(provisional)

    settings_b = Settings(
        repository_root=ROOT,
        source_root=source_root,
        data_dir=source_root / "data",
        artifact_dir=OFFICIAL_ROOT,
        database_path=OFFICIAL_ROOT / "finproof.duckdb",
        artifact_build_config_path=ROOT / "config/artifact_build.yaml",
        expected_artifact_contract_path=ROOT / "config/expected_phase1_artifacts.json",
    )
    started_b = time.monotonic()
    outcome_b = _build_evaluation_artifacts_with_outcome(
        settings_b,
        VersionBundle(),
        options=ArtifactBuildOptions(
            persistence_timestamp=datetime.fromisoformat(TASK7_TIMESTAMP_B.replace("Z", "+00:00"))
        ),
    )
    wall_seconds_b = time.monotonic() - started_b
    table = pq.read_table(
        OFFICIAL_ROOT / "parquet/gold_exact_cross_source_link.parquet",
        columns=["left_product_id", "right_product_id"],
    )
    emitted_pairs = frozenset(
        zip(
            table.column("left_product_id").to_pylist(),
            table.column("right_product_id").to_pylist(),
            strict=True,
        )
    )
    require_exact_link_pair_conservation(
        emitted_pairs=emitted_pairs,
        independently_scanned_pairs=pairs,
    )
    contract_a = outcome_a.logical_contract.model_dump_json()
    contract_b = outcome_b.logical_contract.model_dump_json()
    if contract_a != contract_b:
        raise RuntimeError("Task 7 candidate logical contracts differ")
    outcome_payload = outcome_b.model_dump_json().encode("utf-8") + b"\n"
    OUTCOME_PATH.write_bytes(outcome_payload)
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    MEASUREMENTS_PATH.write_text(
        json.dumps(
            {
                "wall_seconds": wall_seconds_b,
                "peak_rss_bytes": _normalize_peak_rss(int(peak_rss), sys.platform),
                "platform": sys.platform,
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    packet = {
        "candidate_a_root": TASK7_CANDIDATE_A_ROOT.as_posix(),
        "candidate_b_root": OFFICIAL_ROOT.as_posix(),
        "timestamp_a": TASK7_TIMESTAMP_A,
        "timestamp_b": TASK7_TIMESTAMP_B,
        "independent_pair_count": len(pairs),
        "contract": json.loads(contract_b),
        "telemetry_a": outcome_a.telemetry.model_dump(mode="json"),
        "telemetry_b": outcome_b.telemetry.model_dump(mode="json"),
    }
    TASK7_CANDIDATE_PACKET.write_text(
        json.dumps(packet, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(
        json.dumps(
            {
                "candidate_a": TASK7_TIMESTAMP_A,
                "candidate_b": TASK7_TIMESTAMP_B,
                "pairs": len(pairs),
                "packet": TASK7_CANDIDATE_PACKET.as_posix(),
            },
            separators=(",", ":"),
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--child", action="store_true")
    mode.add_argument("--candidate-pair-child", action="store_true")
    args = parser.parse_args()
    if args.candidate_pair_child:
        _candidate_pair_child()
    else:
        _child()
