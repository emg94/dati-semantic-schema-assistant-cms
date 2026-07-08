from pathlib import Path

import pytest

from schema_assistant.ingestion.discovery import SourceFile
from schema_assistant.ingestion.parsers import AssetParser


def test_parse_yaml_asset(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    source_path = tmp_path / "schema.yaml"
    source_path.write_text("info:\n  title: Test\n", encoding="utf-8")

    parsed = AssetParser().parse(_source(source_path, "yaml_schemas"))

    assert "Test" in parsed.content
    assert parsed.processed_payload["format"] == "yaml"


def test_parse_csv_asset(tmp_path: Path) -> None:
    source_path = tmp_path / "date.csv"
    source_path.write_text("name,date\nA,2026-01-01\n", encoding="utf-8")

    parsed = AssetParser().parse(_source(source_path, "dates_collection"))

    assert "2026-01-01" in parsed.content
    assert parsed.processed_payload["row_count"] == 1


def test_parse_ttl_asset(tmp_path: Path) -> None:
    pytest.importorskip("rdflib")
    source_path = tmp_path / "vocab.ttl"
    source_path.write_text(
        """
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex: <https://example.org/> .

ex:item a skos:Concept ;
  skos:prefLabel "Elemento"@it ;
  skos:definition "Definizione di test"@it .
""".strip(),
        encoding="utf-8",
    )

    parsed = AssetParser().parse(_source(source_path, "vocabularies"))

    assert "Elemento" in parsed.content
    assert parsed.processed_payload["triple_count"] >= 3


def _source(path: Path, resource_id: str) -> SourceFile:
    return SourceFile(
        entity_id="istat",
        resource_id=resource_id,  # type: ignore[arg-type]
        path=path,
        relative_path=path.name,
        source_uri=f"file://{path.name}",
    )
