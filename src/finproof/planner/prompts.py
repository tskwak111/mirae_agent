"""Versioned, registry-bounded HCX planner prompt."""

import json
from datetime import date
from hashlib import sha256

from pydantic import BaseModel, ConfigDict

from finproof.domain.query_plan import ProductType
from finproof.planner.provider_schema import build_hcx_query_plan_schema
from finproof.registry.loader import RegistryBundle

PROMPT_VERSION = "phase4-planner-v19"

_FINAL_CONSTRAINTS = (
    "final_constraints=If metric_targets is nonempty, intent must be screen_rank "
    "and top_k_scope must be per_product_type. "
    'For explicit "상품 유형별로 N개씩" or "유형별로 N개씩", '
    "top_k_scope must be per_product_type, never global. "
    "For any heterogeneous query containing "
    "현재 구매 가능한, saleable and mirae_saleable must not appear in filters, metrics, "
    "metric_targets, sort, or aggregation; organizer state policy handles purchaseability. "
    "Every non-aggregate "
    'intent must emit aggregation={"function":"none","field":"","group_by":[]}. '
    'Preserve explicit numeric-zero filters; AUM equal zero requires filters=[{"field":"aum",'
    '"operator":"eq","value":0}]. Treat product_id and product_name as display identity '
    "fields; exclude them from metrics unless the question explicitly asks for a product code, "
    "identifier, or name. For any heterogeneous AUM query, metrics must include aum then "
    "currency exactly once in that order. For intent=screen with a bounded top_k and no "
    'user-specified sort, emit sort=[{"field":"product_name","direction":"asc"}]. '
    "For intent=unsupported, emit product_types=[], "
    "entities=[], result_grain=product, filters=[], metrics=[], metric_targets=[], sort=[], "
    'aggregation={"function":"none","field":"","group_by":[]}, needs_clarification=false, '
    "and a nonempty clarification_reason. For exactly one product_type, use its native "
    "result_grain: domestic_bond=instrument; "
    "domestic_etf|domestic_etn|overseas_etf|overseas_etn=listed_product; "
    "public_fund=fund_item. Use result_grain=product only for heterogeneous native grains."
)

_RULES = """interpret only; never answer the financial question.
Use only canonical names in the supplied compact catalog; never invent identifiers.
Treat snapshot_date={snapshot_date} as current and never claim real-time data.
A plain ETF excludes ETN.
Apply D-027: exactly one aggregation for aggregate intent and none otherwise.
Use result_grain=product only for heterogeneous native grains.
Map native grains exactly: domestic_bond=instrument;
domestic_etf|domestic_etn|overseas_etf|overseas_etn=listed_product;
public_fund=fund_item.
국내채권 means product_types=[domestic_bond], never an entity.
A multi-product filtering or exclusion request uses intent=screen unless the user asks
to produce ranked, compared, or aggregated results; display/warning does not change intent.
Qualitative ranking words such as 낮은/높은 with top-k define sort direction, not a filter.
Without an explicit literal value, set, range, or missing-state condition,
emit filters=[]; never invent a threshold.
Never emit an entity with empty text; product categories and criteria are not entities.
Map 구성종목, 보유종목, 편입종목 at most once to one holding_constituent filter as one scalar eq.
Permit holding_constituent only for domestic_etf, domestic_etn, overseas_etf,
overseas_etn, and public_fund; never emit it as an entity, tuple, fuzzy match, sort,
or aggregation, and never combine it with domestic_bond.
All field-bearing plan members use IDs from the fields catalog;
never emit namespaced metric registry IDs in filters, metrics, sort, or aggregation.
BUYABLE_QUANTITY is invalid and raw-lineage-only; never emit buyable_quantity.
Domestic-bond purchaseability is enforced by organizer state policy, not a plan field.
Use top_k_scope=per_product_type for explicit 각각 N개; use global only for one compatible rank.
Use metric_targets=[] unless the question explicitly assigns different metrics to product types.
For that explicit case only, use intent=screen_rank and top_k_scope=per_product_type;
emit one target per selected product type in product_types order;
each target uses a nonempty ordered subset of metrics and their union equals metrics.
A metric may occur in multiple targets only when the question explicitly shares it.
Emit aggregation={{"function":"none","field":"","group_by":[]}} unless intent=aggregate.
For count use an empty field; min/max/sum/avg require one canonical field.
Ask for clarification only under the registered ambiguity policy.
never emit SQL; never calculate; never advise; never forecast.
output only JSON matching the supplied provider schema."""


class PlannerPrompt(BaseModel):
    """Immutable prompt text with reproducible identity."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    version: str
    checksum: str
    text: str


def build_system_prompt(registries: RegistryBundle, *, snapshot_date: date) -> PlannerPrompt:
    """Build the bounded system prompt from issued registries only."""
    if type(registries) is not RegistryBundle:
        raise TypeError("planner prompt requires the exact registry bundle")
    registries.require_issued()
    catalog = {
        "products": sorted(product.value for product in ProductType),
        "fields": sorted(registries.fields.entries),
        "aliases": {
            "products": _aliases(registries.planner.product_type_aliases),
            "fields": _aliases(registries.planner.field_aliases),
            "periods": _aliases(registries.planner.period_aliases),
            "ranking": _aliases(registries.planner.ranking_aliases),
        },
    }
    text = (
        _RULES.format(snapshot_date=snapshot_date.isoformat())
        + "\ncompact_catalog="
        + json.dumps(catalog, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\nprovider_schema="
        + json.dumps(
            build_hcx_query_plan_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
        + _FINAL_CONSTRAINTS
    )
    return PlannerPrompt(
        version=PROMPT_VERSION,
        checksum=sha256(text.encode("utf-8")).hexdigest(),
        text=text,
    )


def build_user_prompt(question: str) -> str:
    """Keep the question verbatim and place schema-critical invariants last."""
    return f"{question}\n{_FINAL_CONSTRAINTS}"


def _aliases(values: object) -> dict[str, list[str]]:
    if not hasattr(values, "items"):
        raise TypeError("planner aliases must be a mapping")
    return {key: list(aliases) for key, aliases in values.items()}
