"""Product-state eligibility policy."""

from datetime import date

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
            issue_date = values.get("issue_date")
            maturity = values.get("maturity_date")
            not_yet_issued = type(issue_date) is date and issue_date > as_of
            ended = type(maturity) is date and maturity < as_of
            unknown_maturity = type(maturity) is not date
            purchasable = not not_yet_issued and not ended
            states = tuple(
                state
                for state, active in (
                    ("not_yet_issued", not_yet_issued),
                    ("ended", ended),
                    ("unknown_maturity", unknown_maturity),
                    ("purchasable_assumed", purchasable),
                )
                if active
            )
            return StateEvaluation(
                product_id=product.product_id,
                eligible=purchasable,
                state_ids=states,
                warnings=("bond end state is not source-verifiable",) if unknown_maturity else (),
            )
        raise ValueError("state policy is not implemented for product type")
