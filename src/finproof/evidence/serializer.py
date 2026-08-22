"""Stable bounded serialization for optional answer wording context."""

from pathlib import PurePosixPath, PureWindowsPath

from finproof.data.artifacts.hashing import canonical_json_bytes
from finproof.domain.evidence import EvidenceBundle

_MAX_CONTEXT_BYTES = 24_000


def serialize_evidence_context(evidence: EvidenceBundle) -> str:
    if type(evidence) is not EvidenceBundle:
        raise TypeError("evidence context differs")
    payload = evidence.model_dump(mode="json")
    if _contains_local_path(payload):
        raise ValueError("evidence context contains a local path")
    encoded = canonical_json_bytes(payload, terminal_newline=False)
    if len(encoded) > _MAX_CONTEXT_BYTES:
        raise ValueError("evidence context exceeds configured bound")
    return encoded.decode()


def _contains_local_path(value: object) -> bool:
    if type(value) is str:
        return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()
    if type(value) is list:
        return any(_contains_local_path(item) for item in value)
    if type(value) is dict:
        return any(_contains_local_path(item) for item in value.values())
    return False
