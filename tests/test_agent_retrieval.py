from pathlib import Path

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


def test_retrieval_maps_classifications_to_vocabularies() -> None:
    pytest.importorskip("pydantic")
    from schema_assistant.agent.retrieval import _detect_resources
    from schema_assistant.knowledge_base.models import ResourceKind

    keywords: dict[ResourceKind, list[str]] = {
        "vocabularies": ["classificazione", "classificazioni", "benefici"]
    }

    assert "vocabularies" in _detect_resources(
        "Numero totale di benefici distinti nelle classificazioni INPS e INAIL",
        keywords,
    )


def test_retrieval_merges_resource_keywords_and_routing_lexicon(tmp_path: Path) -> None:
    pytest.importorskip("pydantic")
    from schema_assistant.agent.retrieval import _load_resource_keywords

    resources_path = tmp_path / "resources.json"
    lexicon_path = tmp_path / "routing_lexicon.json"
    resources_path.write_text(
        '{"vocabularies": {"keywords": ["vocabolario"]}}',
        encoding="utf-8",
    )
    lexicon_path.write_text(
        '{"vocabularies": {"keywords": ["benefici"]}}',
        encoding="utf-8",
    )

    keywords = _load_resource_keywords(resources_path, lexicon_path)

    assert keywords["vocabularies"] == ["benefici", "vocabolario"]


def test_retrieval_uses_entity_hints_without_matching_generic_words(tmp_path: Path) -> None:
    pytest.importorskip("pydantic")
    from schema_assistant.agent.retrieval import _detect_entities, _load_entity_hints

    lexicon_path = tmp_path / "routing_lexicon.json"
    lexicon_path.write_text(
        """
        {
          "entity_hints": {
            "istat": {"keywords": ["ateco", "attivita economiche", "risorse"]},
            "inps": {"keywords": ["prestazioni pensionistiche", "servizi"]}
          }
        }
        """,
        encoding="utf-8",
    )

    hints = _load_entity_hints(lexicon_path)

    assert _detect_entities("Qual e il codice ATECO di un paninaro?", hints) == {"istat"}
    assert _detect_entities("Mostrami le risorse disponibili", hints) == set()


def test_retrieval_routes_ateco_questions_to_vocabularies() -> None:
    pytest.importorskip("pydantic")
    from schema_assistant.agent.retrieval import _detect_resources
    from schema_assistant.knowledge_base.models import ResourceKind

    keywords: dict[ResourceKind, list[str]] = {
        "vocabularies": ["classificazione", "ateco", "codice ateco"]
    }

    assert "vocabularies" in _detect_resources(
        "Qual e il codice ATECO di un paninaro?",
        keywords,
    )


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
    assert _is_listing_question("Numero totale di benefici distinti per i superstiti")
    assert not _is_listing_question("Dimmi cos'e INAIL")
