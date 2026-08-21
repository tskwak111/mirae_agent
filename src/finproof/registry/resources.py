"""Bounded immutable parsing for packaged registry resources."""

from collections.abc import Hashable, Mapping
from types import MappingProxyType

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from finproof.resources import (
    REGISTRY_RESOURCE_NAMES as REGISTRY_RESOURCE_NAMES,
)
from finproof.resources import (
    registry_resource_bytes as registry_resource_bytes,
)

MAX_REGISTRY_BYTES = 1_048_576


class _UniqueKeySafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[object, object]:
        keys: set[Hashable] = set()
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable) or key in keys:
                raise ConstructorError("registry mapping contains a duplicate or invalid key")
            keys.add(key)
        return super().construct_mapping(node, deep=deep)


def load_registry_document(payload: bytes) -> Mapping[str, object]:
    """Parse one closed YAML mapping and freeze its complete object graph."""
    try:
        if type(payload) is not bytes or len(payload) > MAX_REGISTRY_BYTES:
            raise ValueError
        document = yaml.load(payload.decode("utf-8"), Loader=_UniqueKeySafeLoader)  # noqa: S506
        if type(document) is not dict:
            raise ValueError
        frozen = _freeze(document)
        if not isinstance(frozen, Mapping):
            raise ValueError
        return frozen
    except (UnicodeError, yaml.YAMLError, TypeError, ValueError) as exc:
        raise ValueError("invalid registry resource") from exc


def _freeze(value: object) -> object:
    if type(value) is dict:
        mapping = value
        if any(type(key) is not str for key in mapping):
            raise ValueError
        return MappingProxyType({key: _freeze(child) for key, child in mapping.items()})
    if type(value) is list:
        return tuple(_freeze(child) for child in value)
    if value is None or type(value) in {str, int, bool}:
        return value
    raise ValueError
