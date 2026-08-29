"""Deterministic answer-service composition."""

from datetime import date
from decimal import Decimal
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Any, Literal, cast

from finproof.answer import AnswerRenderer
from finproof.core.settings import ExecutionMode
from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.domain.answers import (
    AnswerClaim,
    AnswerRequest,
    AnswerResult,
    ClaimSignature,
    ComparisonSignature,
    EntitySignature,
    FactPack,
    PreparedAnswer,
    SurfacePart,
    ValueSignature,
    VerifiedAnswer,
)
from finproof.domain.evidence import EvidenceBundle, EvidenceSummaryKind
from finproof.domain.execution import (
    ExecutionBundle,
    ExecutionTrace,
    ExecutionTraceSegment,
    TraceValidation,
)
from finproof.domain.query_plan import Intent, ProductType, QueryPlan
from finproof.entity import EntityIndex, EntityResolver, HoldingResolver
from finproof.evidence import ClaimVerifier, EvidenceBuilder, serialize_evidence_context
from finproof.quality import PolicyEngine, PolicyExecutionResult
from finproof.query import (
    ExecutionBundleBuilder,
    FieldRegistry,
    QueryExecutor,
    ResolutionBundle,
    SemanticValidator,
    ValidationContext,
)
from finproof.query.segmenter import execution_literal_policy_ids
from finproof.registry.loader import RegistryBundle
from finproof.runtime.session import RuntimeArtifactSession
from finproof.service.limits import RequestDeadline
from finproof.storage.repositories.evidence import EvidenceRepository
from finproof.storage.repositories.products import RawExecutionResult, RawFieldValue


