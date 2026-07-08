from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ResourceKind = Literal[
    "ontologies",
    "ttl_schemas",
    "yaml_schemas",
    "vocabularies",
    "context_documents",
    "dates_collection",
]


class SourceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    resource_id: ResourceKind
    source_uri: str
    storage_uri: str | None = None
    source_hash: str
    content_type: str = "text/plain"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("entity_id", "source_uri", "source_hash")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be empty")
        return stripped


class ChunkDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    entity_id: str
    resource_id: ResourceKind
    shard_id: str
    content: str
    embedding: list[float]
    source_uri: str
    storage_uri: str | None = None
    source_hash: str
    chunk_index: int = Field(ge=0)
    token_count: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("chunk_id", "entity_id", "shard_id", "content", "source_uri", "source_hash")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be empty")
        return stripped

    @field_validator("embedding")
    @classmethod
    def _embedding_not_empty(cls, value: list[float]) -> list[float]:
        if not value:
            raise ValueError("embedding cannot be empty")
        return value


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    entity_id: str
    resource_id: ResourceKind
    content: str
    source_uri: str
    storage_uri: str | None = None
    distance: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
