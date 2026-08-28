"""Timestamp-free Phase 1 artifact reproducibility contracts."""

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.data.artifacts.errors import ArtifactContractError, ArtifactErrorCode
from finproof.data.artifacts.safe_files import SafeFileReadError, read_held_regular_file

NonNegativeInt = Annotated[int, Field(ge=0)]
ExactLinkEvidenceCount = Annotated[int, Field(ge=0, le=434)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ExpectedLogicalInput(BaseModel):
    """One logical build-input identity."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )

    namespace: Literal["source_root", "repository"]
    path: str
    kind: str
    size_bytes: NonNegativeInt
    sha256: Sha256


class ExpectedLogicalTable(BaseModel):
    """One logical table identity."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )

    name: str
    grain: str
    schema_hash: Sha256
    row_count: NonNegativeInt
    sort_key: tuple[str, ...]
    unique_key: tuple[str, ...]
    logical_hash: Sha256


class ExpectedSemanticReport(BaseModel):
    """One deterministic semantic-report identity."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )

    report_id: Literal["source_audit", "quality_summary"]
    semantic_hash: Sha256


class ExpectedPhase1ArtifactContract(BaseModel):
    """Expected logical identity of a complete Phase 1 artifact set."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )

    artifact_contract_version: Literal["1.0.0"]
    artifact_set_id: Literal["finproof-data-artifacts/v1"]
    dataset_version: date
    logical_inputs: tuple[ExpectedLogicalInput, ...]
    tables: tuple[ExpectedLogicalTable, ...]
    reports: tuple[ExpectedSemanticReport, ...]
    overall_manifest_logical_hash: Sha256
    exact_link_pair_sha256: Sha256
    exact_link_evidence_count: ExactLinkEvidenceCount

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
        if self.dataset_version != date(2026, 8, 24):
            raise ValueError("dataset_version must be 2026-08-24")
        observed_inputs = tuple(
            (entry.namespace, entry.path, entry.kind) for entry in self.logical_inputs
        )
        if observed_inputs != _EXPECTED_LOGICAL_INPUTS:
            raise ValueError("logical_inputs must use the exact closed order")
        if tuple(table.name for table in self.tables) != _EXPECTED_TABLE_NAMES:
            raise ValueError("tables must use the exact closed order")
        if tuple(table.grain for table in self.tables) != _EXPECTED_TABLE_GRAINS:
            raise ValueError("tables must use the exact closed grains")
        for table, expected_count in zip(
            self.tables,
            _EXPECTED_TABLE_COUNTS,
            strict=True,
        ):
            if expected_count is not None and table.row_count != expected_count:
                raise ValueError("known table count differs from the official baseline")
        if tuple(report.report_id for report in self.reports) != (
            "source_audit",
            "quality_summary",
        ):
            raise ValueError("reports must use the exact closed order")
        return self


class ArtifactLogicalContractPayload(BaseModel):
    """Strict structural twin for actual logical results without baseline values."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )

    artifact_contract_version: Literal["1.0.0"]
    artifact_set_id: Literal["finproof-data-artifacts/v1"]
    dataset_version: date
    logical_inputs: tuple[ExpectedLogicalInput, ...]
    tables: tuple[ExpectedLogicalTable, ...]
    reports: tuple[ExpectedSemanticReport, ...]
    overall_manifest_logical_hash: Sha256
    exact_link_pair_sha256: Sha256
    exact_link_evidence_count: ExactLinkEvidenceCount

    @model_validator(mode="after")
    def require_closed_shape(self) -> Self:
        if self.dataset_version != date(2026, 8, 24):
            raise ValueError("dataset_version must be 2026-08-24")
        observed_inputs = tuple(
            (entry.namespace, entry.path, entry.kind) for entry in self.logical_inputs
        )
        if observed_inputs != _EXPECTED_LOGICAL_INPUTS:
            raise ValueError("logical_inputs must use the exact closed order")
        if tuple(table.name for table in self.tables) != _EXPECTED_TABLE_NAMES:
            raise ValueError("tables must use the exact closed order")
        if tuple(table.grain for table in self.tables) != _EXPECTED_TABLE_GRAINS:
            raise ValueError("tables must use the exact closed grains")
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
        expected = ExpectedPhase1ArtifactContract.model_validate(expected, strict=True)
    except (AttributeError, TypeError, ValueError) as exc:
        raise _reproducibility_error("invalid_expected_contract") from exc
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
        reconstructed = ArtifactLogicalContractPayload.model_validate(
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
    expected_payload = ArtifactLogicalContractPayload.model_validate(
        expected.model_dump(mode="python", warnings="none"),
        strict=True,
    )
    differences = _difference_paths(
        reconstructed.model_dump(mode="python", warnings="none"),
        expected_payload.model_dump(mode="python", warnings="none"),
    )
    if differences:
        raise ArtifactContractError(
            ArtifactErrorCode.REPRODUCIBILITY_MISMATCH,
            operation_id="compare-artifact-contract",
            internal_context={
                "reason": "contract_mismatch",
                "difference_paths": json.dumps(
                    differences,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        )


def _difference_paths(actual: object, expected: object, pointer: str = "") -> tuple[str, ...]:
    differences: set[str] = set()
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key in set(actual) | set(expected):
            child = f"{pointer}/{_escape_pointer_token(key)}"
            if key not in actual or key not in expected:
                differences.add(child)
            else:
                differences.update(_difference_paths(actual[key], expected[key], child))
    elif isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        for index in range(max(len(actual), len(expected))):
            child = f"{pointer}/{index}"
            if index >= len(actual) or index >= len(expected):
                differences.add(child)
            else:
                differences.update(_difference_paths(actual[index], expected[index], child))
    elif actual != expected:
        differences.add(pointer)
    return tuple(sorted(differences))


def _escape_pointer_token(value: object) -> str:
    if type(value) is not str:
        raise TypeError("JSON object keys must be exact strings")
    return value.replace("~", "~0").replace("/", "~1")


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
    "silver_bond_sale_lot",
    "silver_bond_instrument",
    "silver_domestic_listed_product",
    "silver_overseas_listed_product",
    "silver_fund_item",
    "silver_quality_issue",
    "gold_exact_cross_source_link",
    "gold_exact_cross_source_link_evidence",
)

_EXPECTED_TABLE_GRAINS = (
    "source_column",
    "source_row",
    "source_cell",
    "bond_sale_lot",
    "instrument",
    "listed_product",
    "listed_product",
    "fund_item",
    "quality_issue",
    "exact_cross_source_link",
    "exact_cross_source_link_evidence",
)

_EXPECTED_TABLE_COUNTS: tuple[int | None, ...] = (
    251,
    53_375,
    2_828_505,
    21_882,
    20_497,
    1_779,
    6_037,
    23_676,
    None,
    None,
    None,
)
