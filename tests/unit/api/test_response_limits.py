"""Evidence context must use the checked-in answer-policy bound."""

from collections.abc import Mapping

from finproof.evidence.serializer import context_limit_bytes
from finproof.registry.loader import RegistryBundle


def test_evidence_serializer_reads_answer_policy_context_limit() -> None:
    limits = RegistryBundle.from_package().answers.document["limits"]
    assert isinstance(limits, Mapping)

    assert context_limit_bytes() == limits["max_context_bytes"]
