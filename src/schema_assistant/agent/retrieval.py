from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from schema_assistant.agent.config import AgentSettings, get_settings
from schema_assistant.knowledge_base.embeddings import VertexEmbeddingClient
from schema_assistant.knowledge_base.firestore_store import FirestoreVectorStore
from schema_assistant.knowledge_base.models import MetadataSearchResult, ResourceKind, SearchResult

KNOWN_ENTITIES = {"istat", "inps", "inail", "italia"}
CATALOG_KEYWORDS = {"schema.gov.it", "catalogo", "interoperabilita", "documento", "documenti"}
CATALOG_RESOURCES = {"context_documents", "dates_collection"}


@dataclass(frozen=True)
class RetrievalResult:
    context: str
    sources: list[str]
    chunks: list[SearchResult]
    metadata_assets: list[MetadataSearchResult]
    detected_entities: set[str]
    detected_resources: set[str]
    listing_question: bool


class KnowledgeBaseRetriever:
    def __init__(self, settings: AgentSettings) -> None:
        self._settings = settings
        self._resource_keywords = _load_resource_keywords(
            settings.resources_config_path,
            settings.routing_lexicon_config_path,
        )
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
        listing_question = _is_listing_question(question)
        search_limit = (
            self._settings.rag_top_k * 2 if listing_question else self._settings.rag_top_k
        )
        candidate_limit = (
            self._settings.rag_candidate_limit * 2
            if listing_question
            else self._settings.rag_candidate_limit
        )
        if entity_filter or detected_resources:
            candidate_limit = max(candidate_limit, search_limit * 20)
        context_max_chars = (
            self._settings.rag_context_max_chars * 2
            if listing_question
            else self._settings.rag_context_max_chars
        )
        query_vector = self._embeddings.embed_query(question)
        metadata_assets = self._metadata_assets(
            question=question,
            entity_filter=entity_filter,
            detected_resources=detected_resources,
            listing_question=listing_question,
        )

        chunks = self._store.search(
            query_vector,
            limit=search_limit,
            candidate_limit=candidate_limit,
            entity_ids=entity_filter,
            resource_ids=detected_resources or None,
        )

        context = _join_contexts(
            _build_metadata_context(metadata_assets),
            _build_context(chunks, max_chars=context_max_chars) if chunks else None,
        )
        if not context:
            context = _empty_context()
        sources = _dedupe_sources(chunks, metadata_assets)
        return RetrievalResult(
            context=context,
            sources=sources,
            chunks=chunks,
            metadata_assets=metadata_assets,
            detected_entities=detected_entities,
            detected_resources=detected_resources,
            listing_question=listing_question,
        )

    def _metadata_assets(
        self,
        *,
        question: str,
        entity_filter: set[str] | None,
        detected_resources: set[str],
        listing_question: bool,
    ) -> list[MetadataSearchResult]:
        if not listing_question or not entity_filter or not detected_resources:
            return []

        assets = self._store.list_asset_metadata(
            entity_ids=entity_filter,
            resource_ids=detected_resources,
        )
        terms = _important_terms(question)
        scored_assets = [
            (asset, _metadata_score(asset, terms))
            for asset in assets
            if not terms or _metadata_score(asset, terms) > 0
        ]
        if not scored_assets:
            return sorted(assets, key=lambda asset: (asset.entity_id, asset.title))[:40]

        scored_assets.sort(key=lambda item: (-item[1], item[0].entity_id, item[0].title))
        return [asset for asset, _score in scored_assets[:40]]


@lru_cache(maxsize=1)
def get_knowledge_base_retriever() -> KnowledgeBaseRetriever:
    return KnowledgeBaseRetriever(get_settings())


