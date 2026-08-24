"""Bounded final-result evidence access."""

from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finproof.data.artifacts.serialization import canonical_record_json
from finproof.domain.bonds import BondInstrument
from finproof.domain.domestic_listed import ListedProduct
from finproof.domain.evidence import DerivedEvidence, DirectEvidence
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
            by_id = dict(rows)
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
                records.append(
                    RecordEvidence(
                        product_type=request.product_type,
                        product_id=product_id,
                        direct=tuple(direct),
                        derived=tuple(derived),
                    )
                )
        return tuple(records)


class _Cursor(Protocol):
    def fetchall(self) -> tuple[tuple[object, object], ...]: ...


class _Connection(Protocol):
    def execute(self, sql: str, parameters: tuple[str, ...]) -> _Cursor: ...


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
