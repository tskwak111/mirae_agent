"""Official CP8 architectural memory and bounded-work evidence."""

import pytest

from tests.helpers.official_artifact_subprocess import (
    OfficialArtifactSession,
    _normalize_peak_rss,
)

pytestmark = pytest.mark.performance


def test_official_artifact_build_reports_bounded_architectural_memory(
    official_artifact_session: OfficialArtifactSession,
) -> None:
    session = official_artifact_session
    telemetry = session.outcome.telemetry

    assert session.wall_seconds > 0
    assert session.peak_rss_bytes > 0
    assert _normalize_peak_rss(7, "darwin") == 7
    assert _normalize_peak_rss(7, "linux") == 7 * 1024
    assert telemetry.max_live_fund_group_rows <= 16
    assert telemetry.max_writer_batch_rows <= 65_536
    assert telemetry.max_verifier_batch_rows <= 65_536
    assert telemetry.max_bronze_reconstruction_cells <= 98
    assert telemetry.linked_domestic_record_json_parses == 217
    assert telemetry.linked_fund_record_json_parses == 217
    assert telemetry.max_live_link_keys <= 217
    assert telemetry.max_live_evidence_keys <= 434
    assert len(telemetry.physical_files) == 16
    for workspace in (telemetry.staging_workspace, telemetry.verifier_workspace):
        assert workspace.mode == 0o700
        assert workspace.marker_owned is True
        assert workspace.containment_verified is True
        assert workspace.cleanup_completed is True
        assert workspace.threads == 1
        assert workspace.memory_limit == "1GiB"
