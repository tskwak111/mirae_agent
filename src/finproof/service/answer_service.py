"""Deterministic answer-service composition."""

from hashlib import sha256

from finproof.answer import AnswerRenderer
from finproof.domain.answers import AnswerRequest, AnswerResult
from finproof.domain.evidence import EvidenceBundle
from finproof.domain.execution import (
    ExecutionBundle,
    ExecutionTrace,
    ExecutionTraceSegment,
    TraceValidation,
)
from finproof.domain.query_plan import Intent, QueryPlan
from finproof.entity import EntityIndex, EntityResolver
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
from finproof.runtime.session import RuntimeArtifactSession
from finproof.storage.repositories.evidence import EvidenceRepository
from finproof.storage.repositories.products import RawExecutionResult


class AnswerService:
    def __init__(self, session: RuntimeArtifactSession) -> None:
        if type(session) is not RuntimeArtifactSession:
            raise TypeError("answer service requires exact runtime session")
        session.assert_live()
        self._session = session
        fields = FieldRegistry.from_bundle(session.registries)
        self._resolver: EntityResolver | None = None
        self._validator = SemanticValidator(fields)
        self._segmenter = ExecutionBundleBuilder(fields)
        self._executor = QueryExecutor(session)
        self._policy = PolicyEngine()
        self._evidence_repository = EvidenceRepository(session)
        self._evidence_builder = EvidenceBuilder()
        self._renderer = AnswerRenderer()
        self._verifier = ClaimVerifier()

    def answer_plan(self, request: AnswerRequest, plan: QueryPlan) -> AnswerResult:
        if type(request) is not AnswerRequest or type(plan) is not QueryPlan:
            raise TypeError("answer service inputs differ")
        self._session.assert_live()
        if plan.intent in {Intent.CLARIFY, Intent.UNSUPPORTED}:
            evidence = EvidenceBundle(
                direct=(), derived=(), summaries=(), material_policy_limitations=()
            )
            return self._result(
                request=request,
                plan=plan,
                evidence=evidence,
                trace=self._trace(request=request, plan=plan),
            )
        if self._resolver is None:
            self._resolver = EntityResolver(EntityIndex.from_session(self._session))
        resolutions = ResolutionBundle(
            results=tuple(
                self._resolver.resolve(
                    mention,
                    product_types=plan.product_types,
                )
                for mention in plan.entities
            )
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
        bundle = self._segmenter.build(validated, context=context)
        raw = self._executor.execute(bundle)
        policy_result = self._policy.apply(raw, bundle=bundle)
        evidence = self._evidence_builder.build(
            plan=validated,
            policy_result=policy_result,
            repository=self._evidence_repository,
        )
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
        )

    def _result(
        self,
        *,
        request: AnswerRequest,
        plan: QueryPlan,
        evidence: EvidenceBundle,
        trace: ExecutionTrace,
    ) -> AnswerResult:
        draft = self._renderer.render(request=request, plan=plan, evidence=evidence)
        return AnswerResult(
            answer=self._verifier.verify(draft, evidence),
            retrieved_context=serialize_evidence_context(evidence),
            trace=trace,
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
                (item.product_id, item.field_id)
                for item in evidence.direct
                if item.product_id is not None
            } | {
                (item.product_id, item.field_id)
                for item in evidence.derived
                if item.product_id is not None
            }
            returned_products = {product_id for product_id, _ in returned}
            segments = tuple(
                ExecutionTraceSegment(
                    product_type=segment.product_type,
                    native_result_grain=segment.native_result_grain,
                    partition_key=segment.product_type.value,
                    candidate_counts={
                        "raw": raw_segment.candidate_count,
                        "eligible": sum(
                            row.raw.product_type is segment.product_type
                            for row in policy_result.included_rows
                        ),
                    },
                    returned=sum(
                        product_id in returned_products
                        for product_id in {
                            row.raw.product_id
                            for row in policy_result.included_rows
                            if row.raw.product_type is segment.product_type
                        }
                    ),
                )
                for segment, raw_segment in zip(bundle.segments, raw.segments, strict=True)
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
