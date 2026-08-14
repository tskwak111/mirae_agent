"""Strict artifact manifest and descriptor-bound inventory contracts."""

from __future__ import annotations

import os
import shutil
import socket
import stat
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

import pytest
from pydantic import ValidationError

from finproof.data.artifacts.errors import ArtifactContractError
from finproof.data.artifacts.manifest import ArtifactManifest, verify_declared_inventory
from tests.helpers.artifacts import INPUTS, TABLES, manifest_payload, write_artifact_tree

if TYPE_CHECKING:
    from finproof.data.artifacts.hashing import TableSpecIdentity
    from finproof.data.artifacts.manifest import (
        VerifiedPhysicalEntry,
        VerifiedPhysicalInventory,
    )


@dataclass(frozen=True)
class _SyntheticVerifiedTableHandle:
    table_name: str
    entry: VerifiedPhysicalEntry
    row_count: int
    schema_sha256: str
    logical_hash: str


def test_artifact_manifest_exact_valid_shape() -> None:
    manifest = ArtifactManifest.model_validate(manifest_payload(), strict=True)

    assert tuple(ArtifactManifest.model_fields) == (
        "manifest_version",
        "artifact_contract_version",
        "artifact_set_id",
        "dataset_version",
        "persistence_timestamp",
        "source_inputs",
        "versions",
        "files",
        "database_path",
        "database_sha256",
        "tables",
        "logical_hash",
    )
    assert (
        tuple((entry.namespace, entry.path, entry.kind) for entry in manifest.source_inputs)
        == INPUTS
    )
    assert len(manifest.files) == 14
    assert tuple(manifest.tables) == tuple(name for name, _, _ in sorted(TABLES))
    assert isinstance(manifest.tables, MappingProxyType)
    with pytest.raises(TypeError):
        cast(dict[str, Any], manifest.tables)["other"] = manifest.tables["bronze_source_cell"]
    with pytest.raises(ValidationError):
        manifest.logical_hash = "a" * 64


@pytest.mark.parametrize(
    "case",
    [
        "parquet-report-id",
        "parquet-logical-hash",
        "duckdb-report-id",
        "duckdb-logical-hash",
        "report-null-id",
        "report-null-logical-hash",
    ],
)
def test_artifact_file_requires_explicit_report_null_policy(case: str) -> None:
    payload = deepcopy(manifest_payload())
    files = list(payload["files"])
    if case.startswith("parquet-"):
        entry = next(item for item in files if item["kind"] == "parquet")
    elif case.startswith("duckdb-"):
        entry = next(item for item in files if item["kind"] == "duckdb")
    else:
        entry = next(item for item in files if item["kind"] == "report")
    if case.endswith("report-id") or case == "report-null-id":
        entry["report_id"] = None if case == "report-null-id" else "source_audit"
    else:
        entry["logical_hash"] = None if case == "report-null-logical-hash" else "a" * 64
    payload["files"] = tuple(files)

    with pytest.raises(ValueError, match="report"):
        ArtifactManifest.model_validate(payload, strict=True)


