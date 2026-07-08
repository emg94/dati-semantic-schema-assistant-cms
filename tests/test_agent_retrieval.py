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


def test_retrieval_context_does_not_include_source_markers() -> None:
    pytest.importorskip("pydantic")
    from schema_assistant.agent.retrieval import _build_context
    from schema_assistant.knowledge_base.models import SearchResult

    context = _build_context(
        [
            SearchResult(
                chunk_id="1",
                entity_id="istat",
                resource_id="vocabularies",
                content="Contenuto di test",
                source_uri="https://example.org/source.ttl",
            )
        ],
        max_chars=1000,
    )

    assert "[Fonte" not in context
    assert "https://example.org/source.ttl" not in context


def test_retrieval_context_removes_source_lines_from_chunk_content() -> None:
    pytest.importorskip("pydantic")
    from schema_assistant.agent.retrieval import _build_context
    from schema_assistant.knowledge_base.models import SearchResult

    context = _build_context(
        [
            SearchResult(
                chunk_id="1",
                entity_id="inail",
                resource_id="ontologies",
                content=(
                    "Titolo: Core INAIL Ontology\n"
                    "Fonte: https://example.org/core.ttl\n"
                    "URI: https://w3id.org/italia/work-accident/onto/core/"
                ),
                source_uri="https://example.org/source.ttl",
            )
        ],
        max_chars=1000,
    )

    assert "Core INAIL Ontology" in context
    assert "https://example.org/core.ttl" not in context
    assert "https://w3id.org/italia/work-accident/onto/core/" not in context


def test_retrieval_detects_listing_questions() -> None:
    pytest.importorskip("pydantic")
    from schema_assistant.agent.retrieval import _is_listing_question

    assert _is_listing_question("Quali ontologie ha pubblicato INAIL?")
    assert not _is_listing_question("Dimmi cos'e INAIL")
