from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, cast

from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from schema_assistant.knowledge_base.models import ChunkDocument, SearchResult, SourceDocument

CHUNKS_COLLECTION_GROUP = "chunks"
EMBEDDING_FIELD = "embedding"
DISTANCE_FIELD = "vector_distance"


class FirestoreVectorStore:
    def __init__(
        self,
        *,
        project_id: str,
        database: str = "(default)",
        chunks_collection_group: str = CHUNKS_COLLECTION_GROUP,
    ) -> None:
        if not project_id:
            raise ValueError("project_id is required")

        self._client = firestore.Client(project=project_id, database=database)
        self._chunks_collection_group = chunks_collection_group

    def upsert_source(self, source: SourceDocument) -> None:
        entity_ref = self._client.collection("entities").document(source.entity_id)
        resource_ref = entity_ref.collection("resources").document(source.resource_id)
        source_ref = resource_ref.collection("sources").document(source.source_hash)

        batch = self._client.batch()
        batch.set(
            entity_ref,
            {
                "entity_id": source.entity_id,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        batch.set(
            resource_ref,
            {
                "entity_id": source.entity_id,
                "resource_id": source.resource_id,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        batch.set(
            source_ref,
            {
                **source.model_dump(mode="json"),
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        batch.commit()

    def upsert_chunks(self, chunks: Sequence[ChunkDocument]) -> int:
        written = 0
        for chunk_batch in _batches(chunks, 450):
            batch = self._client.batch()
            for chunk in chunk_batch:
                ref = self._chunk_ref(chunk)
                payload = _chunk_payload(chunk)
                batch.set(ref, payload, merge=True)
                written += 1
            batch.commit()
        return written

    def search(
        self,
        query_vector: Sequence[float],
        *,
        limit: int = 8,
        candidate_limit: int | None = None,
        entity_ids: set[str] | None = None,
        resource_ids: set[str] | None = None,
    ) -> list[SearchResult]:
        if limit <= 0:
            raise ValueError("limit must be positive")

        fetch_limit = max(limit, candidate_limit or limit)
        collection_group = self._client.collection_group(self._chunks_collection_group)
        vector_query = collection_group.find_nearest(
            vector_field=EMBEDDING_FIELD,
            query_vector=Vector(list(query_vector)),
            distance_measure=DistanceMeasure.COSINE,
            limit=fetch_limit,
            distance_result_field=DISTANCE_FIELD,
        )

        results: list[SearchResult] = []
        for snapshot in vector_query.stream():
            data = snapshot.to_dict() or {}
            if entity_ids and data.get("entity_id") not in entity_ids:
                continue
            if resource_ids and data.get("resource_id") not in resource_ids:
                continue

            results.append(_search_result(snapshot.id, data))
            if len(results) >= limit:
                break

        return results

    def _chunk_ref(self, chunk: ChunkDocument) -> Any:
        return (
            self._client.collection("entities")
            .document(chunk.entity_id)
            .collection("resources")
            .document(chunk.resource_id)
            .collection("shards")
            .document(chunk.shard_id)
            .collection(self._chunks_collection_group)
            .document(chunk.chunk_id)
        )


def _chunk_payload(chunk: ChunkDocument) -> dict[str, Any]:
    payload = cast(
        dict[str, Any], chunk.model_dump(mode="json", exclude={"created_at", "updated_at"})
    )
    payload[EMBEDDING_FIELD] = Vector(chunk.embedding)
    payload["created_at"] = chunk.created_at or firestore.SERVER_TIMESTAMP
    payload["updated_at"] = firestore.SERVER_TIMESTAMP
    return payload


def _search_result(snapshot_id: str, data: dict[str, Any]) -> SearchResult:
    return SearchResult(
        chunk_id=str(data.get("chunk_id") or snapshot_id),
        entity_id=str(data["entity_id"]),
        resource_id=data["resource_id"],
        content=str(data["content"]),
        source_uri=str(data["source_uri"]),
        storage_uri=data.get("storage_uri"),
        distance=data.get(DISTANCE_FIELD),
        metadata=data.get("metadata") or {},
    )


def _batches(items: Sequence[ChunkDocument], size: int) -> Iterable[Sequence[ChunkDocument]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]
