"""Bounded final-result and sealed-holding evidence access."""

from hashlib import sha256
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.data.artifacts.serialization import canonical_record_json
from finproof.data.holdings import HoldingCoverageRecord, HoldingCoverageState, HoldingRecord
from finproof.domain.bonds import BondInstrument
from finproof.domain.domestic_listed import ListedProduct
from finproof.domain.evidence import (
    DerivedEvidence,
    DirectEvidence,
    HoldingCoverageEvidenceRef,
    HoldingRecordEvidenceRef,
)
from finproof.domain.overseas_listed import OverseasListedProduct
from finproof.domain.public_funds import FundItem, FundItemValue
from finproof.domain.query_plan import ProductType
from finproof.domain.values import DerivedValue, NormalizedValue
from finproof.query.fields import FieldRegistry
from finproof.runtime.session import RuntimeArtifactSession


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class EvidenceLookup(_FrozenModel):
    product_type: ProductType
    product_ids: tuple[str, ...] = Field(min_length=1, max_length=50)
    field_ids: tuple[str, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _unique_values(self) -> "EvidenceLookup":
        if len(set(self.product_ids)) != len(self.product_ids) or len(set(self.field_ids)) != len(
            self.field_ids
        ):
            raise ValueError("evidence lookup values must be unique")
        return self


class RecordEvidence(_FrozenModel):
    product_type: ProductType
    product_id: str
    direct: tuple[DirectEvidence[object], ...]
    derived: tuple[DerivedEvidence[object], ...]


class HoldingEvidenceLookup(_FrozenModel):
    product_type: ProductType
    product_ids: tuple[str, ...] = Field(min_length=1, max_length=50)
    constituent_identifier: str = Field(min_length=1, max_length=300)
    constituent_identifier_type: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _validate_holding_lookup(self) -> "HoldingEvidenceLookup":
        if self.product_type is ProductType.DOMESTIC_BOND or len(set(self.product_ids)) != len(
            self.product_ids
        ):
            raise ValueError("holding evidence lookup differs")
        return self


class HoldingEvidenceResult(_FrozenModel):
    holding_records: tuple[HoldingRecordEvidenceRef, ...] = Field(max_length=50)
    holding_coverage: tuple[HoldingCoverageEvidenceRef, ...] = Field(max_length=50)


class HoldingCoverageStateCount(_FrozenModel):
    product_type: ProductType
    coverage_state: HoldingCoverageState
    owner_count: int = Field(gt=0)


class EvidenceRepository:
    __slots__ = ("_fields", "_session")

    def __init__(self, session: RuntimeArtifactSession) -> None:
        if type(session) is not RuntimeArtifactSession:
            raise TypeError("evidence repository requires exact runtime session")
        session.assert_live()
        self._session = session
        self._fields = FieldRegistry.from_bundle(session.registries)

    def fetch_final_record_evidence(
        self,
        requests: tuple[EvidenceLookup, ...],
    ) -> tuple[RecordEvidence, ...]:
        if type(requests) is not tuple or any(
            type(request) is not EvidenceLookup for request in requests
        ):
            raise TypeError("evidence requests differ")
        if sum(len(request.product_ids) for request in requests) > 50:
            raise ValueError("evidence request bound exceeded")
        self._session.assert_live()
        connection = cast(_Connection | None, self._session._connection)
        if connection is None:
            raise RuntimeError("runtime artifact session is closed")
        records: list[RecordEvidence] = []
        for request in requests:
            product = self._fields.projection("product_id", request.product_type)
            placeholders = ", ".join("?" for _ in request.product_ids)
            predicates = [f'"{product.column_name}" IN ({placeholders})']
            parameters: tuple[str, ...] = request.product_ids
            discriminator = _DISCRIMINATORS.get(request.product_type)
            if discriminator is not None:
                predicates.append('"product_type" = ?')
                parameters = (*parameters, discriminator)
            sql = (
                f'SELECT "{product.column_name}", "record_json" '  # noqa: S608 -- closed identifiers
                f'FROM "{product.table_name}" WHERE '
                + " AND ".join(predicates)
                + f' ORDER BY "{product.column_name}"'
            )
            rows = connection.execute(sql, parameters).fetchall()
            if len(rows) != len(request.product_ids):
                raise ValueError("final evidence record count differs")
            by_id: dict[str, str] = {_text(row[0]): _text(row[1]) for row in rows if len(row) == 2}
            if set(by_id) != set(request.product_ids):
                raise ValueError("final evidence identity differs")
            for product_id in request.product_ids:
                payload = by_id[product_id]
                if type(payload) is not str:
                    raise ValueError("record evidence JSON differs")
                model = _MODELS[request.product_type].model_validate_json(payload)
                if canonical_record_json(model) != payload:
                    raise ValueError("record evidence JSON is not canonical")
                direct: list[DirectEvidence[object]] = []
                derived: list[DerivedEvidence[object]] = []
                for field_id in request.field_ids:
                    projection = self._fields.projection(field_id, request.product_type)
                    wrapped = getattr(model, projection.column_name)
                    if isinstance(wrapped, FundItemValue):
                        wrapped = wrapped.representative
                    evidence_id = f"{request.product_type.value}:{product_id}:{field_id}"
                    if isinstance(wrapped, NormalizedValue):
                        direct.append(
                            DirectEvidence[object](
                                evidence_id=evidence_id,
                                product_type=request.product_type,
                                product_id=product_id,
                                field_id=field_id,
                                value=wrapped,
                            )
                        )
                    elif isinstance(wrapped, DerivedValue):
                        derived.append(
                            DerivedEvidence[object](
                                evidence_id=evidence_id,
                                product_type=request.product_type,
                                product_id=product_id,
                                field_id=field_id,
                                value=wrapped,
                            )
                        )
                    else:
                        raise ValueError("record evidence field differs")
                if (
                    request.product_type is ProductType.DOMESTIC_BOND
                    and "buy_yield" in request.field_ids
                ):
                    if not isinstance(model, BondInstrument):
                        raise ValueError("bond range evidence model differs")
                    bounds = model.buy_yield_range.value
                    if bounds is not None and bounds[0] != bounds[1]:
                        derived.append(
                            DerivedEvidence[object](
                                evidence_id=(
                                    f"{request.product_type.value}:{product_id}:buy_yield_range"
                                ),
                                product_type=request.product_type,
                                product_id=product_id,
                                field_id="buy_yield_range",
                                value=cast(DerivedValue[object], model.buy_yield_range),
                            )
                        )
                records.append(
                    RecordEvidence(
                        product_type=request.product_type,
                        product_id=product_id,
                        direct=tuple(direct),
                        derived=tuple(derived),
                    )
                )
        return tuple(records)

    def fetch_holding_evidence(
        self,
        requests: tuple[HoldingEvidenceLookup, ...],
    ) -> HoldingEvidenceResult:
        if type(requests) is not tuple or any(
            type(request) is not HoldingEvidenceLookup for request in requests
        ):
            raise TypeError("holding evidence requests differ")
        if sum(len(request.product_ids) for request in requests) > 50:
            raise ValueError("holding evidence request bound exceeded")
        self._session.assert_live()
        connection = cast(_Connection | None, self._session._connection)
        if connection is None:
            raise RuntimeError("runtime artifact session is closed")
        holding_refs: list[HoldingRecordEvidenceRef] = []
        coverage_refs: list[HoldingCoverageEvidenceRef] = []
        for request in requests:
            placeholders = ", ".join("?" for _ in request.product_ids)
            owner_parameters = (request.product_type.value, *request.product_ids)
            count_rows = connection.execute(
                "SELECT owner_product_type, owner_product_id, generation_id, COUNT(*) "  # noqa: S608 -- bounded placeholders
                "FROM silver_product_holding WHERE owner_product_type = ? "
                f"AND owner_product_id IN ({placeholders}) "
                "GROUP BY owner_product_type, owner_product_id, generation_id",
                owner_parameters,
            ).fetchall()
            counts = {
                (_text(row[0]), _text(row[1]), _text(row[2])): _integer(row[3])
                for row in count_rows
            }
            holding_rows = connection.execute(
                "SELECT generation_id, owner_product_type, owner_product_id, "  # noqa: S608 -- bounded placeholders
                "owner_source_identifier, owner_identifier_type, owner_link_method, "
                "constituent_identifier, constituent_identifier_type, display_name, "
                "source_owner, source_kind, source_as_of_date, source_row_ordinal, record_json "
                "FROM silver_product_holding WHERE owner_product_type = ? "
                f"AND owner_product_id IN ({placeholders}) "
                "AND constituent_identifier = ? AND constituent_identifier_type = ? "
                "ORDER BY owner_product_id, generation_id, source_row_ordinal",
                (
                    *owner_parameters,
                    request.constituent_identifier,
                    request.constituent_identifier_type,
                ),
            ).fetchall()
            for row in holding_rows:
                payload = _text(row[13])
                record = HoldingRecord.model_validate_json(payload, strict=True)
                if (
                    canonical_record_json(record) != payload
                    or (
                        record.generation_id,
                        record.owner_product_type.value,
                        record.owner_product_id,
                        record.owner_source_identifier,
                        record.owner_identifier_type,
                        record.owner_link_method,
                        record.constituent_identifier,
                        record.constituent_identifier_type,
                        record.display_name,
                        record.source_owner,
                        record.source_kind,
                        record.source_as_of_date,
                        record.source_row_ordinal,
                    )
                    != row[:13]
                ):
                    raise ValueError("canonical holding evidence row differs")
                holding_refs.append(
                    HoldingRecordEvidenceRef(
                        evidence_id=_evidence_id(
                            "holding",
                            record.owner_product_type.value,
                            record.owner_product_id,
                            record.generation_id,
                            str(record.source_row_ordinal),
                        ),
                        owner_product_type=record.owner_product_type,
                        owner_product_id=record.owner_product_id,
                        generation_id=record.generation_id,
                        constituent_identifier=record.constituent_identifier,
                        constituent_identifier_type=record.constituent_identifier_type,
                        display_name=record.display_name,
                        source_kind=record.source_kind,
                        source_as_of_date=record.source_as_of_date,
                        source_row_ordinal=record.source_row_ordinal,
                    )
                )
            coverage_rows = connection.execute(
                "SELECT owner_product_type, owner_product_id, coverage_state, "  # noqa: S608 -- bounded placeholders
                "source_generation_id, owner_source_identifier, owner_identifier_type, "
                "owner_link_method, source_owner, source_kind, source_as_of_date, "
                "observed_holding_count, limitation_code, record_json "
                "FROM silver_product_holding_coverage WHERE owner_product_type = ? "
                f"AND owner_product_id IN ({placeholders}) ORDER BY owner_product_id",
                owner_parameters,
            ).fetchall()
            if len(coverage_rows) != len(request.product_ids):
                raise ValueError("holding coverage evidence count differs")
            observed_owners: set[str] = set()
            for row in coverage_rows:
                payload = _text(row[12])
                coverage = HoldingCoverageRecord.model_validate_json(payload, strict=True)
                if (
                    canonical_record_json(coverage) != payload
                    or (
                        coverage.owner_product_type.value,
                        coverage.owner_product_id,
                        coverage.coverage_state.value,
                        coverage.source_generation_id,
                        coverage.owner_source_identifier,
                        coverage.owner_identifier_type,
                        coverage.owner_link_method,
                        coverage.source_owner,
                        coverage.source_kind,
                        coverage.source_as_of_date,
                        coverage.observed_holding_count,
                        coverage.limitation_code,
                    )
                    != row[:12]
                ):
                    raise ValueError("canonical holding coverage evidence row differs")
                observed_owners.add(coverage.owner_product_id)
                full_count = (
                    0
                    if coverage.coverage_state is HoldingCoverageState.UNAVAILABLE
                    else counts.get(
                        (
                            coverage.owner_product_type.value,
                            coverage.owner_product_id,
                            cast(str, coverage.source_generation_id),
                        ),
                        0,
                    )
                )
                if coverage.observed_holding_count != full_count:
                    raise ValueError("holding coverage observed count differs")
                coverage_refs.append(
                    HoldingCoverageEvidenceRef(
                        evidence_id=_evidence_id(
                            "coverage",
                            coverage.owner_product_type.value,
                            coverage.owner_product_id,
                        ),
                        owner_product_type=coverage.owner_product_type,
                        owner_product_id=coverage.owner_product_id,
                        coverage_state=coverage.coverage_state,
                        source_generation_id=coverage.source_generation_id,
                        observed_holding_count=coverage.observed_holding_count,
                        limitation_code=coverage.limitation_code,
                        source_kind=coverage.source_kind,
                        source_as_of_date=coverage.source_as_of_date,
                    )
                )
            if observed_owners != set(request.product_ids):
                raise ValueError("holding coverage evidence identity differs")
            coverage_generation = {
                (item.owner_product_type, item.owner_product_id): item.source_generation_id
                for item in coverage_refs
                if item.owner_product_type is request.product_type
                and item.owner_product_id in request.product_ids
            }
            if any(
                item.generation_id
                != coverage_generation.get((item.owner_product_type, item.owner_product_id))
                for item in holding_refs
                if item.owner_product_type is request.product_type
                and item.owner_product_id in request.product_ids
            ):
                raise ValueError("holding evidence generation differs from coverage")
            matched_owners = {
                item.owner_product_id
                for item in holding_refs
                if item.owner_product_type is request.product_type
                and item.constituent_identifier == request.constituent_identifier
                and item.constituent_identifier_type == request.constituent_identifier_type
            }
            if matched_owners != set(request.product_ids):
                raise ValueError("positive holding evidence identity differs")
        return HoldingEvidenceResult(
            holding_records=tuple(holding_refs),
            holding_coverage=tuple(coverage_refs),
        )

    def fetch_holding_coverage_state_counts(
        self,
        product_types: tuple[ProductType, ...],
    ) -> tuple[HoldingCoverageStateCount, ...]:
        if (
            type(product_types) is not tuple
            or not product_types
            or len(set(product_types)) != len(product_types)
            or any(product_type is ProductType.DOMESTIC_BOND for product_type in product_types)
        ):
            raise ValueError("holding coverage state-count request differs")
        self._session.assert_live()
        connection = cast(_Connection | None, self._session._connection)
        if connection is None:
            raise RuntimeError("runtime artifact session is closed")
        placeholders = ", ".join("?" for _ in product_types)
        rows = connection.execute(
            "SELECT owner_product_type, coverage_state, COUNT(*) "  # noqa: S608 -- bounded placeholders
            "FROM silver_product_holding_coverage "
            f"WHERE owner_product_type IN ({placeholders}) "
            "GROUP BY owner_product_type, coverage_state "
            "ORDER BY owner_product_type, coverage_state",
            tuple(product_type.value for product_type in product_types),
        ).fetchall()
        result = tuple(
            HoldingCoverageStateCount(
                product_type=ProductType(_text(row[0])),
                coverage_state=HoldingCoverageState(_text(row[1])),
                owner_count=_integer(row[2]),
            )
            for row in rows
        )
        if {item.product_type for item in result} != set(product_types):
            raise ValueError("holding coverage state-count identity differs")
        return result


class _Cursor(Protocol):
    def fetchall(self) -> list[tuple[object, ...]]: ...


class _Connection(Protocol):
    def execute(self, sql: str, parameters: tuple[str, ...]) -> _Cursor: ...


def _text(value: object) -> str:
    if type(value) is not str:
        raise ValueError("holding evidence text differs")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ValueError("holding evidence count differs")
    return value


def _evidence_id(prefix: str, *parts: str) -> str:
    return f"{prefix}:{sha256(chr(31).join(parts).encode()).hexdigest()}"


_MODELS: dict[ProductType, type[BaseModel]] = {
    ProductType.DOMESTIC_BOND: BondInstrument,
    ProductType.DOMESTIC_ETF: ListedProduct,
    ProductType.DOMESTIC_ETN: ListedProduct,
    ProductType.OVERSEAS_ETF: OverseasListedProduct,
    ProductType.OVERSEAS_ETN: OverseasListedProduct,
    ProductType.PUBLIC_FUND: FundItem,
}

_DISCRIMINATORS = {
    ProductType.DOMESTIC_ETF: "ETF",
    ProductType.DOMESTIC_ETN: "ETN",
    ProductType.OVERSEAS_ETF: "ETF",
    ProductType.OVERSEAS_ETN: "ETN",
}
