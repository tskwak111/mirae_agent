"""Shared verified official artifact generation."""

import pytest

from tests.helpers.official_artifact_subprocess import (
    OfficialArtifactSession,
)
from tests.helpers.official_artifact_subprocess import (
    official_artifact_session as load_official_artifact_session,
)


@pytest.fixture(scope="session")
def official_artifact_session() -> OfficialArtifactSession:
    return load_official_artifact_session()
