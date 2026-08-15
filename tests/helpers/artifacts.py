"""Complete synthetic Task 5 artifact fixtures."""

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final

TABLES: Final[tuple[tuple[str, str, int], ...]] = (
    ("bronze_source_column", "source_column", 207),
    ("bronze_source_row", "source_row", 145_393),
    ("bronze_source_cell", "source_cell", 6_401_851),
    ("silver_bond_instrument", "instrument", 42_394),
    ("silver_domestic_listed_product", "listed_product", 1_733),
    ("silver_overseas_listed_product", "listed_product", 5_646),
    ("silver_fund_item", "fund_item", 11_138),
    ("silver_fund_item_attribute", "fund_attribute", 95_618),
    ("silver_quality_issue", "quality_issue", 4),
    ("gold_exact_cross_source_link", "exact_cross_source_link", 47),
    (
        "gold_exact_cross_source_link_evidence",
        "exact_cross_source_link_evidence",
        371,
    ),
)

INPUTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("source_root", "input_manifest.json", "source_manifest"),
    ("source_root", "schema_catalog.json", "source_schema_catalog"),
    ("repository", "config/artifact_build.yaml", "artifact_build_config"),
    ("repository", "config/datasets.yaml", "dataset_registry"),
    ("repository", "config/quality_rules.yaml", "quality_rule_registry"),
    ("repository", "config/rating_scale.yaml", "rating_scale_registry"),
    ("repository", "config/state_rules.yaml", "state_rule_registry"),
    (
        "repository",
        "schemas/artifact_manifest.schema.json",
        "artifact_manifest_schema",
    ),
    ("repository", "schemas/quality_issue.schema.json", "quality_issue_schema"),
)


def expected_contract_payload(*, json_compatible: bool = False) -> dict[str, Any]:
    """Return one complete official-shaped Phase 1 logical contract fixture."""
    logical_inputs: tuple[dict[str, Any], ...] = tuple(
        {
            "namespace": namespace,
            "path": path,
            "kind": kind,
            "size_bytes": index + 1,
            "sha256": f"{index + 1:064x}",
        }
        for index, (namespace, path, kind) in enumerate(INPUTS)
    )
    tables: tuple[dict[str, Any], ...] = tuple(
        {
            "name": name,
            "grain": grain,
            "schema_hash": f"{index + 20:064x}",
            "row_count": row_count,
            "sort_key": ("id",),
            "unique_key": ("id",),
            "logical_hash": f"{index + 40:064x}",
        }
        for index, (name, grain, row_count) in enumerate(TABLES)
    )
    reports: tuple[dict[str, Any], ...] = (
        {"report_id": "source_audit", "semantic_hash": "a" * 64},
        {"report_id": "quality_summary", "semantic_hash": "b" * 64},
    )
    logical_inputs_output: object = logical_inputs
    tables_output: object = tables
    reports_output: object = reports
    dataset_version: object = date(2026, 7, 11)
    if json_compatible:
        logical_inputs_output = list(logical_inputs)
        tables_output = [
            {
                **table,
                "sort_key": list(table["sort_key"]),
                "unique_key": list(table["unique_key"]),
            }
            for table in tables
        ]
        reports_output = list(reports)
        dataset_version = "2026-07-11"
    return {
        "artifact_contract_version": "1.0.0",
        "artifact_set_id": "finproof-data-artifacts/v1",
        "dataset_version": dataset_version,
        "logical_inputs": logical_inputs_output,
        "tables": tables_output,
        "reports": reports_output,
        "overall_manifest_logical_hash": "c" * 64,
        "exact_link_pair_sha256": (
            "8f1049ae6137dbd2141214248c9871f8c4dcced3fcb81cb7c72c2f0863d3a962"
        ),
        "exact_link_evidence_count": 371,
    }


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def manifest_payload() -> dict[str, Any]:
    """Return one complete strict manifest payload with synthetic identities."""
    table_payloads: dict[str, Any] = {}
    for name, grain, row_count in sorted(TABLES):
        layer = name.split("_", maxsplit=1)[0]
        table_payloads[name] = {
            "table_name": name,
            "layer": layer,
            "grain": grain,
            "parquet_path": f"parquet/{name}.parquet",
            "row_count": row_count,
            "schema_sha256": _digest(f"schema:{name}"),
            "sort_key": ("id",),
            "unique_key": ("id",),
            "logical_hash": _digest(f"logical:{name}"),
        }

    files: list[dict[str, object]] = [
        {
            "path": "finproof.duckdb",
            "kind": "duckdb",
            "size_bytes": 8,
            "sha256": _digest("file:finproof.duckdb"),
            "report_id": None,
            "logical_hash": None,
        }
    ]
    for name, _, _ in TABLES:
        path = f"parquet/{name}.parquet"
        files.append(
            {
                "path": path,
                "kind": "parquet",
                "size_bytes": len(path.encode()),
                "sha256": _digest(f"file:{path}"),
                "report_id": None,
                "logical_hash": None,
            }
        )
    for report_id in ("source_audit", "quality_summary"):
        path = f"reports/{report_id}.json"
        files.append(
            {
                "path": path,
                "kind": "report",
                "size_bytes": len(path.encode()),
                "sha256": _digest(f"file:{path}"),
                "report_id": report_id,
                "logical_hash": _digest(f"report:{report_id}"),
            }
        )
    files.sort(key=lambda item: str(item["path"]))
    return {
        "manifest_version": "1.0.0",
        "artifact_contract_version": "1.0.0",
        "artifact_set_id": "finproof-data-artifacts/v1",
        "dataset_version": date(2026, 7, 11),
        "persistence_timestamp": datetime(2026, 8, 15, tzinfo=UTC),
        "source_inputs": tuple(
            {
                "namespace": namespace,
                "path": path,
                "kind": kind,
                "size_bytes": len(path.encode()),
                "sha256": _digest(f"input:{namespace}:{path}"),
            }
            for namespace, path, kind in INPUTS
        ),
        "versions": {
            "dataset_version": date(2026, 7, 11),
            "metric_registry_version": "1.0.0",
            "state_rule_version": "1.0.0",
            "quality_rule_version": "1.0.0",
            "rating_rule_version": "1.0.0",
            "answer_policy_version": "1.0.0",
            "planner_version": "1.0.0",
        },
        "files": tuple(files),
        "database_path": "finproof.duckdb",
        "database_sha256": _digest("file:finproof.duckdb"),
        "tables": table_payloads,
        "logical_hash": _digest("manifest:logical"),
    }