class AnswerService:
    def __init__(self, session: RuntimeArtifactSession) -> None:
        if type(session) is not RuntimeArtifactSession:
            raise TypeError("answer service requires exact runtime session")
        session.assert_live()
        self._session = session
        fields = FieldRegistry.from_bundle(session.registries)
        self._resolver: EntityResolver | None = None
        self._holding_resolver: HoldingResolver | None = None
        self._validator = SemanticValidator(fields)
        self._segmenter = ExecutionBundleBuilder(fields)
        self._executor = QueryExecutor(session)
        self._policy = PolicyEngine()
        self._evidence_repository = EvidenceRepository(session)
        self._evidence_builder = EvidenceBuilder()
        self._renderer = AnswerRenderer()
        self._verifier = ClaimVerifier()
        # ponytail: one session lock; use owner-managed per-worker cursors if DB throughput matters.
        self._request_lock = Lock()

    def answer_plan(self, request: AnswerRequest, plan: QueryPlan) -> AnswerResult:
        """Offline/demo deterministic compatibility boundary."""
        if self._session.versions.execution_mode is ExecutionMode.EVALUATION:
            raise RuntimeError("deterministic publication is unavailable in evaluation")
        deadline = RequestDeadline.start()
        prepared = self.prepare_plan(request, plan, deadline)
        return AnswerResult(
            answer=VerifiedAnswer(
                text=prepared.fact_pack.surface_parts[0].text,
                claims=prepared.claims,
            ),
            retrieved_context=prepared.retrieved_context,
            trace=prepared.trace,
        )

    def prepare_plan(
        self,
        request: AnswerRequest,
        plan: QueryPlan,
        deadline: RequestDeadline,
    ) -> PreparedAnswer:
        if type(request) is not AnswerRequest or type(plan) is not QueryPlan:
            raise TypeError("answer service inputs differ")
        if type(deadline) is not RequestDeadline:
            raise TypeError("answer deadline differs")
        with self._request_lock:
            _require_work(deadline)
            return self._answer_plan(request, plan, deadline)

    def _answer_plan(
        self, request: AnswerRequest, plan: QueryPlan, deadline: RequestDeadline
    ) -> PreparedAnswer:
        self._session.assert_live()
        _require_work(deadline)
        if plan.intent in {Intent.CLARIFY, Intent.UNSUPPORTED}:
            evidence = EvidenceBundle(
                direct=(), derived=(), summaries=(), material_policy_limitations=()
            )
            return self._result(
                request=request,
                plan=plan,
                evidence=evidence,
                trace=self._trace(request=request, plan=plan),
                latency_ms={"database": 0, "evidence": 0},
                deadline=deadline,
            )
        if self._resolver is None:
            self._resolver = EntityResolver(EntityIndex.from_session(self._session))
        holding_filters = tuple(
            clause for clause in plan.filters if clause.field == "holding_constituent"
        )
        if holding_filters and self._holding_resolver is None:
            self._holding_resolver = HoldingResolver.from_session(self._session)
        resolutions = ResolutionBundle(
            results=tuple(
                self._resolver.resolve(
                    mention,
                    product_types=plan.product_types,
                )
                for mention in plan.entities
            ),
            holding_constituent=(
                self._holding_resolver.resolve(holding_filters[0].value)
                if len(holding_filters) == 1
                and type(holding_filters[0].value) is str
                and self._holding_resolver is not None
                else None
            ),
        )
        context = ValidationContext(
            as_of_date=plan.as_of_date,
            execution_mode=self._session.versions.execution_mode,
        )
        validated = self._validator.validate(
            plan,
            resolutions=resolutions,
            context=context,
        )
        _require_work(deadline)
        bundle = self._segmenter.build(validated, context=context)
        database_started = monotonic()
        raw = self._executor.execute(bundle)
        _require_work(deadline)
        database_latency = _elapsed_ms(database_started)
        policy_result = self._policy.apply(raw, bundle=bundle)
        evidence_started = monotonic()
        evidence = self._evidence_builder.build(
            plan=validated,
            policy_result=policy_result,
            repository=self._evidence_repository,
        )
        _require_work(deadline)
        return self._result(
            request=request,
            plan=plan,
            evidence=evidence,
            trace=self._trace(
                request=request,
                plan=plan,
                bundle=bundle,
                raw=raw,
                policy_result=policy_result,
                evidence=evidence,
            ),
            latency_ms={
                "database": database_latency,
                "evidence": _elapsed_ms(evidence_started),
            },
            deadline=deadline,
        )

    def _result(
        self,
        *,
        request: AnswerRequest,
        plan: QueryPlan,
        evidence: EvidenceBundle,
        trace: ExecutionTrace,
        latency_ms: dict[str, int],
        deadline: RequestDeadline,
    ) -> PreparedAnswer:
        _require_work(deadline)
        render_started = monotonic()
        draft = self._renderer.render(request=request, plan=plan, evidence=evidence)
        verified = self._verifier.verify(draft, evidence)
        _require_work(deadline)
        evidence_context = serialize_evidence_context(evidence)
        fact_pack = _build_fact_pack(
            claims=verified.claims,
            text=verified.text,
            evidence=evidence,
            evidence_context=evidence_context,
            registries=self._session.registries,
        )
        retrieved_context = canonical_json_bytes(
            fact_pack.model_dump(mode="json"), terminal_newline=False
        ).decode()
        if len(retrieved_context.encode()) > 24_000:
            raise ValueError("fact pack exceeds context bound")
        return PreparedAnswer(
            fact_pack=fact_pack,
            claims=verified.claims,
            retrieved_context=retrieved_context,
            trace=trace.model_copy(
                update={"latency_ms": {**latency_ms, "render": _elapsed_ms(render_started)}}
            ),
        )

    def _trace(
        self,
        *,
        request: AnswerRequest,
        plan: QueryPlan,
        bundle: object = None,
        raw: object = None,
        policy_result: object = None,
        evidence: EvidenceBundle | None = None,
    ) -> ExecutionTrace:
        executable = (
            type(bundle) is ExecutionBundle
            and type(raw) is RawExecutionResult
            and type(policy_result) is PolicyExecutionResult
            and type(evidence) is EvidenceBundle
        )
        tools: tuple[str, ...]
        if executable:
            assert isinstance(bundle, ExecutionBundle)
            assert isinstance(raw, RawExecutionResult)
            assert isinstance(policy_result, PolicyExecutionResult)
            assert evidence is not None
            returned = {
                (item.product_type, item.product_id, item.field_id)
                for item in evidence.direct
                if item.product_id is not None
            } | {
                (item.product_type, item.product_id, item.field_id)
                for item in evidence.derived
                if item.product_id is not None
            }
            returned_products = {
                (product_type, product_id) for product_type, product_id, _ in returned
            }
            segment_by_type = {segment.product_type: segment for segment in bundle.segments}
            raw_by_type = {segment.product_type: segment for segment in raw.segments}
            partition_specs = tuple(
                (
                    product_type,
                    partition.compatibility_key,
                    partition.currency,
                    {
                        value.product_id
                        for value in partition.selected_values
                        if value.product_type is product_type
                    },
                )
                for partition in policy_result.partitions
                for product_type in dict.fromkeys(value.product_type for value in partition.values)
            ) or tuple(
                (product_type, partition_key, None, set())
                for product_type, partition_key, _ in dict.fromkeys(
                    (
                        item.product_type,
                        item.partition_key,
                        item.native_result_grain,
                    )
                    for item in policy_result.aggregates
                )
            )
            partitioned_types = {product_type for product_type, *_ in partition_specs}
            partition_specs = (
                *partition_specs,
                *(
                    (
                        summary.product_types[0],
                        summary.partition_key,
                        None,
                        set(),
                    )
                    for summary in evidence.summaries
                    if summary.kind is EvidenceSummaryKind.PARTITION
                    and len(summary.product_types) == 1
                    and summary.partition_key is not None
                    and summary.product_types[0] not in partitioned_types
                ),
            )
            if not partition_specs:
                partition_specs = tuple(
                    (
                        segment.product_type,
                        segment.product_type.value,
                        None,
                        {
                            product_id
                            for product_type, product_id in returned_products
                            if product_type is segment.product_type
                        },
                    )
                    for segment in bundle.segments
                )
            partition_specs = tuple(
                spec
                for segment in bundle.segments
                for spec in partition_specs
                if spec[0] is segment.product_type
            )
            segments = tuple(
                ExecutionTraceSegment(
                    product_type=product_type,
                    native_result_grain=segment_by_type[product_type].native_result_grain,
                    partition_key=partition_key,
                    candidate_counts={
                        "raw": raw_by_type[product_type].candidate_count,
                        "eligible": sum(
                            row.raw.product_type is product_type
                            and _matches_currency(row.raw.values, currency)
                            for row in policy_result.included_rows
                        ),
                    },
                    returned=sum(
                        (product_type, product_id) in returned_products
                        for product_id in selected_product_ids
                    ),
                )
                for product_type, partition_key, currency, selected_product_ids in partition_specs
            )
            candidate_counts = {
                "raw": raw.candidate_count,
                "eligible": len(policy_result.included_rows),
                "returned": len(returned_products),
            }
            policy_ids: tuple[str, ...] = tuple(
                dict.fromkeys(
                    (
                        f"state:{self._session.versions.state_rule_version}",
                        f"metric:{self._session.versions.metric_registry_version}",
                        *execution_literal_policy_ids(bundle),
                        *(item.policy_id for item in policy_result.ranks),
                        *(item.policy_id for item in policy_result.aggregates),
                    )
                )
            )
            validation = TraceValidation.PASSED
            tools = (
                "entity_resolver",
                "semantic_validator",
                "query_executor",
                "policy_engine",
                "evidence_builder",
                "claim_verifier",
            )
        else:
            segments = ()
            candidate_counts = {"raw": 0, "eligible": 0, "returned": 0}
            policy_ids = (f"answer:{self._session.versions.answer_policy_version}",)
            validation = (
                TraceValidation.CLARIFY
                if plan.intent is Intent.CLARIFY
                else TraceValidation.UNSUPPORTED
                if plan.intent is Intent.UNSUPPORTED
                else TraceValidation.PASSED
            )
            tools = ("claim_verifier",)
        return ExecutionTrace(
            correlation_id=f"trace-{sha256(request.question_id.encode()).hexdigest()[:16]}",
            intent=plan.intent,
            product_types=plan.product_types,
            as_of_date=plan.as_of_date,
            result_grain=plan.result_grain,
            top_k_scope=plan.top_k_scope,
            segments=segments,
            candidate_counts=candidate_counts,
            tools=tools,
            policy_ids=policy_ids,
            validation=validation,
            versions=self._session.versions.runtime_facts(),
            latency_ms={},
        )


