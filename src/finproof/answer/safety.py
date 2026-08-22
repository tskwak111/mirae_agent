"""Fail-closed deterministic answer safety checks."""

from finproof.domain.answers import AnswerClaim, ClaimKind
from finproof.registry.loader import RegistryBundle


def require_safe_claim(claim: AnswerClaim) -> None:
    if claim.kind is ClaimKind.RECOMMENDATION:
        raise ValueError("recommendation claim is unsupported")
    patterns = RegistryBundle.from_package().answers.document["forbidden_claim_patterns"]
    if not isinstance(patterns, tuple) or any(type(item) is not str for item in patterns):
        raise TypeError("answer safety registry differs")
    if any(pattern in claim.text for pattern in patterns):
        raise ValueError("recommendation claim is unsupported")
