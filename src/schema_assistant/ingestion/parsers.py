from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urldefrag

from schema_assistant.ingestion.discovery import SourceFile

if TYPE_CHECKING:
    from rdflib import Graph, URIRef


@dataclass(frozen=True)
class ParsedAsset:
    source: SourceFile
    content: str
    source_hash: str
    content_type: str
    processed_payload: dict[str, Any] = field(default_factory=dict)


class AssetParser:
    def __init__(self, *, max_triples_per_file: int = 600) -> None:
        self._max_triples_per_file = max_triples_per_file

    def parse(self, source: SourceFile) -> ParsedAsset:
        suffix = source.path.suffix.lower()
        source_hash = file_sha256(source.path)

        if suffix == ".ttl":
            content, payload = self._parse_ttl(source.path)
            content_type = "text/turtle"
        elif suffix in {".yaml", ".yml"}:
            content, payload = self._parse_yaml(source.path)
            content_type = "application/yaml"
        elif suffix == ".pdf":
            content, payload = self._parse_pdf(source.path)
            content_type = "application/pdf"
        elif suffix == ".csv":
            content, payload = self._parse_csv(source.path)
            content_type = "text/csv"
        else:
            content = source.path.read_text(encoding="utf-8", errors="replace")
            payload = {"format": suffix.lstrip(".") or "text"}
            content_type = "text/plain"

        header = [
            f"Ente: {source.entity_id}",
            f"Risorsa: {source.resource_id}",
            f"Fonte: {source.source_uri}",
            "",
        ]

        return ParsedAsset(
            source=source,
            content="\n".join(header) + content.strip(),
            source_hash=source_hash,
            content_type=content_type,
            processed_payload={
                "entity_id": source.entity_id,
                "resource_id": source.resource_id,
                "source_uri": source.source_uri,
                "source_hash": source_hash,
                "relative_path": source.relative_path,
                **payload,
            },
        )

    def _parse_ttl(self, path: Path) -> tuple[str, dict[str, Any]]:
        from rdflib import Graph, URIRef

        graph = Graph()
        graph.parse(path, format="turtle")

        lines: list[str] = []
        namespaces = {prefix: str(namespace) for prefix, namespace in graph.namespaces()}
        subjects = sorted(
            {subject for subject in graph.subjects() if isinstance(subject, URIRef)}, key=str
        )

        for subject in subjects:
            subject_lines = _subject_summary(graph, subject)
            if subject_lines:
                lines.extend(subject_lines)
                lines.append("")

        triples = []
        for index, (subject, predicate, obj) in enumerate(graph):
            if index >= self._max_triples_per_file:
                break
            triples.append(
                {
                    "subject": _clean_node(subject),
                    "predicate": _clean_node(predicate),
                    "object": _clean_node(obj),
                }
            )

        if triples:
            lines.append("Triple principali:")
            for triple in triples:
                lines.append(f"- {triple['subject']} | {triple['predicate']} | {triple['object']}")

        return "\n".join(lines), {
            "format": "ttl",
            "namespaces": namespaces,
            "triple_count": len(graph),
            "sample_triples": triples,
        }

    @staticmethod
    def _parse_yaml(path: Path) -> tuple[str, dict[str, Any]]:
        import yaml

        with path.open("r", encoding="utf-8") as file:
            payload = yaml.safe_load(file) or {}

        content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        return content, {"format": "yaml", "content": payload}

    @staticmethod
    def _parse_pdf(path: Path) -> tuple[str, dict[str, Any]]:
        import pdfplumber

        pages: list[str] = []
        with pdfplumber.open(path) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append(f"Pagina {index}\n{page_text.strip()}")
        return "\n\n".join(pages), {"format": "pdf", "page_count": len(pages)}

    @staticmethod
    def _parse_csv(path: Path) -> tuple[str, dict[str, Any]]:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            sample = file.read(4096)
            file.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(file, dialect=dialect)
            rows = list(reader)

        lines = [json.dumps(row, ensure_ascii=False, default=str) for row in rows]
        return "\n".join(lines), {
            "format": "csv",
            "row_count": len(rows),
            "columns": list(rows[0].keys()) if rows else [],
        }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _subject_summary(graph: Graph, subject: URIRef) -> list[str]:
    from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

    labels = _literal_values(graph, subject, RDFS.label) + _literal_values(
        graph, subject, SKOS.prefLabel
    )
    descriptions = (
        _literal_values(graph, subject, RDFS.comment)
        + _literal_values(graph, subject, SKOS.definition)
        + _literal_values(graph, subject, DCTERMS.description)
    )
    types = [_clean_node(item) for item in graph.objects(subject, RDF.type)]

    if not labels and not descriptions and not types:
        return []

    lines = [f"URI: {_clean_node(subject)}"]
    if labels:
        lines.append(f"Label: {'; '.join(labels)}")
    if descriptions:
        lines.append(f"Descrizione: {'; '.join(descriptions)}")
    if types:
        lines.append(f"Tipi: {', '.join(types)}")

    broader = [_clean_node(item) for item in graph.objects(subject, SKOS.broader)]
    narrower = [_clean_node(item) for item in graph.objects(subject, SKOS.narrower)]
    subclasses = [_clean_node(item) for item in graph.objects(subject, RDFS.subClassOf)]
    ranges = [_clean_node(item) for item in graph.objects(subject, RDFS.range)]
    domains = [_clean_node(item) for item in graph.objects(subject, RDFS.domain)]

    if broader:
        lines.append(f"Broader: {', '.join(broader)}")
    if narrower:
        lines.append(f"Narrower: {', '.join(narrower)}")
    if subclasses:
        lines.append(f"SubClassOf: {', '.join(subclasses)}")
    if domains:
        lines.append(f"Domain: {', '.join(domains)}")
    if ranges:
        lines.append(f"Range: {', '.join(ranges)}")

    if (subject, RDF.type, OWL.ObjectProperty) in graph:
        lines.append("Tipo proprieta: object property")
    if (subject, RDF.type, OWL.DatatypeProperty) in graph:
        lines.append("Tipo proprieta: datatype property")

    return lines


def _literal_values(graph: Graph, subject: URIRef, predicate: URIRef) -> list[str]:
    from rdflib import Literal

    values = []
    for item in graph.objects(subject, predicate):
        if isinstance(item, Literal):
            text = str(item).strip()
            if text:
                values.append(text)
    return values


def _clean_node(value: Any) -> str:
    from rdflib import Literal, URIRef

    if isinstance(value, URIRef):
        uri, fragment = urldefrag(str(value))
        return fragment or uri
    if isinstance(value, Literal):
        text = str(value).strip()
        if value.language:
            return f"{text} @{value.language}"
        if value.datatype:
            return f"{text} ^^ {value.datatype}"
        return text
    return str(value)