def _matches_currency(values: tuple[RawFieldValue, ...], currency: str | None) -> bool:
    return currency is None or any(
        item.field_id == "currency" and item.value == currency for item in values
    )


def _elapsed_ms(started: float) -> int:
    return max(0, int((monotonic() - started) * 1000))


def _require_work(deadline: RequestDeadline) -> None:
    if deadline.remaining_work_seconds() <= 0:
        raise TimeoutError("answer preparation deadline exceeded")


def _build_fact_pack(
    *,
    claims: tuple[AnswerClaim, ...],
    text: str,
    evidence: EvidenceBundle,
    evidence_context: str,
    registries: RegistryBundle,
) -> FactPack:
    claim_ids = tuple(claim.claim_id for claim in claims)
    if len(set(claim_ids)) != len(claim_ids):
        raise ValueError("claim IDs differ")
    limitation_by_claim = tuple(_limitation_codes(claim, evidence) for claim in claims)
    required_codes = tuple(dict.fromkeys(code for codes in limitation_by_claim for code in codes))
    signatures = tuple(
        _claim_signature(claim, codes, evidence, registries)
        for claim, codes in zip(claims, limitation_by_claim, strict=True)
    )
    return FactPack(
        surface_parts=(
            SurfacePart(
                part_id="surface:answer",
                text=text,
                claim_ids=claim_ids,
                limitation_codes=required_codes,
            ),
        ),
        claim_signatures=signatures,
        required_claim_ids=claim_ids,
        required_limitation_codes=required_codes,
        evidence_context_sha256=sha256(evidence_context.encode()).hexdigest(),
    )


