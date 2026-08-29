"""Request service composition with cycle-free public imports."""

from typing import Any

__all__ = [
    "AnswerService",
    "EvaluationOrchestrator",
    "EvaluationPublication",
    "RequestDeadline",
    "RequestLimiter",
    "build_safe_publication",
    "publish_result",
]


def __getattr__(name: str) -> Any:
    if name == "AnswerService":
        from finproof.service.answer_service import AnswerService

        return AnswerService
    if name == "EvaluationOrchestrator":
        from finproof.service.orchestrator import EvaluationOrchestrator

        return EvaluationOrchestrator
    if name in {"RequestDeadline", "RequestLimiter"}:
        from finproof.service.limits import RequestDeadline, RequestLimiter

        return {"RequestDeadline": RequestDeadline, "RequestLimiter": RequestLimiter}[name]
    if name in {"EvaluationPublication", "build_safe_publication", "publish_result"}:
        from finproof.service.publication import (
            EvaluationPublication,
            build_safe_publication,
            publish_result,
        )

        return {
            "EvaluationPublication": EvaluationPublication,
            "build_safe_publication": build_safe_publication,
            "publish_result": publish_result,
        }[name]
    raise AttributeError(name)