@pytest.mark.parametrize(
    "case",
    [
        "manifest-version",
        "artifact-version",
        "artifact-set",
        "dataset-date",
        "naive-time",
        "offset-time",
        "input-order",
        "input-missing",
        "input-duplicate",
        "input-namespace",
        "input-path",
        "input-kind",
        "input-negative-size",
        "input-hash",
        "version-dataset",
        "version-metric",
        "version-state",
        "version-quality",
        "version-rating",
        "version-answer",
        "version-planner",
        "file-order",
        "file-missing",
        "file-duplicate",
        "file-path",
        "file-kind",
        "file-negative-size",
        "file-hash",
        "report-duplicate-id",
        "database-path",
        "database-hash",
        "table-order",
        "table-missing",
        "table-key-name",
        "table-layer",
        "table-grain",
        "table-path",
        "table-negative-count",
        "table-schema-hash",
        "table-logical-hash",
        "table-empty-sort",
        "table-duplicate-sort",
        "table-empty-unique",
        "table-duplicate-unique",
        "manifest-hash",
    ],
)
def test_artifact_manifest_rejects_each_inventory_path_version_and_scalar_mutation(
    case: str,
) -> None:
    payload = deepcopy(manifest_payload())
    if case == "manifest-version":
        payload["manifest_version"] = "2.0.0"
    elif case == "artifact-version":
        payload["artifact_contract_version"] = "2.0.0"
    elif case == "artifact-set":
        payload["artifact_set_id"] = "other"
    elif case == "dataset-date":
        payload["dataset_version"] = date(2026, 7, 10)
    elif case == "naive-time":
        payload["persistence_timestamp"] = datetime(2026, 8, 15)
    elif case == "offset-time":
        payload["persistence_timestamp"] = datetime(
            2026, 8, 15, tzinfo=timezone(timedelta(hours=9))
        )
    elif case.startswith("input-"):
        entries = list(payload["source_inputs"])
        if case == "input-order":
            entries.reverse()
        elif case == "input-missing":
            entries.pop()
        elif case == "input-duplicate":
            entries[-1] = deepcopy(entries[0])
        elif case == "input-namespace":
            entries[0]["namespace"] = "repository"
        elif case == "input-path":
            entries[0]["path"] = "../input_manifest.json"
        elif case == "input-kind":
            entries[0]["kind"] = "other"
        elif case == "input-negative-size":
            entries[0]["size_bytes"] = -1
        else:
            entries[0]["sha256"] = "A" * 64
        payload["source_inputs"] = tuple(entries)
    elif case.startswith("version-"):
        field = {
            "version-dataset": "dataset_version",
            "version-metric": "metric_registry_version",
            "version-state": "state_rule_version",
            "version-quality": "quality_rule_version",
            "version-rating": "rating_rule_version",
            "version-answer": "answer_policy_version",
            "version-planner": "planner_version",
        }[case]
        payload["versions"][field] = date(2026, 7, 10) if field == "dataset_version" else "2.0.0"
    elif case.startswith("file-") or case == "report-duplicate-id":
        entries = list(payload["files"])
        if case == "file-order":
            entries.reverse()
        elif case == "file-missing":
            entries.pop()
        elif case == "file-duplicate":
            entries[-1] = deepcopy(entries[0])
        elif case == "report-duplicate-id":
            reports = [entry for entry in entries if entry["kind"] == "report"]
            reports[0]["report_id"] = reports[1]["report_id"]
        else:
            entry = next(item for item in entries if item["kind"] == "parquet")
            if case == "file-path":
                entry["path"] = "/absolute.parquet"
            elif case == "file-kind":
                entry["kind"] = "other"
            elif case == "file-negative-size":
                entry["size_bytes"] = -1
            else:
                entry["sha256"] = "A" * 64
        payload["files"] = tuple(entries)
    elif case == "database-path":
        payload["database_path"] = "other.duckdb"
    elif case == "database-hash":
        payload["database_sha256"] = "a" * 64
    elif case.startswith("table-"):
        tables = dict(payload["tables"])
        if case == "table-order":
            tables = dict(reversed(tuple(tables.items())))
        elif case == "table-missing":
            tables.pop(next(iter(tables)))
        else:
            key = next(iter(tables))
            table = tables[key]
            if case == "table-key-name":
                table["table_name"] = "other"
            elif case == "table-layer":
                table["layer"] = "other"
            elif case == "table-grain":
                table["grain"] = "other"
            elif case == "table-path":
                table["parquet_path"] = "../other.parquet"
            elif case == "table-negative-count":
                table["row_count"] = -1
            elif case == "table-schema-hash":
                table["schema_sha256"] = "A" * 64
            elif case == "table-logical-hash":
                table["logical_hash"] = "A" * 64
            elif case == "table-empty-sort":
                table["sort_key"] = ()
            elif case == "table-duplicate-sort":
                table["sort_key"] = ("id", "id")
            elif case == "table-empty-unique":
                table["unique_key"] = ()
            else:
                table["unique_key"] = ("id", "id")
        payload["tables"] = tables
    else:
        payload["logical_hash"] = "A" * 64

    with pytest.raises(ValueError, match="validation error"):
        ArtifactManifest.model_validate(payload, strict=True)


def test_manifest_load_parses_only_without_opening_declared_files(
    tmp_path: Path,
) -> None:
    manifest = ArtifactManifest.model_validate(manifest_payload(), strict=True)
    path = tmp_path / "manifest.json"
    path.write_text(manifest.model_dump_json(), encoding="utf-8")

    loaded = ArtifactManifest.load(path)

    assert loaded == manifest
    assert tuple(tmp_path.iterdir()) == (path,)


