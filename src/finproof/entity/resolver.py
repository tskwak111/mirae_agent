"""Deterministic product entity resolution."""

from difflib import SequenceMatcher

from finproof.domain.query_plan import EntityIdentifierType, EntityMention, ProductType
from finproof.entity.index import EntityIndex, _IndexedProduct
from finproof.entity.models import ResolutionCandidate, ResolutionMatchKind, ResolutionResult
from finproof.entity.normalization import normalize_product_text


class EntityResolver:
    def __init__(self, index: EntityIndex) -> None:
        if type(index) is not EntityIndex:
            raise TypeError("resolver requires the exact entity index")
        self._index = index

    def resolve(
        self,
        mention: EntityMention,
        *,
        product_types: tuple[ProductType, ...],
    ) -> ResolutionResult:
        if type(mention) is not EntityMention or type(product_types) is not tuple:
            raise TypeError("resolution inputs differ")
        if not product_types or len(set(product_types)) != len(product_types):
            raise ValueError("resolution product types differ")
        if any(type(product_type) is not ProductType for product_type in product_types):
            raise TypeError("resolution product type differs")
        query = normalize_product_text(mention.text)
        product_order = {product_type: index for index, product_type in enumerate(product_types)}
        eligible = tuple(
            sorted(
                (entry for entry in self._index._entries if entry.product_type in product_types),
                key=lambda entry: (product_order[entry.product_type], entry.product_id),
            )
        )
        primary = next(
            (
                entry
                for entry in eligible
                if mention.identifier_type
                in {EntityIdentifierType.UNKNOWN, EntityIdentifierType.PRODUCT_ID}
                and (EntityIdentifierType.PRODUCT_ID, query) in entry.identifiers
            ),
            None,
        )
        if primary is not None:
            candidate = _candidate(primary, ResolutionMatchKind.EXACT_PRODUCT_ID, 10_000)
            return ResolutionResult(selected=candidate, candidates=(candidate,))

        secondary = next(
            (
                entry
                for entry in eligible
                if any(
                    value == query
                    and kind is not EntityIdentifierType.PRODUCT_ID
                    and mention.identifier_type in {EntityIdentifierType.UNKNOWN, kind}
                    for kind, value in entry.identifiers
                )
            ),
            None,
        )
        if secondary is not None:
            candidate = _candidate(secondary, ResolutionMatchKind.EXACT_IDENTIFIER, 9_900)
            return ResolutionResult(selected=candidate, candidates=(candidate,))

        names = (
            tuple(entry for entry in eligible if query in entry.names)
            if mention.identifier_type
            in {
                EntityIdentifierType.UNKNOWN,
                EntityIdentifierType.NAME,
            }
            else ()
        )
        if len(names) == 1:
            candidate = _candidate(names[0], ResolutionMatchKind.EXACT_NAME, 9_800)
            return ResolutionResult(selected=candidate, candidates=(candidate,))
        if len(names) > 1:
            candidates = tuple(
                sorted(
                    (_candidate(entry, ResolutionMatchKind.EXACT_NAME, 9_800) for entry in names),
                    key=lambda candidate: (
                        tuple(ProductType).index(candidate.product_type),
                        candidate.product_id,
                    ),
                )
            )[:5]
            return ResolutionResult(selected=None, candidates=candidates)
        if mention.identifier_type not in {
            EntityIdentifierType.UNKNOWN,
            EntityIdentifierType.NAME,
        }:
            return ResolutionResult(selected=None, candidates=())
        fuzzy = tuple(
            sorted(
                (
                    _candidate(
                        entry,
                        ResolutionMatchKind.FUZZY_CANDIDATE,
                        max(
                            int(SequenceMatcher(None, query, name).ratio() * 10_000)
                            for name in entry.names
                        ),
                    )
                    for entry in eligible
                    if entry.names
                ),
                key=lambda candidate: (
                    -candidate.score,
                    tuple(ProductType).index(candidate.product_type),
                    candidate.product_id,
                ),
            )
        )
        return ResolutionResult(
            selected=None,
            candidates=tuple(candidate for candidate in fuzzy if candidate.score >= 4_000)[:5],
        )


def _candidate(
    entry: _IndexedProduct,
    kind: ResolutionMatchKind,
    score: int,
) -> ResolutionCandidate:
    return ResolutionCandidate(
        product_id=entry.product_id,
        product_type=entry.product_type,
        name=entry.name,
        match_kind=kind,
        score=score,
    )
