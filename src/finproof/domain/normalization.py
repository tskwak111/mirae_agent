"""Immutable result contract for pure source-row normalization."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from finproof.domain.quality import DataQualityIssue


class NormalizationResult[RecordT](BaseModel):
    """A normalized record or a deterministic quarantine result."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    record: RecordT | None
    issues: tuple[DataQualityIssue, ...]

    @model_validator(mode="after")
    def validate_quarantine_equivalence(self) -> Self:
        """Keep record absence exactly equivalent to at least one quarantine issue."""
        contains_quarantined_issue = any(issue.quarantined for issue in self.issues)
        if self.record is None and not contains_quarantined_issue:
            raise ValueError("record=None requires at least one quarantined issue")
        if self.record is not None and contains_quarantined_issue:
            raise ValueError("record cannot contain quarantined issue")
        return self