def test_verified_inventory_exact_tree_and_entry_identities(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    manifest = write_artifact_tree(root)

    with verify_declared_inventory(manifest, root) as inventory:
        assert inventory.manifest_entry.path.as_posix() == "manifest.json"
        assert tuple(entry.path.as_posix() for entry in inventory.declared_entries) == tuple(
            entry.path for entry in manifest.files
        )
        for entry in (inventory.manifest_entry, *inventory.declared_entries):
            assert entry.st_dev > 0
            assert entry.st_ino > 0
            assert entry.file_type > 0
            assert entry.st_nlink == 1


@pytest.mark.parametrize(
    "case",
    [
        "extra-file",
        "extra-directory",
        "file-symlink",
        "directory-symlink",
        "fifo",
        "socket",
        "hardlink",
        "missing-file",
        "wal",
        "case-duplicate",
        "size-mismatch",
        "checksum-mismatch",
    ],
)
def test_verified_inventory_rejects_every_unsafe_tree_shape_without_mutation(
    tmp_path: Path,
    case: str,
) -> None:
    root = tmp_path / "artifacts"
    manifest = write_artifact_tree(root)
    target = root / manifest.files[1].path
    listening_socket: socket.socket | None = None
    if case == "extra-file":
        (root / "extra.txt").write_bytes(b"extra")
    elif case == "extra-directory":
        (root / "extra").mkdir()
    elif case == "file-symlink":
        external = tmp_path / "external.parquet"
        external.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(external)
    elif case == "directory-symlink":
        moved = tmp_path / "moved-parquet"
        (root / "parquet").rename(moved)
        (root / "parquet").symlink_to(moved, target_is_directory=True)
    elif case == "fifo":
        target.unlink()
        os.mkfifo(target)
    elif case == "socket":
        listening_socket = socket.socket(socket.AF_UNIX)
        short_socket = Path("/private/tmp") / f"fp-socket-{os.getpid()}"
        try:
            listening_socket.bind(str(short_socket))
        except OSError:
            listening_socket.close()
            pytest.skip("Unix-domain socket filesystem entries are unavailable")
        short_socket.rename(root / "s.sock")
    elif case == "hardlink":
        target.unlink()
        os.link(root / manifest.files[2].path, target)
    elif case == "missing-file":
        target.unlink()
    elif case == "wal":
        (root / "finproof.duckdb.wal").write_bytes(b"wal")
    elif case == "case-duplicate":
        (root / "FINPROOF.duckdb").write_bytes(b"duplicate")
    elif case == "size-mismatch":
        target.write_bytes(target.read_bytes() + b"x")
    else:
        payload = target.read_bytes()
        target.write_bytes(bytes([payload[0] ^ 1]) + payload[1:])

    snapshots = {
        path: path.read_bytes() for path in root.rglob("*") if stat.S_ISREG(path.lstat().st_mode)
    }
    try:
        with pytest.raises(ArtifactContractError):
            verify_declared_inventory(manifest, root)
    finally:
        if listening_socket is not None:
            listening_socket.close()
        if case == "socket":
            (root / "s.sock").unlink()
    assert all(path.read_bytes() == before for path, before in snapshots.items())


def test_verified_inventory_binds_manifest_to_held_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from finproof.data.artifacts import manifest as manifest_module

    root = tmp_path / "artifacts"
    other_root = tmp_path / "other-artifacts"
    manifest = write_artifact_tree(root)
    other_manifest = write_artifact_tree(other_root).model_copy(update={"logical_hash": "e" * 64})
    (other_root / "manifest.json").write_text(other_manifest.model_dump_json(), encoding="utf-8")
    with pytest.raises(ArtifactContractError):
        verify_declared_inventory(other_manifest, root)

    original_check = manifest_module._check_exact_tree
    swapped = False

    def swap_root_after_check(path: Path, bound: ArtifactManifest) -> None:
        nonlocal swapped
        original_check(path, bound)
        if not swapped:
            swapped = True
            path.rename(tmp_path / "parked-artifacts")
            write_artifact_tree(path)

    monkeypatch.setattr(manifest_module, "_check_exact_tree", swap_root_after_check)
    with pytest.raises(ArtifactContractError):
        verify_declared_inventory(manifest, root)
    assert swapped


@pytest.mark.parametrize("operation", ["require-owned", "open-verified"])
@pytest.mark.parametrize("candidate", ["forged", "copied", "foreign"])
def test_verified_entry_reopen_rejects_forged_foreign_or_copied_entry(
    tmp_path: Path,
    operation: str,
    candidate: str,
) -> None:
    root = tmp_path / "artifacts"
    other_root = tmp_path / "other-artifacts"
    manifest = write_artifact_tree(root)
    other_manifest = write_artifact_tree(other_root)
    with (
        verify_declared_inventory(manifest, root) as inventory,
        verify_declared_inventory(other_manifest, other_root) as other_inventory,
    ):
        owned = inventory.declared_entries[0]
        inventory.require_owned(owned)
        if candidate == "copied":
            unowned = replace(owned)
        elif candidate == "foreign":
            unowned = other_inventory.declared_entries[0]
        else:
            unowned = replace(owned, st_ino=owned.st_ino + 1)
        if operation == "require-owned":
            with pytest.raises(ArtifactContractError):
                inventory.require_owned(unowned)
        else:
            with pytest.raises(ArtifactContractError):
                inventory.open_verified(unowned)


@pytest.mark.parametrize("case", ["leaf-swap", "parent-swap", "root-swap"])
def test_verified_entry_reopen_rejects_each_leaf_parent_and_root_swap(
    tmp_path: Path,
    case: str,
) -> None:
    root = tmp_path / "artifacts"
    manifest = write_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        entry = next(item for item in inventory.declared_entries if item.kind == "parquet")
        target = root.joinpath(*entry.path.parts)
        if case == "leaf-swap":
            replacement = tmp_path / "replacement.parquet"
            replacement.write_bytes(target.read_bytes())
            replacement.replace(target)
        elif case == "parent-swap":
            parked = tmp_path / "parked-parquet"
            (root / "parquet").rename(parked)
            shutil.copytree(parked, root / "parquet")
        else:
            parked = tmp_path / "parked-root"
            root.rename(parked)
            shutil.copytree(parked, root)

        with pytest.raises(ArtifactContractError), inventory.open_verified(entry) as stream:
            stream.read()


@pytest.mark.parametrize("case", ["during-open", "between-stages"])
def test_inventory_detects_same_inode_same_size_byte_mutation_between_stages(
    tmp_path: Path,
    case: str,
) -> None:
    root = tmp_path / "artifacts"
    manifest = write_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        entry = next(item for item in inventory.declared_entries if item.kind == "parquet")
        target = root.joinpath(*entry.path.parts)
        before = target.read_bytes()
        mutated = bytes([before[0] ^ 1]) + before[1:]
        identity = target.lstat()

        if case == "during-open":

            def consume_then_mutate() -> None:
                with inventory.open_verified(entry) as stream:
                    assert stream.read() == before
                    target.write_bytes(mutated)

            with pytest.raises(ArtifactContractError):
                consume_then_mutate()
        else:
            target.write_bytes(mutated)
            with pytest.raises(ArtifactContractError):
                inventory.assert_unchanged()

        after = target.lstat()
        assert (after.st_dev, after.st_ino, after.st_size) == (
            identity.st_dev,
            identity.st_ino,
            identity.st_size,
        )


@pytest.mark.parametrize(
    "missing_support",
    [
        "nofollow-flag",
        "directory-flag",
        "cloexec-flag",
        "open-dir-fd",
        "stat-dir-fd",
        "stat-nofollow",
        "scandir-fd",
    ],
)
def test_inventory_fails_closed_without_descriptor_scandir_or_nofollow_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing_support: str,
) -> None:
    root = tmp_path / "artifacts"
    manifest = write_artifact_tree(root)
    if missing_support == "nofollow-flag":
        monkeypatch.setattr(os, "O_NOFOLLOW", 0)
    elif missing_support == "directory-flag":
        monkeypatch.setattr(os, "O_DIRECTORY", 0)
    elif missing_support == "cloexec-flag":
        monkeypatch.setattr(os, "O_CLOEXEC", 0)
    elif missing_support == "open-dir-fd":
        monkeypatch.setattr(
            os,
            "supports_dir_fd",
            os.supports_dir_fd - {os.open},
        )
    elif missing_support == "stat-dir-fd":
        monkeypatch.setattr(
            os,
            "supports_dir_fd",
            os.supports_dir_fd - {os.stat},
        )
    elif missing_support == "stat-nofollow":
        monkeypatch.setattr(
            os,
            "supports_follow_symlinks",
            os.supports_follow_symlinks - {os.stat},
        )
    else:
        monkeypatch.setattr(
            os,
            "supports_fd",
            os.supports_fd - {os.scandir},
        )

    with pytest.raises(ArtifactContractError):
        verify_declared_inventory(manifest, root)