def write_artifact_tree(root: Path) -> Any:
    """Write one complete synthetic physical tree and return its strict manifest."""
    from finproof.data.artifacts.manifest import ArtifactManifest

    payload = manifest_payload()
    files = list(payload["files"])
    root.mkdir()
    (root / "parquet").mkdir()
    (root / "reports").mkdir()
    for entry in files:
        path = root / entry["path"]
        content = f"synthetic:{entry['path']}\n".encode()
        path.write_bytes(content)
        entry["size_bytes"] = len(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
    database = next(entry for entry in files if entry["kind"] == "duckdb")
    payload["database_sha256"] = database["sha256"]
    payload["files"] = tuple(files)
    manifest = ArtifactManifest.model_validate(payload, strict=True)
    (root / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    return manifest


def write_empty_parquet_artifact_tree(root: Path) -> Any:
    """Write a complete CP2-valid tree with eleven empty real Parquet files."""
    import pyarrow as pa  # type: ignore[import-untyped]
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    from finproof.data.artifacts.hashing import schema_sha256, table_logical_hash
    from finproof.data.artifacts.manifest import ArtifactManifest
    from finproof.data.artifacts.parquet_io import _arrow_schema
    from finproof.data.artifacts.table_specs import TABLE_SPECS

    payload = manifest_payload()
    files = [dict(entry) for entry in payload["files"]]
    root.mkdir()
    (root / "parquet").mkdir()
    (root / "reports").mkdir()

    tables: dict[str, object] = {}
    for spec in TABLE_SPECS:
        path = root / spec.parquet_path
        pq.write_table(
            pa.Table.from_pylist([], schema=_arrow_schema(spec)),
            path,
            compression="zstd",
            compression_level=3,
            write_statistics=True,
            data_page_size=1_048_576,
            row_group_size=65_536,
        )
        logical_hash = table_logical_hash(spec, row_count=0, rows=())
        tables[spec.table_name] = {
            "table_name": spec.table_name,
            "layer": spec.layer,
            "grain": spec.grain,
            "parquet_path": spec.parquet_path,
            "row_count": 0,
            "schema_sha256": schema_sha256(spec),
            "sort_key": spec.sort_key,
            "unique_key": spec.unique_key,
            "logical_hash": logical_hash,
        }

    for entry in files:
        path = root / str(entry["path"])
        if entry["kind"] != "parquet":
            path.write_bytes(f"synthetic:{entry['path']}\n".encode())
        content = path.read_bytes()
        entry["size_bytes"] = len(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
    database = next(entry for entry in files if entry["kind"] == "duckdb")
    payload["database_sha256"] = database["sha256"]
    payload["files"] = tuple(files)
    payload["tables"] = {name: tables[name] for name in sorted(tables)}
    manifest = ArtifactManifest.model_validate(payload, strict=True)
    (root / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    return manifest


class TestUniqueKeyIndex:
    """Bounded test double for the owner-managed unique index capability."""

    __test__ = False

    def __init__(self) -> None:
        self._keys: list[bytes] = []

    def insert_canonical_batch(self, keys: tuple[bytes, ...]) -> None:
        self._keys.extend(keys)

    def assert_unique(self) -> None:
        if len(self._keys) != len(set(self._keys)):
            raise ValueError("duplicate unique key")


class TestVerificationWorkspace:
    """Owner-issued pathless verification-workspace test double."""

    __test__ = False

    def __init__(self) -> None:
        self.unchanged = True

    def create_unique_key_index(self, *, limits: Any) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def opened() -> Any:
            assert limits.batch_rows > 0
            yield TestUniqueKeyIndex()

        return opened()

    def assert_unchanged(self) -> None:
        if not self.unchanged:
            raise ValueError("verification workspace changed")


class TestStageParquetLeaf:
    """Filesystem-backed exact-leaf test capability."""

    __test__ = False

    def __init__(self, root: Path, table_name: str) -> None:
        from pathlib import PurePosixPath

        self._root = root
        self.table_name = table_name
        self.relative_path = PurePosixPath(f"parquet/{table_name}.parquet")
        self._identity: tuple[int, int, int, int, int] | None = None

    def _path(self) -> Path:
        return self._root.joinpath(*self.relative_path.parts)

    def create_exclusive(self) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def opened() -> Any:
            import os
            import stat

            path = self._path()
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(path, flags, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                yield stream
            observed = path.stat(follow_symlinks=False)
            if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
                raise ValueError("stage leaf must be one exact regular inode")
            self._identity = (
                observed.st_dev,
                observed.st_ino,
                observed.st_size,
                stat.S_IFMT(observed.st_mode),
                observed.st_nlink,
            )

        return opened()

    def open_verified(self) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def opened() -> Any:
            import os

            self.assert_unchanged()
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self._path(), flags)
            with os.fdopen(descriptor, "rb") as stream:
                yield stream
            self.assert_unchanged()

        return opened()

    def create_verification_workspace(self) -> Any:
        from contextlib import contextmanager

        @contextmanager
        def opened() -> Any:
            yield TestVerificationWorkspace()

        return opened()

    def assert_unchanged(self) -> None:
        import stat

        observed = self._path().stat(follow_symlinks=False)
        if self._identity != (
            observed.st_dev,
            observed.st_ino,
            observed.st_size,
            stat.S_IFMT(observed.st_mode),
            observed.st_nlink,
        ):
            raise ValueError("stage leaf changed")

    def unlink_if_exact_writer_owned(self) -> None:
        self.assert_unchanged()
        self._path().unlink()


class TestStageArtifactOwner:
    """Exact object-identity registry test owner for CP3 staged capabilities."""

    __test__ = False

    def __init__(self, root: Path, persistence_timestamp: datetime) -> None:
        self._root = root
        self.persistence_timestamp = persistence_timestamp
        self._live = True
        self._leaves: list[TestStageParquetLeaf] = []
        self._pairs: dict[int, tuple[object, object, object, tuple[object, ...]]] = {}
        self._sets: dict[int, tuple[object, object]] = {}

    def claim_parquet_leaf(self, table_name: str) -> TestStageParquetLeaf:
        leaf = TestStageParquetLeaf(self._root, table_name)
        self._leaves.append(leaf)
        return leaf

    def assert_live(self) -> None:
        if not self._live:
            raise ValueError("stage owner closed")

    def close(self) -> None:
        self._live = False

    def require_owned_parquet_leaf(self, leaf: Any) -> None:
        self.assert_live()
        if not any(item is leaf for item in self._leaves):
            raise ValueError("foreign stage leaf")
        leaf.assert_unchanged()

    def _register_staged_verification(self, value: object, handle: object) -> object:
        token = object()
        self._pairs[id(value)] = (
            value,
            handle,
            token,
            self._staged_pair_fingerprint(value, handle),
        )
        return token

    @staticmethod
    def _staged_pair_fingerprint(value: Any, handle: Any) -> tuple[object, ...]:
        try:
            return (
                value.logical.model_dump_json(),
                id(value._leaf),
                value._relative_path,
                value._leaf_identity,
                value.physical_size_bytes,
                value.physical_sha256,
                handle.table_name,
                id(handle._leaf),
                handle._relative_path,
                handle._leaf_identity,
                handle.row_count,
                handle.schema_sha256,
                handle.logical_hash,
                handle.physical_size_bytes,
                handle.physical_sha256,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("unregistered staged verification") from exc

    def _require_registered_staged_verification(
        self, value: object, handle: object, token: object
    ) -> None:
        pair = self._pairs.get(id(value))
        if (
            pair is None
            or pair[0] is not value
            or pair[1] is not handle
            or pair[2] is not token
            or pair[3] != self._staged_pair_fingerprint(value, handle)
        ):
            raise ValueError("unregistered staged verification")

    def _require_registered_staged_handle(self, handle: object, token: object) -> None:
        if not any(
            pair[1] is handle
            and pair[2] is token
            and pair[3] == self._staged_pair_fingerprint(pair[0], handle)
            for pair in self._pairs.values()
        ):
            raise ValueError("unregistered staged handle")

    def _register_staged_set(self, value: object) -> object:
        token = object()
        self._sets[id(value)] = (value, token)
        return token

    def _replace_registered_staged_set(self, previous: object, value: object) -> object:
        pair = self._sets.get(id(previous))
        if pair is None or pair[0] is not previous:
            raise ValueError("superseded staged set")
        token = self._register_staged_set(value)
        del self._sets[id(previous)]
        return token

    def _require_registered_staged_set(self, value: object, token: object) -> None:
        pair = self._sets.get(id(value))
        if pair is None or pair[0] is not value or pair[1] is not token:
            raise ValueError("unregistered staged set")
