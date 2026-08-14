"""Strict artifact manifest and descriptor-bound verification foundation."""

import hashlib
import json
import os
import stat
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager, suppress
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Annotated, BinaryIO, Literal, Protocol, Self, cast

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.expected_contract import (
    ArtifactLogicalContractView,
    ExpectedLogicalInput,
    ExpectedLogicalTable,
    ExpectedSemanticReport,
)
from finproof.data.artifacts.hashing import TableSpecIdentity, manifest_logical_hash
from finproof.data.artifacts.resources import artifact_manifest_schema_bytes
from finproof.data.artifacts.safe_files import SafeFileReadError, read_held_regular_file

NonNegativeInt = Annotated[int, Field(ge=0)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ArtifactInput(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: Literal["source_root", "repository"]
    path: str
    kind: str
    size_bytes: NonNegativeInt
    sha256: Sha256


class ArtifactVersions(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    dataset_version: date
    metric_registry_version: Literal["1.0.0"]
    state_rule_version: Literal["1.0.0"]
    quality_rule_version: Literal["1.0.0"]
    rating_rule_version: Literal["1.0.0"]
    answer_policy_version: Literal["1.0.0"]
    planner_version: Literal["1.0.0"]

    @model_validator(mode="after")
    def require_official_dataset_date(self) -> Self:
        if self.dataset_version != date(2026, 7, 11):
            raise ValueError("versions.dataset_version must be 2026-07-11")
        return self


class ArtifactFile(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    path: str
    kind: Literal["parquet", "report", "duckdb"]
    size_bytes: NonNegativeInt
    sha256: Sha256
    report_id: str | None
    logical_hash: Sha256 | None

    @field_validator("path")
    @classmethod
    def require_safe_path(cls, value: str) -> str:
        return _safe_relative_path(value)

    @model_validator(mode="after")
    def require_explicit_report_identity_policy(self) -> Self:
        if self.kind == "report":
            if self.report_id not in {"source_audit", "quality_summary"}:
                raise ValueError("report entries require one closed report_id")
            if self.logical_hash is None:
                raise ValueError("report entries require logical_hash")
        elif self.report_id is not None or self.logical_hash is not None:
            raise ValueError("non-report entries require explicit null report identity")
        return self


class ArtifactTable(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    table_name: str
    layer: Literal["bronze", "silver", "gold"]
    grain: str
    parquet_path: str
    row_count: NonNegativeInt
    schema_sha256: Sha256
    sort_key: tuple[str, ...]
    unique_key: tuple[str, ...]
    logical_hash: Sha256

    @field_validator("parquet_path")
    @classmethod
    def require_safe_parquet_path(cls, value: str) -> str:
        return _safe_relative_path(value)

    @model_validator(mode="after")
    def require_nonempty_unique_keys(self) -> Self:
        for value, field in (
            (self.sort_key, "sort_key"),
            (self.unique_key, "unique_key"),
        ):
            if not value or len(value) != len(set(value)):
                raise ValueError(f"{field} must be nonempty and unique")
            if any(type(name) is not str or not name for name in value):
                raise ValueError(f"{field} entries must be exact nonempty strings")
        return self


class ArtifactManifest(BaseModel):
    """Strict immutable artifact manifest."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    manifest_version: Literal["1.0.0"]
    artifact_contract_version: Literal["1.0.0"]
    artifact_set_id: Literal["finproof-data-artifacts/v1"]
    dataset_version: date
    persistence_timestamp: datetime
    source_inputs: tuple[ArtifactInput, ...]
    versions: ArtifactVersions
    files: tuple[ArtifactFile, ...]
    database_path: str
    database_sha256: Sha256
    tables: Mapping[str, ArtifactTable]
    logical_hash: Sha256

    @classmethod
    def load(cls, path: Path) -> Self:
        """Parse and validate only one descriptor-held manifest leaf."""
        try:
            return cls._from_bytes(read_held_regular_file(path))
        except (
            json.JSONDecodeError,
            OSError,
            SafeFileReadError,
            TypeError,
            ValueError,
        ) as exc:
            raise ArtifactContractError(
                ArtifactErrorCode.MANIFEST_INVALID,
                operation_id="load-artifact-manifest",
                internal_context={"reason": "invalid_manifest"},
            ) from exc

    @classmethod
    def _from_bytes(cls, payload: bytes) -> Self:
        parsed = json.loads(payload, object_pairs_hook=_reject_duplicate_pairs)
        schema = json.loads(
            artifact_manifest_schema_bytes(),
            object_pairs_hook=_reject_duplicate_pairs,
        )
        Draft202012Validator.check_schema(schema)
        errors = tuple(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(parsed)
        )
        if errors:
            raise ValueError("manifest does not satisfy its JSON Schema")
        return cls.model_validate_json(payload, strict=True)

    @field_validator("database_path")
    @classmethod
    def require_safe_database_path(cls, value: str) -> str:
        return _safe_relative_path(value)

    @field_validator("persistence_timestamp")
    @classmethod
    def require_exact_utc(cls, value: datetime) -> datetime:
        offset = value.utcoffset()
        if value.tzinfo is None or offset is None:
            raise ValueError("persistence_timestamp must be timezone-aware UTC")
        if offset.total_seconds() != 0:
            raise ValueError("persistence_timestamp must be UTC")
        return value

    @field_validator("tables")
    @classmethod
    def freeze_tables(cls, value: Mapping[str, ArtifactTable]) -> Mapping[str, ArtifactTable]:
        return MappingProxyType(dict(value))

    @field_serializer("tables")
    def serialize_tables(self, value: Mapping[str, ArtifactTable]) -> dict[str, ArtifactTable]:
        return dict(value)

    @model_validator(mode="after")
    def require_closed_inventories(self) -> Self:
        if self.dataset_version != date(2026, 7, 11):
            raise ValueError("dataset_version must be 2026-07-11")
        observed_inputs = tuple(
            (entry.namespace, entry.path, entry.kind) for entry in self.source_inputs
        )
        if observed_inputs != _INPUT_INVENTORY:
            raise ValueError("source_inputs must use the exact closed order")
        observed_files = tuple((entry.path, entry.kind) for entry in self.files)
        if observed_files != _FILE_INVENTORY:
            raise ValueError("files must use the exact closed order")
        report_ids = tuple(
            entry.report_id
            for entry in self.files
            if entry.kind == "report" and entry.report_id is not None
        )
        if tuple(sorted(report_ids)) != ("quality_summary", "source_audit"):
            raise ValueError("files must contain both report identities exactly once")
        if self.database_path != "finproof.duckdb":
            raise ValueError("database_path must name the sole DuckDB entry")
        database_file = self.files[0]
        if database_file.sha256 != self.database_sha256:
            raise ValueError("database_sha256 must match its file entry")
        if tuple(self.tables) != tuple(sorted(_TABLE_IDENTITIES)):
            raise ValueError("tables must use the exact closed lexical order")
        for name, (layer, grain) in _TABLE_IDENTITIES.items():
            table = self.tables[name]
            if (
                table.table_name != name
                or table.layer != layer
                or table.grain != grain
                or table.parquet_path != f"parquet/{name}.parquet"
            ):
                raise ValueError("table identity does not match its closed registry entry")
        return self


def _safe_relative_path(value: str) -> str:
    if not value or "\\" in value or "\0" in value or "%" in value:
        raise ValueError("path must be a canonical POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise ValueError("path must be a canonical POSIX relative path")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("path contains an unsafe component")
    return value


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


_INPUT_INVENTORY = (
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

_TABLE_IDENTITIES = {
    "bronze_source_column": ("bronze", "source_column"),
    "bronze_source_row": ("bronze", "source_row"),
    "bronze_source_cell": ("bronze", "source_cell"),
    "silver_bond_instrument": ("silver", "instrument"),
    "silver_domestic_listed_product": ("silver", "listed_product"),
    "silver_overseas_listed_product": ("silver", "listed_product"),
    "silver_fund_item": ("silver", "fund_item"),
    "silver_fund_item_attribute": ("silver", "fund_attribute"),
    "silver_quality_issue": ("silver", "quality_issue"),
    "gold_exact_cross_source_link": ("gold", "exact_cross_source_link"),
    "gold_exact_cross_source_link_evidence": (
        "gold",
        "exact_cross_source_link_evidence",
    ),
}

_FILE_INVENTORY = tuple(
    sorted(
        (
            ("finproof.duckdb", "duckdb"),
            *((f"parquet/{name}.parquet", "parquet") for name in _TABLE_IDENTITIES),
            ("reports/source_audit.json", "report"),
            ("reports/quality_summary.json", "report"),
        )
    )
)

_VERIFIED_TABLE_ORDER = (
    "bronze_source_column",
    "bronze_source_row",
    "bronze_source_cell",
    "silver_bond_instrument",
    "silver_domestic_listed_product",
    "silver_overseas_listed_product",
    "silver_fund_item",
    "silver_fund_item_attribute",
    "silver_quality_issue",
    "gold_exact_cross_source_link",
    "gold_exact_cross_source_link_evidence",
)


def verify_declared_inventory(
    manifest: ArtifactManifest, root: Path
) -> "VerifiedPhysicalInventory":
    held_tree: _HeldArtifactTree | None = None
    try:
        _require_descriptor_inventory_support()
        if not root.is_absolute():
            raise ValueError("artifact root must be absolute")
        held_tree = _HeldArtifactTree.open(root)
        _check_exact_tree(root, manifest)
        held_tree.revalidate_ancestors()
        held_tree.open_required_directories()
        held_tree.check_exact_tree(manifest)
        manifest_entry, manifest_payload = held_tree.read_initial_entry(
            PurePosixPath("manifest.json"), "manifest"
        )
        if ArtifactManifest._from_bytes(manifest_payload) != manifest:
            raise ValueError("held manifest does not match supplied manifest")
        declared_with_payloads = tuple(
            held_tree.read_initial_entry(PurePosixPath(entry.path), entry.kind)
            for entry in manifest.files
        )
        declared_entries = tuple(entry for entry, _ in declared_with_payloads)
        for observed, declared in zip(declared_entries, manifest.files, strict=True):
            if observed.size_bytes != declared.size_bytes or observed.sha256 != declared.sha256:
                raise ValueError("declared file size or digest does not match")
        held_tree.revalidate_ancestors()
        held_tree.check_exact_tree(manifest)
        inventory = VerifiedPhysicalInventory(
            manifest=manifest,
            held_tree=held_tree,
            manifest_entry=manifest_entry,
            declared_entries=declared_entries,
        )
        held_tree = None
        return inventory
    except ArtifactContractError as exc:
        raise _inventory_error() from exc
    except (OSError, TypeError, ValueError) as exc:
        raise _inventory_error() from exc
    finally:
        if held_tree is not None:
            with suppress(OSError):
                held_tree.close()


def _check_exact_tree(root: Path, manifest: ArtifactManifest) -> None:
    ephemeral = _HeldArtifactTree.open(root)
    try:
        ephemeral.open_required_directories()
        ephemeral.check_exact_tree(manifest)
    finally:
        ephemeral.close()


def _inventory_error() -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.EXACT_TREE_MISMATCH,
        operation_id="verify-artifact-inventory",
        internal_context={"reason": "unsafe_physical_inventory"},
    )


@dataclass(frozen=True)
class VerifiedPhysicalEntry:
    """One physical leaf identity owned by a live inventory."""

    path: PurePosixPath
    kind: Literal["manifest", "parquet", "report", "duckdb"]
    size_bytes: int
    sha256: str
    st_dev: int
    st_ino: int
    file_type: int
    st_nlink: int


class VerifiedPhysicalInventory(AbstractContextManager["VerifiedPhysicalInventory"]):
    """Live capability over one initially checked physical inventory."""

    def __init__(
        self,
        *,
        manifest: ArtifactManifest,
        held_tree: "_HeldArtifactTree",
        manifest_entry: VerifiedPhysicalEntry,
        declared_entries: tuple[VerifiedPhysicalEntry, ...],
    ) -> None:
        self._manifest = manifest
        self._held_tree = held_tree
        self._manifest_entry = manifest_entry
        self._declared_entries = declared_entries
        self._closed = False

    @property
    def manifest_entry(self) -> VerifiedPhysicalEntry:
        self._require_live()
        return self._manifest_entry

    @property
    def declared_entries(self) -> tuple[VerifiedPhysicalEntry, ...]:
        self._require_live()
        return self._declared_entries

    def __enter__(self) -> Self:
        self._require_live()
        return self

    def __exit__(self, *args: object) -> None:
        self._closed = True
        try:
            self._held_tree.close()
        except OSError as exc:
            raise _inventory_capability_error("descriptor_close_failed") from exc

    def require_owned(self, entry: VerifiedPhysicalEntry) -> None:
        self._require_live()
        if not any(entry is owned for owned in self._declared_entries):
            raise _inventory_capability_error("unowned_entry")

    def open_verified(
        self,
        entry: VerifiedPhysicalEntry,
    ) -> AbstractContextManager[BinaryIO]:
        self.require_owned(entry)
        return self._open_owned_entry(entry)

    @contextmanager
    def _open_owned_entry(self, entry: VerifiedPhysicalEntry) -> Iterator[BinaryIO]:
        stream: BinaryIO | None = None
        try:
            self._held_tree.revalidate_ancestors()
            stream = self._held_tree.open_entry(entry)
            self._require_expected_content(stream, entry)
            stream.seek(0)
        except (OSError, TypeError, ValueError) as exc:
            if stream is not None:
                stream.close()
            raise _inventory_capability_error("verified_reopen_failed") from exc
        with stream:
            yield stream
            self._require_expected_content(stream, entry)
            self._held_tree.revalidate_entry(entry, stream.fileno())
            self._held_tree.revalidate_ancestors()
            self._held_tree.check_exact_tree(self._manifest)

    def assert_unchanged(self) -> None:
        self._require_live()
        try:
            self._held_tree.revalidate_ancestors()
            self._held_tree.check_exact_tree(self._manifest)
            manifest_payload = self._read_entry(self._manifest_entry)
            if (
                ArtifactManifest.model_validate_json(manifest_payload, strict=True)
                != self._manifest
            ):
                raise ValueError("held manifest changed")
            for entry in self._declared_entries:
                with self.open_verified(entry):
                    pass
        except ArtifactContractError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise _inventory_capability_error("inventory_rescan_failed") from exc

    def _require_live(self) -> None:
        if self._closed:
            raise _inventory_capability_error("closed_inventory")

    def _read_entry(self, entry: VerifiedPhysicalEntry) -> bytes:
        with self._held_tree.open_entry(entry) as stream:
            payload = self._require_expected_content(stream, entry)
            self._held_tree.revalidate_entry(entry, stream.fileno())
            return payload

    @staticmethod
    def _require_expected_content(
        stream: BinaryIO,
        entry: VerifiedPhysicalEntry,
    ) -> bytes:
        stream.seek(0)
        payload = stream.read()
        if len(payload) != entry.size_bytes or hashlib.sha256(payload).hexdigest() != entry.sha256:
            raise _checksum_error(entry)
        return payload


class ClosedTableSpecRegistry(Protocol):
    def ordered_specs(self) -> tuple[TableSpecIdentity, ...]: ...


class VerifiedTableHandle(Protocol):
    @property
    def table_name(self) -> str: ...

    @property
    def entry(self) -> VerifiedPhysicalEntry: ...

    @property
    def row_count(self) -> int: ...

    @property
    def schema_sha256(self) -> str: ...

    @property
    def logical_hash(self) -> str: ...


@dataclass(frozen=True, init=False)
class TableVerificationResult:
    tables: tuple[ExpectedLogicalTable, ...]
    handles: tuple[VerifiedTableHandle, ...]

    def __init__(self) -> None:
        raise TypeError("TableVerificationResult requires from_verified")

    @classmethod
    def from_verified(
        cls,
        *,
        inventory: VerifiedPhysicalInventory,
        tables: tuple[ExpectedLogicalTable, ...],
        handles: tuple[VerifiedTableHandle, ...],
    ) -> "TableVerificationResult":
        cls._validate(inventory=inventory, tables=tables, handles=handles)
        result = object.__new__(cls)
        object.__setattr__(result, "tables", tables)
        object.__setattr__(result, "handles", handles)
        object.__setattr__(result, "_owner", inventory)
        return result

    def validate_against(self, inventory: VerifiedPhysicalInventory) -> None:
        if inventory is not getattr(self, "_owner", None):
            raise _table_result_error("foreign_inventory")
        self._validate(inventory=inventory, tables=self.tables, handles=self.handles)

    @staticmethod
    def _validate(
        *,
        inventory: VerifiedPhysicalInventory,
        tables: tuple[ExpectedLogicalTable, ...],
        handles: tuple[VerifiedTableHandle, ...],
    ) -> None:
        try:
            if type(tables) is not tuple or type(handles) is not tuple:
                raise TypeError("table result inventories must be exact tuples")
            if tuple(table.name for table in tables) != _VERIFIED_TABLE_ORDER:
                raise ValueError("logical table inventory has the wrong order")
            if len(handles) != len(_VERIFIED_TABLE_ORDER):
                raise ValueError("verified handle inventory has the wrong length")
            for expected_name, table, handle in zip(
                _VERIFIED_TABLE_ORDER,
                tables,
                handles,
                strict=True,
            ):
                if type(table) is not ExpectedLogicalTable:
                    raise TypeError("logical table has the wrong type")
                entry = handle.entry
                if type(entry) is not VerifiedPhysicalEntry:
                    raise TypeError("verified handle entry has the wrong type")
                inventory.require_owned(entry)
                if entry.path != PurePosixPath(f"parquet/{expected_name}.parquet"):
                    raise ValueError("verified entry path does not match table")
                if (
                    type(handle.table_name) is not str
                    or type(handle.row_count) is not int
                    or type(handle.schema_sha256) is not str
                    or type(handle.logical_hash) is not str
                    or handle.table_name != expected_name
                    or table.name != handle.table_name
                    or table.row_count != handle.row_count
                    or table.schema_hash != handle.schema_sha256
                    or table.logical_hash != handle.logical_hash
                ):
                    raise ValueError("logical table and verified handle differ")
        except ArtifactContractError:
            raise
        except (AttributeError, TypeError, ValueError) as exc:
            raise _table_result_error("invalid_table_verification_result") from exc


class ArtifactTableVerifier(Protocol):
    def verify_tables(
        self,
        *,
        manifest: ArtifactManifest,
        inventory: VerifiedPhysicalInventory,
        specs: tuple[TableSpecIdentity, ...],
    ) -> TableVerificationResult: ...


class ReportVerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    reports: tuple[ExpectedSemanticReport, ...]
    exact_link_pair_sha256: str
    exact_link_evidence_count: int


class ArtifactReportVerifier(Protocol):
    def verify_reports(
        self,
        *,
        manifest: ArtifactManifest,
        inventory: VerifiedPhysicalInventory,
        tables: TableVerificationResult,
    ) -> ReportVerificationResult: ...


class ArtifactCoreVerificationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    artifact_contract_version: str
    artifact_set_id: str
    dataset_version: date
    logical_inputs: tuple[ExpectedLogicalInput, ...]
    tables: tuple[ExpectedLogicalTable, ...]
    reports: tuple[ExpectedSemanticReport, ...]
    overall_manifest_logical_hash: str
    exact_link_pair_sha256: str
    exact_link_evidence_count: int


class ArtifactExpectedVerificationResult(ArtifactCoreVerificationResult):
    pass


class ArtifactDatabaseVerifier(Protocol):
    def verify_database(
        self,
        *,
        manifest: ArtifactManifest,
        inventory: VerifiedPhysicalInventory,
        specs: tuple[TableSpecIdentity, ...],
        tables: TableVerificationResult,
        logical: ArtifactCoreVerificationResult,
    ) -> None: ...


class ArtifactExpectedComparator(Protocol):
    def compare(self, *, actual: ArtifactLogicalContractView) -> None: ...


class ArtifactVerificationKernel:
    def __init__(
        self,
        *,
        table_registry: ClosedTableSpecRegistry | None,
        table_verifier: ArtifactTableVerifier | None,
        report_verifier: ArtifactReportVerifier | None,
        database_verifier: ArtifactDatabaseVerifier | None,
        expected_comparator: ArtifactExpectedComparator | None,
    ) -> None:
        self._table_registry = table_registry
        self._table_verifier = table_verifier
        self._report_verifier = report_verifier
        self._database_verifier = database_verifier
        self._expected_comparator = expected_comparator

    def verify_candidate_core(
        self,
        *,
        manifest: ArtifactManifest,
        root: Path,
    ) -> ArtifactCoreVerificationResult:
        self._require_ports(include_expected=False)
        assert self._table_registry is not None
        assert self._table_verifier is not None
        assert self._report_verifier is not None
        assert self._database_verifier is not None
        with verify_declared_inventory(manifest, root) as inventory:
            specs = self._table_registry.ordered_specs()
            tables = self._table_verifier.verify_tables(
                manifest=manifest,
                inventory=inventory,
                specs=specs,
            )
            tables.validate_against(inventory)
            reports = self._report_verifier.verify_reports(
                manifest=manifest,
                inventory=inventory,
                tables=tables,
            )
            tables.validate_against(inventory)
            logical = _build_core_result(manifest, tables, reports)
            tables.validate_against(inventory)
            self._database_verifier.verify_database(
                manifest=manifest,
                inventory=inventory,
                specs=specs,
                tables=tables,
                logical=logical,
            )
            inventory.assert_unchanged()
            return logical

    def verify_expected(
        self,
        *,
        manifest: ArtifactManifest,
        root: Path,
    ) -> ArtifactExpectedVerificationResult:
        self._require_ports(include_expected=True)
        assert self._table_registry is not None
        assert self._table_verifier is not None
        assert self._report_verifier is not None
        assert self._database_verifier is not None
        assert self._expected_comparator is not None
        with verify_declared_inventory(manifest, root) as inventory:
            specs = self._table_registry.ordered_specs()
            tables = self._table_verifier.verify_tables(
                manifest=manifest,
                inventory=inventory,
                specs=specs,
            )
            tables.validate_against(inventory)
            reports = self._report_verifier.verify_reports(
                manifest=manifest,
                inventory=inventory,
                tables=tables,
            )
            tables.validate_against(inventory)
            logical = _build_core_result(manifest, tables, reports)
            tables.validate_against(inventory)
            self._database_verifier.verify_database(
                manifest=manifest,
                inventory=inventory,
                specs=specs,
                tables=tables,
                logical=logical,
            )
            self._expected_comparator.compare(actual=logical)
            inventory.assert_unchanged()
            return ArtifactExpectedVerificationResult.model_validate(
                logical.model_dump(mode="python"),
                strict=True,
            )

    def _require_ports(self, *, include_expected: bool) -> None:
        ports: dict[str, object | None] = {
            "table_registry": self._table_registry,
            "table_verifier": self._table_verifier,
            "report_verifier": self._report_verifier,
            "database_verifier": self._database_verifier,
        }
        if include_expected:
            ports["expected_comparator"] = self._expected_comparator
        missing = sorted(name for name, port in ports.items() if port is None)
        if missing:
            raise ArtifactContractError(
                ArtifactErrorCode.VERIFICATION_INCOMPLETE,
                operation_id="verify-artifact-set",
                internal_context={
                    "reason": "missing_verification_ports",
                    "ports": json.dumps(missing, separators=(",", ":")),
                },
            )


@dataclass(frozen=True)
class _ManifestLogicalProjection:
    manifest_version: str
    artifact_contract_version: str
    artifact_set_id: str
    dataset_version: date
    logical_inputs: tuple[ExpectedLogicalInput, ...]
    versions: ArtifactVersions
    tables: tuple[ExpectedLogicalTable, ...]
    reports: tuple[ExpectedSemanticReport, ...]


def _build_core_result(
    manifest: ArtifactManifest,
    tables: TableVerificationResult,
    reports: ReportVerificationResult,
) -> ArtifactCoreVerificationResult:
    logical_inputs = tuple(
        ExpectedLogicalInput.model_validate(
            entry.model_dump(mode="python", warnings="none"),
            strict=True,
        )
        for entry in manifest.source_inputs
    )
    projection = _ManifestLogicalProjection(
        manifest_version=manifest.manifest_version,
        artifact_contract_version=manifest.artifact_contract_version,
        artifact_set_id=manifest.artifact_set_id,
        dataset_version=manifest.dataset_version,
        logical_inputs=logical_inputs,
        versions=manifest.versions,
        tables=tables.tables,
        reports=reports.reports,
    )
    observed_hash = manifest_logical_hash(projection)
    if observed_hash != manifest.logical_hash:
        raise ArtifactContractError(
            ArtifactErrorCode.LOGICAL_HASH_MISMATCH,
            operation_id="verify-artifact-logical-hash",
            internal_context={"reason": "manifest_logical_hash_mismatch"},
        )
    return ArtifactCoreVerificationResult(
        artifact_contract_version=manifest.artifact_contract_version,
        artifact_set_id=manifest.artifact_set_id,
        dataset_version=manifest.dataset_version,
        logical_inputs=logical_inputs,
        tables=tables.tables,
        reports=reports.reports,
        overall_manifest_logical_hash=observed_hash,
        exact_link_pair_sha256=reports.exact_link_pair_sha256,
        exact_link_evidence_count=reports.exact_link_evidence_count,
    )


def _stat_identity(value: os.stat_result) -> tuple[int, int, int]:
    return (value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode))


class _HeldArtifactTree:
    """Retained descriptor chain for one closed artifact tree."""

    def __init__(
        self,
        *,
        descriptors: list[int],
        chain_records: list[tuple[int, str, tuple[int, int, int], int]],
        root_fd: int,
    ) -> None:
        self._descriptors = descriptors
        self._chain_records = chain_records
        self._root_fd = root_fd
        self._directory_fds: dict[str, int] = {}
        self._directory_records: dict[str, tuple[int, int, int]] = {}
        self._closed = False

    @classmethod
    def open(cls, root: Path) -> "_HeldArtifactTree":
        descriptors: list[int] = []
        records: list[tuple[int, str, tuple[int, int, int], int]] = []
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            anchor_fd = os.open(root.anchor, flags)
            descriptors.append(anchor_fd)
            anchor_identity = _stat_identity(os.fstat(anchor_fd))
            if anchor_identity[2] != stat.S_IFDIR:
                raise ValueError("filesystem anchor is not a directory")
            parent_fd = anchor_fd
            for component in root.parts[1:]:
                before = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
                if stat.S_IFMT(before.st_mode) != stat.S_IFDIR:
                    raise ValueError("artifact ancestor is not a directory")
                child_fd = os.open(component, flags, dir_fd=parent_fd)
                descriptors.append(child_fd)
                identity = _stat_identity(os.fstat(child_fd))
                if identity != _stat_identity(before):
                    raise ValueError("artifact ancestor changed while opening")
                records.append((parent_fd, component, identity, child_fd))
                parent_fd = child_fd
            return cls(
                descriptors=descriptors,
                chain_records=records,
                root_fd=parent_fd,
            )
        except BaseException:
            for descriptor in reversed(descriptors):
                with suppress(OSError):
                    os.close(descriptor)
            raise

    def open_required_directories(self) -> None:
        self._require_live()
        if self._directory_fds:
            return
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
        for name in ("parquet", "reports"):
            before = os.stat(name, dir_fd=self._root_fd, follow_symlinks=False)
            if stat.S_IFMT(before.st_mode) != stat.S_IFDIR:
                raise ValueError("artifact child directory has an unsafe type")
            child_fd = os.open(name, flags, dir_fd=self._root_fd)
            self._descriptors.append(child_fd)
            identity = _stat_identity(os.fstat(child_fd))
            if identity != _stat_identity(before):
                raise ValueError("artifact child directory changed while opening")
            self._directory_fds[name] = child_fd
            self._directory_records[name] = identity

    def check_exact_tree(self, manifest: ArtifactManifest) -> None:
        self._require_live()
        self.revalidate_ancestors()
        expected_root = {"manifest.json", "finproof.duckdb", "parquet", "reports"}
        if self._scan_names(self._root_fd) != expected_root:
            raise ValueError("artifact root inventory differs")
        for directory_name in ("parquet", "reports"):
            directory_fd = self._directory_fds[directory_name]
            expected = {
                PurePosixPath(entry.path).name
                for entry in manifest.files
                if PurePosixPath(entry.path).parent.as_posix() == directory_name
            }
            if self._scan_names(directory_fd) != expected:
                raise ValueError("artifact child inventory differs")

    def read_initial_entry(
        self,
        path: PurePosixPath,
        kind: Literal["manifest", "parquet", "report", "duckdb"],
    ) -> tuple[VerifiedPhysicalEntry, bytes]:
        parent_fd, name = self._parent_and_name(path)
        before = self._require_regular_leaf(parent_fd, name)
        entry = VerifiedPhysicalEntry(
            path=path,
            kind=kind,
            size_bytes=before.st_size,
            sha256="0" * 64,
            st_dev=before.st_dev,
            st_ino=before.st_ino,
            file_type=stat.S_IFMT(before.st_mode),
            st_nlink=before.st_nlink,
        )
        with self.open_entry(entry, check_digest=False) as stream:
            payload = stream.read()
            self.revalidate_entry(entry, stream.fileno())
        return replace_entry_digest(entry, payload), payload

    def open_entry(
        self,
        entry: VerifiedPhysicalEntry,
        *,
        check_digest: bool = True,
    ) -> BinaryIO:
        del check_digest
        self._require_live()
        parent_fd, name = self._parent_and_name(entry.path)
        before = self._require_regular_leaf(parent_fd, name)
        if (
            _stat_identity(before)
            != (
                entry.st_dev,
                entry.st_ino,
                entry.file_type,
            )
            or before.st_nlink != entry.st_nlink
        ):
            raise ValueError("verified leaf identity changed")
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        opened = os.fstat(descriptor)
        if _stat_identity(opened) != _stat_identity(before) or opened.st_nlink != 1:
            os.close(descriptor)
            raise ValueError("verified leaf changed while opening")
        return cast(BinaryIO, os.fdopen(descriptor, "rb", closefd=True))

    def revalidate_entry(self, entry: VerifiedPhysicalEntry, descriptor: int) -> None:
        parent_fd, name = self._parent_and_name(entry.path)
        opened = os.fstat(descriptor)
        after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        expected = (entry.st_dev, entry.st_ino, entry.file_type)
        if (
            _stat_identity(opened) != expected
            or _stat_identity(after) != expected
            or opened.st_nlink != entry.st_nlink
            or after.st_nlink != entry.st_nlink
        ):
            raise ValueError("verified leaf changed during use")

    def revalidate_ancestors(self) -> None:
        self._require_live()
        for parent_fd, component, expected, child_fd in self._chain_records:
            opened = os.fstat(child_fd)
            after = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
            if _stat_identity(opened) != expected or _stat_identity(after) != expected:
                raise ValueError("artifact ancestor identity changed")
        for name, child_fd in self._directory_fds.items():
            expected = self._directory_records[name]
            opened = os.fstat(child_fd)
            after = os.stat(name, dir_fd=self._root_fd, follow_symlinks=False)
            if _stat_identity(opened) != expected or _stat_identity(after) != expected:
                raise ValueError("artifact directory identity changed")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close_failed = False
        for descriptor in reversed(self._descriptors):
            try:
                os.close(descriptor)
            except OSError:
                close_failed = True
        self._descriptors.clear()
        if close_failed:
            raise OSError("artifact descriptor close failed")

    def _parent_and_name(self, path: PurePosixPath) -> tuple[int, str]:
        if len(path.parts) == 1:
            return self._root_fd, path.name
        if len(path.parts) == 2 and path.parts[0] in self._directory_fds:
            return self._directory_fds[path.parts[0]], path.name
        raise ValueError("artifact entry is outside the closed tree")

    @staticmethod
    def _require_regular_leaf(parent_fd: int, name: str) -> os.stat_result:
        value = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if stat.S_IFMT(value.st_mode) != stat.S_IFREG or value.st_nlink != 1:
            raise ValueError("artifact leaf must be a single-link regular file")
        return value

    @staticmethod
    def _scan_names(directory_fd: int) -> set[str]:
        names: set[str] = set()
        with os.scandir(directory_fd) as entries:
            for entry in entries:
                value = entry.stat(follow_symlinks=False)
                file_type = stat.S_IFMT(value.st_mode)
                if file_type not in {stat.S_IFDIR, stat.S_IFREG}:
                    raise ValueError("artifact inventory contains an unsafe type")
                if entry.name in names:
                    raise ValueError("artifact inventory contains a duplicate name")
                names.add(entry.name)
        return names

    def _require_live(self) -> None:
        if self._closed:
            raise ValueError("artifact descriptor tree is closed")


def replace_entry_digest(
    entry: VerifiedPhysicalEntry,
    payload: bytes,
) -> VerifiedPhysicalEntry:
    return VerifiedPhysicalEntry(
        path=entry.path,
        kind=entry.kind,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        st_dev=entry.st_dev,
        st_ino=entry.st_ino,
        file_type=entry.file_type,
        st_nlink=entry.st_nlink,
    )


def _require_descriptor_inventory_support() -> None:
    if not (
        getattr(os, "O_CLOEXEC", 0)
        and getattr(os, "O_DIRECTORY", 0)
        and getattr(os, "O_NOFOLLOW", 0)
        and os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
        and os.scandir in os.supports_fd
    ):
        raise ValueError("descriptor inventory support is unavailable")


def _inventory_capability_error(reason: str) -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.EXACT_TREE_MISMATCH,
        operation_id="use-artifact-inventory",
        internal_context={"reason": reason},
    )


def _checksum_error(entry: VerifiedPhysicalEntry) -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.CHECKSUM_MISMATCH,
        operation_id="use-artifact-inventory",
        target_basename=entry.path.name,
        internal_context={"reason": "physical_checksum_mismatch"},
    )


def _table_result_error(reason: str) -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.VERIFICATION_INCOMPLETE,
        operation_id="verify-artifact-tables",
        internal_context={"reason": reason},
    )