@pytest.mark.parametrize(
    ("route", "missing"),
    [
        ("candidate", ("table_registry",)),
        ("candidate", ("table_verifier",)),
        ("candidate", ("report_verifier",)),
        ("candidate", ("database_verifier",)),
        (
            "candidate",
            (
                "table_registry",
                "table_verifier",
                "report_verifier",
                "database_verifier",
            ),
        ),
        ("expected", ("table_registry",)),
        ("expected", ("table_verifier",)),
        ("expected", ("report_verifier",)),
        ("expected", ("database_verifier",)),
        ("expected", ("expected_comparator",)),
        (
            "expected",
            (
                "table_registry",
                "table_verifier",
                "report_verifier",
                "database_verifier",
                "expected_comparator",
            ),
        ),
    ],
)
def test_verification_kernel_requires_every_port_before_filesystem_work(
    tmp_path: Path,
    route: str,
    missing: tuple[str, ...],
) -> None:
    from finproof.data.artifacts.errors import ArtifactErrorCode
    from finproof.data.artifacts.manifest import ArtifactVerificationKernel

    ports: dict[str, object | None] = {
        "table_registry": object(),
        "table_verifier": object(),
        "report_verifier": object(),
        "database_verifier": object(),
        "expected_comparator": object(),
    }
    for name in missing:
        ports[name] = None
    kernel = ArtifactVerificationKernel(**cast(Any, ports))
    operation = kernel.verify_candidate_core if route == "candidate" else kernel.verify_expected

    with pytest.raises(ArtifactContractError) as caught:
        operation(
            manifest=ArtifactManifest.model_validate(manifest_payload(), strict=True),
            root=tmp_path / "does-not-exist",
        )

    assert caught.value.code is ArtifactErrorCode.VERIFICATION_INCOMPLETE
    assert caught.value.internal_context == {
        "reason": "missing_verification_ports",
        "ports": "[" + ",".join(f'"{name}"' for name in sorted(set(missing))) + "]",
    }


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "direct-constructor",
        "forged-entry",
        "copied-entry",
        "foreign-entry",
        "closed-owner",
        "closed-result-owner",
        "foreign-owner",
        "reordered-tables",
        "reordered-handles",
        "table-name",
        "table-count",
        "table-schema",
        "table-logical",
        "handle-name",
        "handle-count",
        "handle-schema",
        "handle-logical",
    ],
)
def test_table_verification_result_requires_exact_live_inventory_owned_entries(
    tmp_path: Path,
    case: str,
) -> None:
    from finproof.data.artifacts.expected_contract import ExpectedLogicalTable
    from finproof.data.artifacts.manifest import TableVerificationResult

    if case == "direct-constructor":
        with pytest.raises(TypeError):
            TableVerificationResult()
        return

    root = tmp_path / "artifacts"
    other_root = tmp_path / "other-artifacts"
    manifest = write_artifact_tree(root)
    other_manifest = write_artifact_tree(other_root)
    inventory = verify_declared_inventory(manifest, root)
    other_inventory = verify_declared_inventory(other_manifest, other_root)
    try:
        entries = {entry.path.as_posix(): entry for entry in inventory.declared_entries}
        other_entries = {entry.path.as_posix(): entry for entry in other_inventory.declared_entries}
        tables = tuple(
            ExpectedLogicalTable(
                name=name,
                grain=manifest.tables[name].grain,
                schema_hash=manifest.tables[name].schema_sha256,
                row_count=manifest.tables[name].row_count,
                sort_key=manifest.tables[name].sort_key,
                unique_key=manifest.tables[name].unique_key,
                logical_hash=manifest.tables[name].logical_hash,
            )
            for name, _, _ in TABLES
        )
        handles = tuple(
            _SyntheticVerifiedTableHandle(
                table_name=table.name,
                entry=entries[f"parquet/{table.name}.parquet"],
                row_count=table.row_count,
                schema_sha256=table.schema_hash,
                logical_hash=table.logical_hash,
            )
            for table in tables
        )

        if case == "forged-entry":
            handles = (
                replace(handles[0], entry=replace(handles[0].entry, st_ino=0)),
                *handles[1:],
            )
        elif case == "copied-entry":
            handles = (replace(handles[0], entry=replace(handles[0].entry)), *handles[1:])
        elif case == "foreign-entry":
            handles = (
                replace(
                    handles[0],
                    entry=other_entries[f"parquet/{tables[0].name}.parquet"],
                ),
                *handles[1:],
            )
        elif case == "closed-owner":
            inventory.__exit__()
        elif case == "reordered-tables":
            tables = tuple(reversed(tables))
        elif case == "reordered-handles":
            handles = tuple(reversed(handles))
        elif case.startswith("table-"):
            field = case.removeprefix("table-")
            updates = {
                "name": "other",
                "count": tables[0].row_count + 1,
                "schema": "e" * 64,
                "logical": "e" * 64,
            }
            key = {
                "name": "name",
                "count": "row_count",
                "schema": "schema_hash",
                "logical": "logical_hash",
            }[field]
            tables = (tables[0].model_copy(update={key: updates[field]}), *tables[1:])
        elif case.startswith("handle-"):
            field = case.removeprefix("handle-")
            if field == "name":
                first_handle = replace(handles[0], table_name="other")
            elif field == "count":
                first_handle = replace(handles[0], row_count=handles[0].row_count + 1)
            elif field == "schema":
                first_handle = replace(handles[0], schema_sha256="e" * 64)
            else:
                first_handle = replace(handles[0], logical_hash="e" * 64)
            handles = (first_handle, *handles[1:])

        if case == "valid":
            result = TableVerificationResult.from_verified(
                inventory=inventory,
                tables=tables,
                handles=handles,
            )
            assert result.tables is tables
            assert result.handles is handles
            result.validate_against(inventory)
            return

        if case == "foreign-owner":
            result = TableVerificationResult.from_verified(
                inventory=inventory,
                tables=tables,
                handles=handles,
            )
            with pytest.raises(ArtifactContractError):
                result.validate_against(other_inventory)
            return

        if case == "closed-result-owner":
            result = TableVerificationResult.from_verified(
                inventory=inventory,
                tables=tables,
                handles=handles,
            )
            inventory.__exit__()
            with pytest.raises(ArtifactContractError):
                result.validate_against(inventory)
            return

        with pytest.raises(ArtifactContractError):
            TableVerificationResult.from_verified(
                inventory=inventory,
                tables=tables,
                handles=handles,
            )
    finally:
        inventory.__exit__()
        other_inventory.__exit__()


