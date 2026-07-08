import pytest


def test_retrieval_detects_entities_and_catalog() -> None:
    pytest.importorskip("pydantic")
    from schema_assistant.agent.retrieval import _detect_entities

    assert _detect_entities("Mostrami i vocabolari ISTAT su schema.gov.it") == {
        "catalog",
        "istat",
    }


def test_retrieval_detects_date_resource() -> None:
    pytest.importorskip("pydantic")
    from schema_assistant.agent.retrieval import _detect_resources

    assert "dates_collection" in _detect_resources("Quando e stata pubblicata?", {})


def test_catalog_resources_use_catalog_entity_filter() -> None:
    pytest.importorskip("pydantic")
    from schema_assistant.agent.retrieval import _entity_filter_for_resources

    assert _entity_filter_for_resources({"istat"}, {"dates_collection"}) == {"catalog"}
