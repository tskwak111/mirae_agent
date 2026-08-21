"""Product-state eligibility policy."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from finproof.domain.query_plan import ProductType
from finproof.storage import RawFieldValue


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class PolicyProduct(_FrozenModel):
    product_type: ProductType
    product_id: str
    values: tuple[RawFieldValue, ...]


class StateEvaluation(_FrozenModel):
    product_id: str
    eligible: bool
    state_ids: tuple[str, ...]
    warnings: tuple[str, ...]


class StatePolicy:
    def evaluate(self, product: PolicyProduct, *, as_of: date) -> StateEvaluation:
        if type(product) is not PolicyProduct or type(as_of) is not date:
            raise TypeError("state policy inputs differ")
        fields = {item.field_id: item for item in product.values}
        values = {field_id: item.value for field_id, item in fields.items()}
        if product.product_type in {
            ProductType.DOMESTIC_ETF,
            ProductType.DOMESTIC_ETN,
        }:
            suspended = values.get("suspension_flag") is True
            saleable = values.get("saleable") is True
            listing_date = values.get("listing_date")
            listing_end_date = values.get("listing_end_date")
            starts_on_time = type(listing_date) is date and listing_date <= as_of
            open_ended = (
                listing_end_date is None
                and fields.get("listing_end_date") is not None
                and fields["listing_end_date"].quality_status
                in {"missing_blank", "sentinel_max_date"}
            )
            ends_on_time = open_ended or (
                type(listing_end_date) is date and listing_end_date >= as_of
            )
            states = tuple(
                state
                for state, active in (
                    ("saleable", saleable),
                    ("suspended", suspended),
                    ("not_yet_listed", not starts_on_time),
                    ("listing_ended", not ends_on_time),
                )
                if active
            )
            return StateEvaluation(
                product_id=product.product_id,
                eligible=saleable and not suspended and starts_on_time and ends_on_time,
                state_ids=states,
                warnings=(),
            )
        if product.product_type is ProductType.DOMESTIC_BOND:
            quantity = values.get("buyable_quantity")
            maturity = values.get("maturity_date")
            source_buyable = type(quantity) is Decimal and quantity > 0
            if type(maturity) is not date:
                return StateEvaluation(
                    product_id=product.product_id,
                    eligible=False,
                    state_ids=tuple(
                        state
                        for state, active in (
                            ("source_buyable", source_buyable),
                            ("unknown_maturity", True),
                        )
                        if active
                    ),
                    warnings=("validated buyability requires a valid maturity date",),
                )
            matured = maturity < as_of
            validated_buyable = source_buyable and not matured
            states = tuple(
                state
                for state, active in (
                    ("source_buyable", source_buyable),
                    ("matured", matured),
                    ("validated_buyable", validated_buyable),
                )
                if active
            )
            return StateEvaluation(
                product_id=product.product_id,
                eligible=validated_buyable,
                state_ids=states,
                warnings=("source quantity remains positive after maturity",)
                if source_buyable and matured
                else (),
            )
        raise ValueError("state policy is not implemented for product type")