def _claim_signature(
    claim: AnswerClaim,
    limitation_codes: tuple[str, ...],
    evidence: EvidenceBundle,
    registries: RegistryBundle,
) -> ClaimSignature:
    summaries = tuple(item for item in evidence.summaries if item.summary_id in claim.evidence_ids)
    ranks = {item.rank for item in summaries if item.rank is not None}
    ties = {item.tie_count for item in summaries if item.tie_count is not None}
    partitions = {item.partition_key for item in summaries if item.partition_key is not None} | (
        {claim.partition_key} if claim.partition_key is not None else set()
    )
    if len(ranks) > 1 or len(ties) > 1 or len(partitions) > 1:
        raise ValueError("claim rank binding is ambiguous")
    entities: tuple[EntitySignature, ...] = ()
    if claim.product_id is not None:
        product_type = claim.product_type or (
            claim.product_types[0] if len(claim.product_types) == 1 else None
        )
        if product_type is None:
            raise ValueError("claim entity product type is missing")
        entities = (
            EntitySignature(
                product_type=product_type,
                product_id=claim.product_id,
                display_name=_display_name(evidence, product_type, claim.product_id),
            ),
        )
    values: tuple[ValueSignature, ...] = ()
    if claim.value is not None and (claim.field_id is not None or claim.kind.value == "numeric"):
        field_id = claim.field_id or "value"
        values = (
            ValueSignature(
                field_id=field_id,
                canonical_normalized_json=canonical_json_bytes(
                    claim.value, terminal_newline=False
                ).decode(),
                display_text=str(claim.value),
                unit=_field_unit(field_id, claim, registries),
            ),
        )
    return ClaimSignature(
        claim_id=claim.claim_id,
        kind=claim.kind,
        surface_text=claim.text,
        entities=entities,
        values=values,
        rank=next(iter(ranks), None),
        tie_count=next(iter(ties), None),
        partition=next(iter(partitions), None),
        comparison=_comparison(claim, evidence),
        evidence_ids=claim.evidence_ids,
        limitation_codes=limitation_codes,
    )


