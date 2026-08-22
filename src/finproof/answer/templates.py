"""Closed access to versioned Korean answer wording."""

from collections.abc import Mapping


def wording_text(wording: Mapping[str, object], key: str) -> str:
    value = wording.get(key)
    if type(value) is not str:
        raise TypeError("answer wording differs")
    return value
