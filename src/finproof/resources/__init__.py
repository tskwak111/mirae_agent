"""Stable package anchor for closed FinProof runtime resources."""

from importlib import metadata as importlib_metadata
from importlib.resources import files
from pathlib import Path

from finproof.data.artifacts.safe_files import read_held_regular_file

REGISTRY_RESOURCE_NAMES = (
    "datasets.yaml",
    "metric_registry.yaml",
    "field_registry.yaml",
    "state_rules.yaml",
    "quality_rules.yaml",
    "rating_scale.yaml",
    "answer_policy.yaml",
    "planner_catalog.yaml",
)


def registry_resource_bytes(name: str) -> bytes:
    """Read one allowlisted packaged runtime-registry resource."""
    if name not in REGISTRY_RESOURCE_NAMES:
        raise ValueError("unknown registry resource")
    primary = files(__package__).joinpath("registries", name)
    try:
        return primary.read_bytes()
    except FileNotFoundError:
        destination = f"finproof/resources/registries/{name}"
        distribution = importlib_metadata.distribution("finproof")
        root = Path(str(distribution.locate_file("")))
        candidate = Path(str(distribution.locate_file(destination)))
        if candidate != root.joinpath(*destination.split("/")):
            raise ValueError("registry resource location differs") from None
        return read_held_regular_file(candidate)