def _display_name(evidence: EvidenceBundle, product_type: ProductType, product_id: str) -> str:
    names = {
        item.value.normalized_value
        for item in evidence.direct
        if item.product_type is product_type
        and item.product_id == product_id
        and item.field_id == "product_name"
        and type(item.value.normalized_value) is str
        and item.value.normalized_value
    }
    if len(names) != 1:
        raise ValueError("applicable entity name is missing or ambiguous")
    return next(iter(names))


def _field_unit(field_id: str, claim: AnswerClaim, registries: RegistryBundle) -> str | None:
    canonical_field = field_id.removesuffix("_difference")
    if canonical_field == "remaining_days":
        canonical_field = "remaining_days_at_as_of"
    field = registries.fields.entries.get(canonical_field)
    if field is None:
        return None
    product_types = (claim.product_type,) if claim.product_type is not None else claim.product_types
    units = {
        metric.unit
        for metric_id in field.metric_ids
        if (metric := registries.metrics.entries.get(metric_id)) is not None
        and (not product_types or any(item in metric.product_types for item in product_types))
    }
    if len(units) > 1:
        raise ValueError("claim unit binding is ambiguous")
    return next(iter(units), None)


def _comparison(claim: AnswerClaim, evidence: EvidenceBundle) -> ComparisonSignature | None:
    if claim.field_id is None or not claim.field_id.endswith("_difference"):
        return None
    metric_id = (
        "remaining_days_at_as_of"
        if claim.field_id == "remaining_days_difference"
        else claim.field_id.removesuffix("_difference")
    )
    operands = tuple(
        (item.product_id, item.value.normalized_value)
        for item in evidence.direct
        if item.product_type is claim.product_type
        and item.product_id is not None
        and item.field_id == metric_id
    ) + tuple(
        (item.product_id, item.value.value)
        for item in evidence.derived
        if item.product_type is claim.product_type
        and item.product_id is not None
        and item.field_id == metric_id
    )
    unique = tuple(dict.fromkeys(operands))
    if len(unique) != 2 or claim.product_id not in {item[0] for item in unique}:
        raise ValueError("comparison operands are missing or ambiguous")
    left = next(item for item in unique if item[0] == claim.product_id)
    right = next(item for item in unique if item[0] != claim.product_id)
    if type(left[1]) is not type(right[1]) or type(left[1]) not in {int, Decimal, date}:
        raise ValueError("comparison operands differ")
    left_value = cast(Any, left[1])
    right_value = cast(Any, right[1])
    relation: Literal["gt", "lt", "eq"] = (
        "eq" if left_value == right_value else "gt" if left_value > right_value else "lt"
    )
    return ComparisonSignature(
        relation=relation,
        left_product_id=left[0],
        right_product_id=right[0],
        left_value_json=canonical_json_bytes(left_value, terminal_newline=False).decode(),
        right_value_json=canonical_json_bytes(right_value, terminal_newline=False).decode(),
    )


def _limitation_codes(claim: AnswerClaim, evidence: EvidenceBundle) -> tuple[str, ...]:
    if claim.claim_id == "claim:snapshot":
        return ("snapshot_assumption",)
    if claim.claim_id == "claim:clarify":
        return ("clarification_required",)
    if claim.claim_id == "claim:unsupported":
        return ("unsupported_request",)
    if claim.kind.value != "limitation":
        return ()
    coverage_codes = tuple(
        item.limitation_code
        for item in evidence.holding_coverage
        if item.evidence_id in claim.evidence_ids
    )
    if coverage_codes:
        return tuple(dict.fromkeys(coverage_codes))
    if any(
        item.partition_key == "limitation:overseas-return-1y"
        and item.summary_id in claim.evidence_ids
        for item in evidence.summaries
    ):
        return ("overseas_return_1y_unavailable",)
    return (
        "policy:"
        + sha256(
            canonical_json_bytes(
                {"text": claim.text, "evidence_ids": claim.evidence_ids},
                terminal_newline=False,
            )
        ).hexdigest(),
    )
