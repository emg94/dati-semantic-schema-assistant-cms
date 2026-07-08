import pytest


def test_firestore_write_batch_size_must_stay_within_firestore_limit() -> None:
    pytest.importorskip("google.cloud.firestore")
    from schema_assistant.knowledge_base.firestore_store import FirestoreVectorStore

    with pytest.raises(ValueError, match="between 1 and 450"):
        FirestoreVectorStore(
            project_id="test-project",
            write_batch_size=0,
        )

    with pytest.raises(ValueError, match="between 1 and 450"):
        FirestoreVectorStore(
            project_id="test-project",
            write_batch_size=451,
        )


def test_source_index_entry_normalizes_missing_values() -> None:
    pytest.importorskip("google.cloud.firestore")
    from schema_assistant.knowledge_base.firestore_store import SourceIndexEntry

    entry = SourceIndexEntry(
        source_uri="file.ttl",
        source_hash="abc",
        status="completed",
        chunks_written=12,
    )

    assert entry.status == "completed"
    assert entry.chunks_written == 12
