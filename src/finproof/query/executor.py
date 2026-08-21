"""Ordered native query execution."""

from finproof.domain.execution import ExecutionBundle
from finproof.query.ast import QueryAst
from finproof.query.compiler import SqlCompiler
from finproof.query.fields import FieldRegistry
from finproof.runtime.session import RuntimeArtifactSession
from finproof.storage.repositories.products import (
    ProductRepository,
    RawExecutionResult,
)


class QueryExecutor:
    __slots__ = ("_compiler", "_fields", "_repository", "_session")

    def __init__(self, session: RuntimeArtifactSession) -> None:
        if type(session) is not RuntimeArtifactSession:
            raise TypeError("query executor requires exact runtime session")
        session.assert_live()
        self._session = session
        self._fields = FieldRegistry.from_bundle(session.registries)
        self._compiler = SqlCompiler()
        self._repository = ProductRepository(session)

    def execute(self, bundle: ExecutionBundle) -> RawExecutionResult:
        if type(bundle) is not ExecutionBundle:
            raise TypeError("query executor requires exact execution bundle")
        self._session.assert_live()
        segments = tuple(
            self._repository.execute(
                self._compiler.compile(QueryAst.from_segment(segment, fields=self._fields))
            )
            for segment in bundle.segments
        )
        return RawExecutionResult(
            segments=segments,
            candidate_count=sum(segment.candidate_count for segment in segments),
        )
