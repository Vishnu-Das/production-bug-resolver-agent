import pytest

from bug_resolver.retrieval.faiss_vector_store import FAISSVectorStore


def test_faiss_vector_store_rejects_invalid_dimension():
    with pytest.raises(ValueError, match="dimension must be greater than 0"):
        FAISSVectorStore(dimension=0)


def test_faiss_vector_store_adds_and_searches_vectors():
    store = FAISSVectorStore(dimension=3)

    store.add(
        vectors=[
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        metadata=[
            {
                "item_id": "chunk-1",
                "file_path": "app.py",
            },
            {
                "item_id": "chunk-2",
                "file_path": "search.py",
            },
        ],
    )

    results = store.search([1.0, 0.0, 0.0], limit=1)

    assert store.size == 2
    assert len(results) == 1
    assert results[0].item_id == "chunk-1"
    assert results[0].metadata["file_path"] == "app.py"
    assert results[0].score > 0.99


def test_faiss_vector_store_returns_empty_results_when_empty():
    store = FAISSVectorStore(dimension=3)

    results = store.search([1.0, 0.0, 0.0])

    assert results == []


def test_faiss_vector_store_rejects_mismatched_vectors_and_metadata():
    store = FAISSVectorStore(dimension=3)

    with pytest.raises(ValueError, match="vectors and metadata must have the same length"):
        store.add(
            vectors=[
                [1.0, 0.0, 0.0],
            ],
            metadata=[],
        )


def test_faiss_vector_store_rejects_wrong_vector_dimension():
    store = FAISSVectorStore(dimension=3)

    with pytest.raises(ValueError, match="Expected vectors with dimension 3"):
        store.add(
            vectors=[
                [1.0, 0.0],
            ],
            metadata=[
                {
                    "item_id": "chunk-1",
                }
            ],
        )


def test_faiss_vector_store_rejects_invalid_limit():
    store = FAISSVectorStore(dimension=3)

    with pytest.raises(ValueError, match="limit must be greater than 0"):
        store.search([1.0, 0.0, 0.0], limit=0)


def test_faiss_vector_store_can_save_and_load(tmp_path):
    store = FAISSVectorStore(dimension=3)

    store.add(
        vectors=[
            [1.0, 0.0, 0.0],
        ],
        metadata=[
            {
                "item_id": "chunk-1",
                "file_path": "app.py",
            }
        ],
    )

    index_path = tmp_path / "index.faiss"
    metadata_path = tmp_path / "metadata.json"

    store.save(index_path=index_path, metadata_path=metadata_path)

    loaded_store = FAISSVectorStore.load(
        index_path=index_path,
        metadata_path=metadata_path,
    )

    results = loaded_store.search([1.0, 0.0, 0.0], limit=1)

    assert loaded_store.size == 1
    assert len(results) == 1
    assert results[0].item_id == "chunk-1"
    assert results[0].metadata["file_path"] == "app.py"