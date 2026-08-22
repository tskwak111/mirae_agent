import tempfile
from pathlib import Path

from tests.helpers import official_artifact_subprocess


def test_official_cache_parent_falls_back_when_private_tmp_is_absent(
    tmp_path: Path,
) -> None:
    missing_private_tmp = tmp_path / "private-tmp-does-not-exist"

    selected = official_artifact_subprocess._official_cache_parent(missing_private_tmp)

    assert selected == Path(tempfile.gettempdir())
    assert selected.is_dir()
