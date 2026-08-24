"""Deterministic golden-case evaluation contracts."""

from finproof.evaluation.loader import load_golden_cases, suite_checksum
from finproof.evaluation.models import (
    AggregateGroupValue,
    ExpectedAggregate,
    ExpectedAnswerSemantics,
    ExpectedPlan,
    ExpectedResult,
    ExpectedValue,
    GoldenCase,
    ObservedAggregate,
    ObservedCase,
    ObservedValue,
    ProductIdentity,
)
from finproof.evaluation.runner import EvaluationMode, EvaluationReport, EvaluationRunner
from finproof.evaluation.scoring import CaseScore, score_aggregates, score_case

__all__ = [
    "AggregateGroupValue",
    "CaseScore",
    "EvaluationMode",
    "EvaluationReport",
    "EvaluationRunner",
    "ExpectedAggregate",
    "ExpectedAnswerSemantics",
    "ExpectedPlan",
    "ExpectedResult",
    "ExpectedValue",
    "GoldenCase",
    "ObservedAggregate",
    "ObservedCase",
    "ObservedValue",
    "ProductIdentity",
    "load_golden_cases",
    "score_aggregates",
    "score_case",
    "suite_checksum",
]
