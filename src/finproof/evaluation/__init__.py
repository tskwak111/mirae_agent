"""Deterministic golden-case evaluation contracts."""

from finproof.evaluation.loader import load_golden_cases, suite_checksum
from finproof.evaluation.models import (
    ExpectedAnswerSemantics,
    ExpectedPlan,
    ExpectedResult,
    ExpectedValue,
    GoldenCase,
    ObservedCase,
    ObservedValue,
)
from finproof.evaluation.runner import EvaluationMode, EvaluationReport, EvaluationRunner
from finproof.evaluation.scoring import CaseScore, score_case

__all__ = [
    "CaseScore",
    "EvaluationMode",
    "EvaluationReport",
    "EvaluationRunner",
    "ExpectedAnswerSemantics",
    "ExpectedPlan",
    "ExpectedResult",
    "ExpectedValue",
    "GoldenCase",
    "ObservedCase",
    "ObservedValue",
    "load_golden_cases",
    "score_case",
    "suite_checksum",
]