def _load_resource_keywords(*paths: Path) -> dict[ResourceKind, list[str]]:
    keywords: dict[ResourceKind, list[str]] = {}
    for path in paths:
        if not path.exists():
            continue

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        for resource_id, config in payload.items():
            if not isinstance(config, dict):
                continue
            raw_keywords = config.get("keywords") or []
            current_keywords = keywords.setdefault(resource_id, [])
            current_keywords.extend(str(item).lower() for item in raw_keywords if str(item).strip())
    for resource_id, values in keywords.items():
        keywords[resource_id] = sorted(set(values))
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
        return _empty_context()

    blocks: list[str] = []
    used_chars = 0
    for index, chunk in enumerate(chunks, start=1):
        text = _sanitize_context_content(chunk.content)
        if not text:
            continue

        block = (
            f"Estratto {index}\n"
            f"Ente: {chunk.entity_id}\n"
            f"Risorsa: {chunk.resource_id}\n"
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


def _build_metadata_context(assets: list[MetadataSearchResult]) -> str | None:
    if not assets:
        return None

    lines = [
        "Indice metadata degli asset pertinenti.",
        "Usa questo indice per domande di elenco, confronto o conteggio.",
    ]
    for index, asset in enumerate(assets, start=1):
        labels = "; ".join(asset.labels[:8])
        keywords = "; ".join(asset.keywords[:12])
        lines.append(
            "\n".join(
                item
                for item in [
                    f"Asset {index}",
                    f"Ente: {asset.entity_id}",
                    f"Risorsa: {asset.resource_id}",
                    f"Titolo: {asset.title}",
                    f"Percorso: {asset.relative_path}",
                    f"Formato: {asset.format or asset.content_type}",
                    f"Label: {labels}" if labels else "",
                    f"Keyword: {keywords}" if keywords else "",
                ]
                if item
            )
        )
    return "\n\n---\n\n".join(lines)


def _empty_context() -> str:
    return (
        "Nessun contesto e stato trovato nella knowledge base per questa domanda. "
        "Rispondi dichiarando che non hai informazioni sufficienti."
    )


def _join_contexts(*contexts: str | None) -> str:
    return "\n\n===\n\n".join(context for context in contexts if context)


def _sanitize_context_content(content: str) -> str:
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if re.match(r"^(fonte|source|uri)\s*:", stripped, flags=re.IGNORECASE):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _dedupe_sources(
    chunks: list[SearchResult],
    metadata_assets: list[MetadataSearchResult] | None = None,
) -> list[str]:
    sources = []
    seen = set()
    for source in [
        *(asset.source_uri for asset in metadata_assets or []),
        *(chunk.source_uri for chunk in chunks),
    ]:
        if source in seen:
            continue
        seen.add(source)
        sources.append(source)
    return sources


def _normalize_text(value: str) -> str:
    lowered = value.lower()
    return re.sub(r"\s+", " ", lowered).strip()


def _is_listing_question(question: str) -> bool:
    normalized = _normalize_text(question)
    listing_keywords = {
        "elenca",
        "elenco",
        "lista",
        "quali",
        "quanti",
        "quante",
        "numero",
        "totale",
        "distinti",
        "distinte",
        "combinano",
        "combinate",
        "tutte",
        "tutti",
        "pubblicato",
        "pubblicati",
        "pubblicate",
        "risorse",
        "ontologie",
        "vocabolari",
        "classificazione",
        "classificazioni",
        "schemi",
    }
    return any(keyword in normalized for keyword in listing_keywords)


def _important_terms(question: str) -> set[str]:
    stop_words = {
        "agli",
        "alla",
        "alle",
        "associati",
        "classificazioni",
        "combinano",
        "combinate",
        "come",
        "con",
        "degli",
        "delle",
        "distinti",
        "distinte",
        "inail",
        "inps",
        "istat",
        "italia",
        "numero",
        "ontologie",
        "quale",
        "quali",
        "quando",
        "risorse",
        "schemi",
        "sono",
        "totale",
        "vocabolari",
    }
    normalized = _normalize_text(question)
    return {
        token
        for token in re.findall(r"\w{4,}", normalized)
        if token not in stop_words and not token.isdigit()
    }


def _metadata_score(asset: MetadataSearchResult, terms: set[str]) -> int:
    search_text = _normalize_text(
        " ".join(
            [
                asset.title,
                asset.relative_path,
                " ".join(asset.labels),
                " ".join(asset.keywords),
            ]
        )
    )
    return sum(1 for term in terms if term in search_text)
