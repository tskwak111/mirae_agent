from pathlib import Path

import pytest
import yaml
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).parents[2]
ONTOLOGY = ROOT / "ontology"
NAMES = ("common.ttl", "bond_kr.ttl", "etf_kr.ttl", "etf_gl.ttl", "fund_pub.ttl")
FP = Namespace("http://mafest.ai/product#")


def _all_graphs() -> Graph:
    graph = Graph()
    for name in NAMES:
        graph.parse(ONTOLOGY / name, format="turtle")
    return graph


def test_submission_has_exactly_the_five_required_ontologies() -> None:
    assert tuple(sorted(path.name for path in ONTOLOGY.glob("*.ttl"))) == tuple(sorted(NAMES))


@pytest.mark.parametrize("name", NAMES)
def test_submission_ontology_is_valid_turtle(name: str) -> None:
    assert len(Graph().parse(ONTOLOGY / name, format="turtle")) > 0


def test_domain_classes_share_product_and_evidence_contract() -> None:
    graph = _all_graphs()
    assert (FP.DomesticBond, RDFS.subClassOf, FP.Product) in graph
    assert (FP.DomesticETF, RDFS.subClassOf, FP.ListedProduct) in graph
    assert (FP.DomesticETN, RDFS.subClassOf, FP.ListedProduct) in graph
    assert (FP.OverseasETF, RDFS.subClassOf, FP.ListedProduct) in graph
    assert (FP.OverseasETN, RDFS.subClassOf, FP.ListedProduct) in graph
    assert (FP.PublicFund, RDFS.subClassOf, FP.Product) in graph
    assert (FP.hasEvidence, RDF.type, OWL.ObjectProperty) in graph


def test_source_fidelity_and_native_grains_are_explicit() -> None:
    graph = _all_graphs()
    for grain in (FP.instrument, FP.listed_product, FP.fund_item):
        assert (grain, RDF.type, FP.ResultGrain) in graph
    for property_name in (
        "sourceTable",
        "sourceFile",
        "sourceSheet",
        "sourceRowNumber",
        "sourceColumn",
        "rawValue",
        "normalizedValue",
        "transformationRuleVersion",
        "qualityStatus",
        "applicableDate",
    ):
        assert (FP[property_name], RDF.type, OWL.DatatypeProperty) in graph
    assert (FP.DomesticBond, FP.nativeGrain, FP.instrument) in graph
    assert (FP.DomesticETF, FP.nativeGrain, FP.listed_product) in graph
    assert (FP.OverseasETF, FP.nativeGrain, FP.listed_product) in graph
    assert (FP.PublicFund, FP.nativeGrain, FP.fund_item) in graph


def test_ontologies_have_korean_labels_and_preserve_frozen_boundaries() -> None:
    graph = _all_graphs()
    for resource in (
        FP.Product,
        FP.Evidence,
        FP.DomesticBond,
        FP.DomesticETF,
        FP.DomesticETN,
        FP.OverseasETF,
        FP.OverseasETN,
        FP.PublicFund,
    ):
        assert any(
            isinstance(label, Literal) and label.language == "ko"
            for label in graph.objects(resource, RDFS.label)
        )
    assert FP.DomesticETF != FP.DomesticETN
    assert FP.OverseasETF != FP.OverseasETN
    overseas = "\n".join(
        str(term).lower()
        for term in Graph().parse(ONTOLOGY / "etf_gl.ttl", format="turtle").all_nodes()
    )
    assert "return1y" not in overseas
    assert "return_1y" not in overseas
    assert "du_er_1y" not in overseas
    assert not any("buyable_quantity" in str(term).lower() for term in graph.all_nodes())
    text = "\n".join((ONTOLOGY / name).read_text(encoding="utf-8") for name in NAMES).lower()
    assert "api." not in text
    assert "실시간" not in text


def test_state_rules_match_the_implemented_registry() -> None:
    graph = _all_graphs()
    registered = yaml.safe_load((ROOT / "config/state_rules.yaml").read_text(encoding="utf-8"))[
        "rules"
    ]
    assert {
        str(registry_id)
        for state_rule in graph.subjects(RDF.type, FP.StateRule)
        for registry_id in graph.objects(state_rule, FP.registryId)
    } == set(registered)