@pytest.mark.parametrize(
    "fail_at",
    [None, "inventory", "tables", "reports", "overall", "database", "expected", "rescan"],
)
def test_verification_kernel_exact_expected_order_and_short_circuit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_at: str | None,
) -> None:
    from finproof.data.artifacts import manifest as manifest_module
    from finproof.data.artifacts.expected_contract import (
        ExpectedLogicalInput,
        ExpectedLogicalTable,
        ExpectedSemanticReport,
    )
    from finproof.data.artifacts.manifest import (
        ArtifactCoreVerificationResult,
        ArtifactExpectedVerificationResult,
        ArtifactVerificationKernel,
        ReportVerificationResult,
        TableVerificationResult,
    )

    events: list[str] = []
    captured_inventories: list[VerifiedPhysicalInventory] = []
    root = tmp_path / "artifacts"
    manifest = write_artifact_tree(root)
    original_inventory = manifest_module.verify_declared_inventory
    original_rescan = manifest_module.VerifiedPhysicalInventory.assert_unchanged

    def inventory_spy(value: ArtifactManifest, path: Path) -> VerifiedPhysicalInventory:
        events.append("inventory")
        if fail_at == "inventory":
            raise RuntimeError("inventory")
        inventory = original_inventory(value, path)
        captured_inventories.append(inventory)
        return inventory

    def rescan_spy(inventory: VerifiedPhysicalInventory) -> None:
        events.append("rescan")
        if fail_at == "rescan":
            raise RuntimeError("rescan")
        original_rescan(inventory)

    monkeypatch.setattr(manifest_module, "verify_declared_inventory", inventory_spy)
    monkeypatch.setattr(
        manifest_module.VerifiedPhysicalInventory,
        "assert_unchanged",
        rescan_spy,
    )

    class Registry:
        def ordered_specs(self) -> tuple[TableSpecIdentity, ...]:
            return ()

    class TableVerifier:
        def verify_tables(self, **kwargs: Any) -> TableVerificationResult:
            events.append("tables")
            if fail_at == "tables":
                raise RuntimeError("tables")
            inventory = kwargs["inventory"]
            entries = {entry.path.as_posix(): entry for entry in inventory.declared_entries}
            tables = tuple(
                ExpectedLogicalTable(
                    name=name,
                    grain=manifest.tables[name].grain,
                    schema_hash=manifest.tables[name].schema_sha256,
                    row_count=manifest.tables[name].row_count,
                    sort_key=manifest.tables[name].sort_key,
                    unique_key=manifest.tables[name].unique_key,
                    logical_hash=manifest.tables[name].logical_hash,
                )
                for name, _, _ in TABLES
            )
            handles = tuple(
                _SyntheticVerifiedTableHandle(
                    table_name=table.name,
                    entry=entries[f"parquet/{table.name}.parquet"],
                    row_count=table.row_count,
                    schema_sha256=table.schema_hash,
                    logical_hash=table.logical_hash,
                )
                for table in tables
            )
            return TableVerificationResult.from_verified(
                inventory=inventory,
                tables=tables,
                handles=handles,
            )

    report_result = ReportVerificationResult(
        reports=(
            ExpectedSemanticReport(report_id="source_audit", semantic_hash="a" * 64),
            ExpectedSemanticReport(report_id="quality_summary", semantic_hash="b" * 64),
        ),
        exact_link_pair_sha256="c" * 64,
        exact_link_evidence_count=7,
    )

    class ReportVerifier:
        def verify_reports(self, **_kwargs: object) -> ReportVerificationResult:
            events.append("reports")
            if fail_at == "reports":
                raise RuntimeError("reports")
            return report_result

    class DatabaseVerifier:
        def verify_database(self, **_kwargs: object) -> None:
            events.append("database")
            if fail_at == "database":
                raise RuntimeError("database")

    class ExpectedComparator:
        def compare(self, **_kwargs: object) -> None:
            events.append("expected")
            if fail_at == "expected":
                raise RuntimeError("expected")

    def build_core(
        value: ArtifactManifest,
        tables: TableVerificationResult,
        reports: ReportVerificationResult,
    ) -> ArtifactCoreVerificationResult:
        events.append("overall")
        if fail_at == "overall":
            raise RuntimeError("overall")
        return ArtifactCoreVerificationResult(
            artifact_contract_version=value.artifact_contract_version,
            artifact_set_id=value.artifact_set_id,
            dataset_version=value.dataset_version,
            logical_inputs=tuple(
                ExpectedLogicalInput.model_validate(entry.model_dump(), strict=True)
                for entry in value.source_inputs
            ),
            tables=tables.tables,
            reports=reports.reports,
            overall_manifest_logical_hash=value.logical_hash,
            exact_link_pair_sha256=reports.exact_link_pair_sha256,
            exact_link_evidence_count=reports.exact_link_evidence_count,
        )

    monkeypatch.setattr(manifest_module, "_build_core_result", build_core, raising=False)
    kernel = ArtifactVerificationKernel(
        table_registry=Registry(),
        table_verifier=TableVerifier(),
        report_verifier=ReportVerifier(),
        database_verifier=DatabaseVerifier(),
        expected_comparator=ExpectedComparator(),
    )

    if fail_at is None:
        result = kernel.verify_expected(manifest=manifest, root=root)
        assert type(result) is ArtifactExpectedVerificationResult
    else:
        with pytest.raises(RuntimeError, match=fail_at):
            kernel.verify_expected(manifest=manifest, root=root)

    expected_order = [
        "inventory",
        "tables",
        "reports",
        "overall",
        "database",
        "expected",
        "rescan",
    ]
    if fail_at is None:
        assert events == expected_order
    else:
        assert events == expected_order[: expected_order.index(fail_at) + 1]
    for inventory in captured_inventories:
        with pytest.raises(ArtifactContractError):
            _ = inventory.declared_entries


