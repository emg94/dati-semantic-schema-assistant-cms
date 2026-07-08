from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from schema_assistant.agent.config import AgentSettings, get_settings
from schema_assistant.knowledge_base.embeddings import VertexEmbeddingClient
from schema_assistant.knowledge_base.firestore_store import FirestoreVectorStore
from schema_assistant.knowledge_base.models import ResourceKind, SearchResult

KNOWN_ENTITIES = {"istat", "inps", "inail", "italia"}
CATALOG_KEYWORDS = {"schema.gov.it", "catalogo", "interoperabilita", "documento", "documenti"}
CATALOG_RESOURCES = {"context_documents", "dates_collection"}


@dataclass(frozen=True)
class RetrievalResult:
    context: str
    sources: list[str]
    chunks: list[SearchResult]
    detected_entities: set[str]
    detected_resources: set[str]


class KnowledgeBaseRetriever:
    def __init__(self, settings: AgentSettings) -> None:
        self._settings = settings
        self._resource_keywords = _load_resource_keywords(settings.resources_config_path)
        self._embeddings = VertexEmbeddingClient(
            project_id=settings.project_id,
            location=settings.location,
            model=settings.embedding_model,
            output_dimensionality=settings.embedding_dimension,
        )
        self._store = FirestoreVectorStore(
            project_id=settings.project_id,
            database=settings.firestore_database,
            chunks_collection_group=settings.firestore_chunks_collection_group,
        )

    def retrieve(self, question: str) -> RetrievalResult:
        detected_entities = _detect_entities(question)
        detected_resources = _detect_resources(question, self._resource_keywords)
        entity_filter = _entity_filter_for_resources(detected_entities, detected_resources)
        query_vector = self._embeddings.embed_query(question)

        chunks = self._store.search(
            query_vector,
            limit=self._settings.rag_top_k,
            candidate_limit=self._settings.rag_candidate_limit,
            entity_ids=entity_filter,
            resource_ids=detected_resources or None,
        )

        context = _build_context(chunks, max_chars=self._settings.rag_context_max_chars)
        sources = _dedupe_sources(chunks)
        return RetrievalResult(
            context=context,
            sources=sources,
            chunks=chunks,
            detected_entities=detected_entities,
            detected_resources=detected_resources,
        )


@lru_cache(maxsize=1)
def get_knowledge_base_retriever() -> KnowledgeBaseRetriever:
    return KnowledgeBaseRetriever(get_settings())


def _load_resource_keywords(path: Path) -> dict[ResourceKind, list[str]]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    keywords: dict[ResourceKind, list[str]] = {}
    for resource_id, config in payload.items():
        if not isinstance(config, dict):
            continue
        raw_keywords = config.get("keywords") or []
        keywords[resource_id] = [str(item).lower() for item in raw_keywords if str(item).strip()]
    return keywords


def _detect_entities(question: str) -> set[str]:
    normalized = _normalize_text(question)
    detected = {entity for entity in KNOWN_ENTITIES if entity in normalized}
    if any(keyword in normalized for keyword in CATALOG_KEYWORDS):
        detected.add("catalog")
    return detected


def _detect_resources(
    question: str,
    resource_keywords: dict[ResourceKind, list[str]],
) -> set[str]:
    normalized = _normalize_text(question)
    detected: set[str] = set()

    date_words = {"data", "date", "quando", "pubblicazione", "creazione", "immissione"}
    if any(word in normalized for word in date_words):
        detected.add("dates_collection")

    for resource_id, keywords in resource_keywords.items():
        if any(_normalize_text(keyword) in normalized for keyword in keywords):
            detected.add(resource_id)

    return detected


def _entity_filter_for_resources(
    detected_entities: set[str],
    detected_resources: set[str],
) -> set[str] | None:
    if detected_resources and detected_resources.issubset(CATALOG_RESOURCES):
        return {"catalog"}
    return detected_entities or None


def _build_context(chunks: list[SearchResult], *, max_chars: int) -> str:
    if not chunks:
        return (
            "Nessun contesto e stato trovato nella knowledge base per questa domanda. "
            "Rispondi dichiarando che non hai informazioni sufficienti."
        )

    blocks: list[str] = []
    used_chars = 0
    for index, chunk in enumerate(chunks, start=1):
        text = chunk.content.strip()
        if not text:
            continue

        block = (
            f"[Fonte {index}]\n"
            f"Ente: {chunk.entity_id}\n"
            f"Risorsa: {chunk.resource_id}\n"
            f"URI: {chunk.source_uri}\n"
            f"Contenuto:\n{text}"
        )
        remaining = max_chars - used_chars
        if remaining <= 0:
            break
        if len(block) > remaining:
            block = block[:remaining].rstrip()
        blocks.append(block)
        used_chars += len(block)

    return "\n\n---\n\n".join(blocks)


def _dedupe_sources(chunks: list[SearchResult]) -> list[str]:
    sources = []
    seen = set()
    for chunk in chunks:
        source = chunk.source_uri
        if source in seen:
            continue
        seen.add(source)
        sources.append(source)
    return sources


def _normalize_text(value: str) -> str:
    lowered = value.lower()
    return re.sub(r"\s+", " ", lowered).strip()
