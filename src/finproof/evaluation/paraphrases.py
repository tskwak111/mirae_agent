"""Deterministic, reviewed rule-based paraphrase generation."""

import re
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from finproof.evaluation.models import GoldenCase


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class ParaphraseRule(_FrozenModel):
    rule_id: str = Field(min_length=1, max_length=100)
    pattern: str = Field(min_length=1, max_length=1_000)
    replacement: str = Field(min_length=1, max_length=1_000)
    preserve_numeric_tokens: bool = True

    @field_validator("pattern")
    @classmethod
    def _validate_pattern(cls, value: str) -> str:
        re.compile(value)
        return value


class ParaphraseRules(_FrozenModel):
    version: str = Field(min_length=1, max_length=100)
    rules: tuple[ParaphraseRule, ...]

    @field_validator("rules", mode="before")
    @classmethod
    def _freeze_rules(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @classmethod
    def load(cls, path: Path) -> Self:
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as error:
            raise ValueError("paraphrase rules could not be loaded") from error
        return cls.model_validate(document, strict=True)


class DerivedCase(GoldenCase):
    base_case_id: str = Field(min_length=1, max_length=200)
    transformation_id: str = Field(min_length=1, max_length=100)


def generate_rule_paraphrases(
    case: GoldenCase,
    rules: ParaphraseRules,
) -> tuple[DerivedCase, ...]:
    variants: list[DerivedCase] = []
    seen = {case.question}
    for rule in rules.rules:
        question, replacements = re.subn(rule.pattern, rule.replacement, case.question, count=1)
        if replacements != 1 or question in seen:
            continue
        if rule.preserve_numeric_tokens and _numeric_tokens(question) != _numeric_tokens(
            case.question
        ):
            raise ValueError(f"paraphrase rule changes semantic values: {rule.rule_id}")
        seen.add(question)
        variants.append(
            DerivedCase.model_validate(
                {
                    **case.model_dump(mode="python"),
                    "case_id": f"{case.case_id}::{rule.rule_id}",
                    "question": question,
                    "base_case_id": case.case_id,
                    "transformation_id": rule.rule_id,
                }
            )
        )
    return tuple(variants)


def _numeric_tokens(value: str) -> tuple[str, ...]:
    return tuple(sorted(re.findall(r"[+-]?\d+(?:[.,]\d+)*(?:%|억|만)?", value)))