@pytest.mark.parametrize(
    "fail_at",
    [None, "inventory", "tables", "reports", "overall", "database", "rescan"],
)
def test_verification_kernel_candidate_core_skips_only_expected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_at: str | None,
) -> None:
    from finproof.data.artifacts import manifest as manifest_module
    from finproof.data.artifacts.expected_contract import (
        ExpectedLogicalInput,
        ExpectedLogicalTable,
        ExpectedSemanticReport,
    )
    from finproof.data.artifacts.manifest import (
        ArtifactCoreVerificationResult,
        ArtifactVerificationKernel,
        ReportVerificationResult,
        TableVerificationResult,
    )

    events: list[str] = []
    captured_inventories: list[VerifiedPhysicalInventory] = []
    root = tmp_path / "artifacts"
    manifest = write_artifact_tree(root)
    original_inventory = manifest_module.verify_declared_inventory
    original_rescan = manifest_module.VerifiedPhysicalInventory.assert_unchanged

    def inventory_spy(value: ArtifactManifest, path: Path) -> VerifiedPhysicalInventory:
        events.append("inventory")
        if fail_at == "inventory":
            raise RuntimeError("inventory")
        inventory = original_inventory(value, path)
        captured_inventories.append(inventory)
        return inventory

    def rescan_spy(inventory: VerifiedPhysicalInventory) -> None:
        events.append("rescan")
        if fail_at == "rescan":
            raise RuntimeError("rescan")
        original_rescan(inventory)

    monkeypatch.setattr(manifest_module, "verify_declared_inventory", inventory_spy)
    monkeypatch.setattr(
        manifest_module.VerifiedPhysicalInventory,
        "assert_unchanged",
        rescan_spy,
    )

    class Registry:
        def ordered_specs(self) -> tuple[TableSpecIdentity, ...]:
            return ()

    class TableVerifier:
        def verify_tables(self, **kwargs: Any) -> TableVerificationResult:
            events.append("tables")
            if fail_at == "tables":
                raise RuntimeError("tables")
            inventory = kwargs["inventory"]
            entries = {entry.path.as_posix(): entry for entry in inventory.declared_entries}
            tables = tuple(
                ExpectedLogicalTable(
                    name=name,
                    grain=manifest.tables[name].grain,
                    schema_hash=manifest.tables[name].schema_sha256,
                    row_count=manifest.tables[name].row_count,
                    sort_key=manifest.tables[name].sort_key,
                    unique_key=manifest.tables[name].unique_key,
                    logical_hash=manifest.tables[name].logical_hash,
                )
                for name, _, _ in TABLES
            )
            handles = tuple(
                _SyntheticVerifiedTableHandle(
                    table_name=table.name,
                    entry=entries[f"parquet/{table.name}.parquet"],
                    row_count=table.row_count,
                    schema_sha256=table.schema_hash,
                    logical_hash=table.logical_hash,
                )
                for table in tables
            )
            return TableVerificationResult.from_verified(
                inventory=inventory,
                tables=tables,
                handles=handles,
            )

    report_result = ReportVerificationResult(
        reports=(
            ExpectedSemanticReport(report_id="source_audit", semantic_hash="a" * 64),
            ExpectedSemanticReport(report_id="quality_summary", semantic_hash="b" * 64),
        ),
        exact_link_pair_sha256="c" * 64,
        exact_link_evidence_count=7,
    )

    class ReportVerifier:
        def verify_reports(self, **_kwargs: object) -> ReportVerificationResult:
            events.append("reports")
            if fail_at == "reports":
                raise RuntimeError("reports")
            return report_result

    class DatabaseVerifier:
        def verify_database(self, **_kwargs: object) -> None:
            events.append("database")
            if fail_at == "database":
                raise RuntimeError("database")

    class ForbiddenExpectedComparator:
        def compare(self, **_kwargs: object) -> None:
            raise AssertionError("candidate core called expected comparator")

    def build_core(
        value: ArtifactManifest,
        tables: TableVerificationResult,
        reports: ReportVerificationResult,
    ) -> ArtifactCoreVerificationResult:
        events.append("overall")
        if fail_at == "overall":
            raise RuntimeError("overall")
        return ArtifactCoreVerificationResult(
            artifact_contract_version=value.artifact_contract_version,
            artifact_set_id=value.artifact_set_id,
            dataset_version=value.dataset_version,
            logical_inputs=tuple(
                ExpectedLogicalInput.model_validate(entry.model_dump(), strict=True)
                for entry in value.source_inputs
            ),
            tables=tables.tables,
            reports=reports.reports,
            overall_manifest_logical_hash=value.logical_hash,
            exact_link_pair_sha256=reports.exact_link_pair_sha256,
            exact_link_evidence_count=reports.exact_link_evidence_count,
        )

    monkeypatch.setattr(manifest_module, "_build_core_result", build_core)
    kernel = ArtifactVerificationKernel(
        table_registry=Registry(),
        table_verifier=TableVerifier(),
        report_verifier=ReportVerifier(),
        database_verifier=DatabaseVerifier(),
        expected_comparator=ForbiddenExpectedComparator(),
    )

    if fail_at is None:
        result = kernel.verify_candidate_core(manifest=manifest, root=root)
        assert type(result) is ArtifactCoreVerificationResult
    else:
        with pytest.raises(RuntimeError, match=fail_at):
            kernel.verify_candidate_core(manifest=manifest, root=root)

    expected_order = ["inventory", "tables", "reports", "overall", "database", "rescan"]
    if fail_at is None:
        assert events == expected_order
    else:
        assert events == expected_order[: expected_order.index(fail_at) + 1]
    for inventory in captured_inventories:
        with pytest.raises(ArtifactContractError):
            _ = inventory.declared_entries


def test_cp2_exports_no_public_manifest_verify_or_verified_artifact_set() -> None:
    from finproof.data.artifacts import manifest as manifest_module

    assert not hasattr(ArtifactManifest, "verify")
    assert not hasattr(manifest_module, "VerifiedArtifactSet")


def test_verified_inventory_detects_physical_byte_mutation_without_mutating_tree(
    tmp_path: Path,
) -> None:
    from finproof.data.artifacts.errors import ArtifactErrorCode

    root = tmp_path / "artifacts"
    manifest = write_artifact_tree(root)
    with verify_declared_inventory(manifest, root) as inventory:
        entry = next(item for item in inventory.declared_entries if item.kind == "parquet")
        target = root.joinpath(*entry.path.parts)
        before = target.read_bytes()
        mutated = bytes([before[0] ^ 1]) + before[1:]
        target.write_bytes(mutated)
        tree_before = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if stat.S_ISREG(path.lstat().st_mode)
        }

        with pytest.raises(ArtifactContractError) as caught:
            inventory.assert_unchanged()

        assert caught.value.code is ArtifactErrorCode.CHECKSUM_MISMATCH
        assert {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if stat.S_ISREG(path.lstat().st_mode)
        } == tree_before
