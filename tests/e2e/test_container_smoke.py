"""Dynamic Docker smoke and fail-closed startup checks."""

import json
import os
import shutil
import socket
import stat
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator

from tests.helpers.official_artifact_subprocess import OfficialArtifactSession

_RUN = os.getenv("FINPROOF_RUN_DOCKER_SMOKE") == "1"
_IMAGE = os.getenv("FINPROOF_IMAGE")
_DOCKER = shutil.which("docker")


def _docker_available() -> bool:
    return (
        _DOCKER is not None
        and subprocess.run(  # noqa: S603 -- resolved Docker executable
            [_DOCKER, "info"], capture_output=True, check=False
        ).returncode
        == 0
    )


pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not _RUN or not _IMAGE or not _docker_available(),
        reason="explicit Docker smoke image and available daemon required",
    ),
]


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _port_open(port: int) -> bool:
    with socket.socket() as client:
        client.settimeout(0.1)
        return client.connect_ex(("127.0.0.1", port)) == 0


@contextmanager
def _readable_mount(root: Path) -> Iterator[Path]:
    original: list[tuple[Path, int]] = []
    try:
        for path in (root, *sorted(root.rglob("*"))):
            observed = path.stat(follow_symlinks=False)
            if stat.S_ISLNK(observed.st_mode):
                raise ValueError("verified artifact mount contains a symbolic link")
            mode = stat.S_IMODE(observed.st_mode)
            original.append((path, mode))
            os.chmod(
                path,
                mode | (0o055 if stat.S_ISDIR(observed.st_mode) else 0o044),
                follow_symlinks=False,
            )
        yield root
    finally:
        for path, mode in reversed(original):
            os.chmod(path, mode, follow_symlinks=False)


@contextmanager
def _container(artifact_root: Path, port: int) -> Iterator[str]:
    if _DOCKER is None or _IMAGE is None:
        raise RuntimeError("Docker smoke selector differs")
    name = f"finproof-task5-{uuid4().hex[:12]}"
    completed = subprocess.run(  # noqa: S603 -- closed Docker CLI arguments
        [
            _DOCKER,
            "run",
            "--detach",
            "--name",
            name,
            "--publish",
            f"127.0.0.1:{port}:8000",
            "--mount",
            f"type=bind,src={artifact_root},dst=/app/artifacts,readonly",
            "--env",
            "FINPROOF_EXECUTION_MODE=extended_demo",
            "--env",
            "FINPROOF_HCX_ENABLED=false",
            _IMAGE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        yield completed.stdout.strip()
    finally:
        subprocess.run(  # noqa: S603 -- closed Docker CLI arguments
            [_DOCKER, "rm", "--force", name], capture_output=True, check=False
        )


def _wait_for_port(port: int, container_id: str, timeout: float = 3_600.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_open(port):
            return
        assert _DOCKER is not None
        state = subprocess.run(  # noqa: S603 -- closed Docker CLI arguments
            [_DOCKER, "inspect", "--format", "{{.State.Running}}", container_id],
            capture_output=True,
            check=False,
            text=True,
        )
        if state.stdout.strip() == "false":
            logs = subprocess.run(  # noqa: S603 -- closed Docker CLI arguments
                [_DOCKER, "logs", container_id], capture_output=True, check=False, text=True
            )
            raise AssertionError(f"container exited before binding: {logs.stderr[-1000:]}")
        time.sleep(0.1)
    raise AssertionError("container did not bind within the startup bound")


def _wait_for_application(port: int, container_id: str, timeout: float = 3_600.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/version", timeout=0.2):
                raise AssertionError("unexpected public version route")
        except HTTPError as missing:
            if missing.code == 404:
                missing.close()
                return
            raise
        except OSError:
            pass
        assert _DOCKER is not None
        state = subprocess.run(  # noqa: S603 -- closed Docker CLI arguments
            [_DOCKER, "inspect", "--format", "{{.State.Running}}", container_id],
            capture_output=True,
            check=False,
            text=True,
        )
        if state.stdout.strip() == "false":
            logs = subprocess.run(  # noqa: S603 -- closed Docker CLI arguments
                [_DOCKER, "logs", container_id], capture_output=True, check=False, text=True
            )
            raise AssertionError(f"container exited during startup: {logs.stderr[-1000:]}")
        time.sleep(0.1)
    raise AssertionError("application did not become ready within the startup bound")


def test_container_answers_from_read_only_expected_verified_artifacts(
    official_artifact_session: OfficialArtifactSession,
) -> None:
    port = _free_port()
    original_modes = tuple(
        stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
        for path in (
            official_artifact_session.root,
            official_artifact_session.root / "manifest.json",
        )
    )
    with (
        _readable_mount(official_artifact_session.root) as artifact_root,
        _container(artifact_root, port) as container_id,
    ):
        _wait_for_port(port, container_id)
        _wait_for_application(port, container_id)
        with urlopen(
            f"http://127.0.0.1:{port}/answer?"
            + urlencode({"question_id": "DOCKER-1", "question": "국내 ETF 중 추적오차가 낮은 5개"}),
            timeout=15,
        ) as response:
            payload = json.load(response)
        schema = json.loads(Path("schemas/api_response.schema.json").read_bytes())
        Draft202012Validator(schema).validate(payload)
        assert set(payload) == {
            "question_id",
            "question",
            "retrieved_context",
            "think_trace",
            "answer",
        }
        with pytest.raises(HTTPError) as missing:
            urlopen(f"http://127.0.0.1:{port}/version", timeout=5)
        assert missing.value.code == 404
    assert original_modes == tuple(
        stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
        for path in (
            official_artifact_session.root,
            official_artifact_session.root / "manifest.json",
        )
    )


def test_container_exits_before_binding_when_artifacts_are_missing(tmp_path: Path) -> None:
    port = _free_port()
    missing_root = tmp_path / "missing-artifacts"
    missing_root.mkdir()
    with _container(missing_root, port) as container_id:
        assert _DOCKER is not None
        completed = subprocess.run(  # noqa: S603 -- closed Docker CLI arguments
            [_DOCKER, "wait", container_id],
            capture_output=True,
            check=True,
            text=True,
            timeout=15,
        )
        assert completed.stdout.strip() != "0"
        assert not _port_open(port)


def test_container_exits_before_binding_when_manifest_is_tampered(tmp_path: Path) -> None:
    port = _free_port()
    tampered_root = tmp_path / "tampered-artifacts"
    tampered_root.mkdir()
    (tampered_root / "manifest.json").write_text('{"tampered":true}', encoding="utf-8")
    with (
        _readable_mount(tampered_root) as artifact_root,
        _container(artifact_root, port) as container_id,
    ):
        assert _DOCKER is not None
        completed = subprocess.run(  # noqa: S603 -- closed Docker CLI arguments
            [_DOCKER, "wait", container_id],
            capture_output=True,
            check=True,
            text=True,
            timeout=15,
        )
        assert completed.stdout.strip() != "0"
        assert not _port_open(port)
