"""Timestamp-free Phase 1 artifact reproducibility contracts."""

from datetime import date
from pathlib import Path
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, model_validator

from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.safe_files import SafeFileReadError, read_held_regular_file


class ExpectedLogicalInput(BaseModel):
    """One logical build-input identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    namespace: str
    path: str
    kind: str
    size_bytes: int
    sha256: str


class ExpectedLogicalTable(BaseModel):
    """One logical table identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str
    grain: str
    schema_hash: str
    row_count: int
    sort_key: tuple[str, ...]
    unique_key: tuple[str, ...]
    logical_hash: str


class ExpectedSemanticReport(BaseModel):
    """One deterministic semantic-report identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    report_id: str
    semantic_hash: str


class ExpectedPhase1ArtifactContract(BaseModel):
    """Expected logical identity of a complete Phase 1 artifact set."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    artifact_contract_version: str
    artifact_set_id: str
    dataset_version: date
    logical_inputs: tuple[ExpectedLogicalInput, ...]
    tables: tuple[ExpectedLogicalTable, ...]
    reports: tuple[ExpectedSemanticReport, ...]
    overall_manifest_logical_hash: str
    exact_link_pair_sha256: str
    exact_link_evidence_count: int

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load one canonical JSON expected contract."""
        try:
            return cls.model_validate_json(read_held_regular_file(path), strict=True)
        except (OSError, SafeFileReadError, TypeError, ValueError) as exc:
            raise ArtifactContractError(
                ArtifactErrorCode.UNSAFE_TARGET,
                operation_id="load-expected-contract",
                internal_context={"reason": "unsafe_expected_contract_path"},
            ) from exc

    @model_validator(mode="after")
    def require_official_dataset_date(self) -> Self:
        """Bind expected artifacts to the official Phase 1 snapshot."""
        if self.dataset_version != date(2026, 7, 11):
            raise ValueError("dataset_version must be 2026-07-11")
        observed_inputs = tuple(
            (entry.namespace, entry.path, entry.kind) for entry in self.logical_inputs
        )
        if observed_inputs != _EXPECTED_LOGICAL_INPUTS:
            raise ValueError("logical_inputs must use the exact closed order")
        if tuple(table.name for table in self.tables) != _EXPECTED_TABLE_NAMES:
            raise ValueError("tables must use the exact closed order")
        if tuple(report.report_id for report in self.reports) != (
            "source_audit",
            "quality_summary",
        ):
            raise ValueError("reports must use the exact closed order")
        return self


class ArtifactLogicalContractView(Protocol):
    """Read-only logical identity supplied by a verified artifact set."""

    @property
    def artifact_contract_version(self) -> str: ...

    @property
    def artifact_set_id(self) -> str: ...

    @property
    def dataset_version(self) -> date: ...

    @property
    def logical_inputs(self) -> tuple[ExpectedLogicalInput, ...]: ...

    @property
    def tables(self) -> tuple[ExpectedLogicalTable, ...]: ...

    @property
    def reports(self) -> tuple[ExpectedSemanticReport, ...]: ...

    @property
    def overall_manifest_logical_hash(self) -> str: ...

    @property
    def exact_link_pair_sha256(self) -> str: ...

    @property
    def exact_link_evidence_count(self) -> int: ...


def compare_expected_artifact_contract(
    actual: ArtifactLogicalContractView,
    expected: ExpectedPhase1ArtifactContract,
) -> None:
    """Compare an actual logical contract with its frozen expected identity."""
    try:
        if type(actual.artifact_contract_version) is not str:
            raise TypeError("artifact_contract_version")
        if type(actual.artifact_set_id) is not str:
            raise TypeError("artifact_set_id")
        if type(actual.dataset_version) is not date:
            raise TypeError("dataset_version")
        if type(actual.overall_manifest_logical_hash) is not str:
            raise TypeError("overall_manifest_logical_hash")
        if type(actual.exact_link_pair_sha256) is not str:
            raise TypeError("exact_link_pair_sha256")
        if type(actual.exact_link_evidence_count) is not int:
            raise TypeError("exact_link_evidence_count")
        reconstructed = ExpectedPhase1ArtifactContract.model_validate(
            {
                "artifact_contract_version": actual.artifact_contract_version,
                "artifact_set_id": actual.artifact_set_id,
                "dataset_version": actual.dataset_version,
                "logical_inputs": _strict_actual_entries(
                    actual.logical_inputs, ExpectedLogicalInput
                ),
                "tables": _strict_actual_entries(actual.tables, ExpectedLogicalTable),
                "reports": _strict_actual_entries(actual.reports, ExpectedSemanticReport),
                "overall_manifest_logical_hash": actual.overall_manifest_logical_hash,
                "exact_link_pair_sha256": actual.exact_link_pair_sha256,
                "exact_link_evidence_count": actual.exact_link_evidence_count,
            },
            strict=True,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise _reproducibility_error("invalid_actual_contract") from exc
    if reconstructed != expected:
        raise _reproducibility_error("contract_mismatch")


def _strict_actual_entries[EntryModel: BaseModel](
    entries: object,
    entry_type: type[EntryModel],
) -> tuple[EntryModel, ...]:
    if type(entries) is not tuple:
        raise TypeError("inventory must be an exact tuple")
    validated: list[EntryModel] = []
    for entry in entries:
        if type(entry) is not entry_type:
            raise TypeError("inventory entry has the wrong structural type")
        validated.append(
            entry_type.model_validate(entry.model_dump(mode="python", warnings="none"), strict=True)
        )
    return tuple(validated)


def _reproducibility_error(reason: str) -> ArtifactContractError:
    return ArtifactContractError(
        ArtifactErrorCode.REPRODUCIBILITY_MISMATCH,
        operation_id="compare-artifact-contract",
        internal_context={"reason": reason},
    )


_EXPECTED_LOGICAL_INPUTS = (
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

_EXPECTED_TABLE_NAMES = (
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
