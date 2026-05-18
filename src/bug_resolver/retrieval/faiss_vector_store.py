from __future__ import annotations

from pathlib import Path
from typing import Any

import faiss
import numpy as np
from pydantic import Field

from bug_resolver.schemas.common import StrictBaseModel


class VectorSearchResult(StrictBaseModel):
    item_id: str = Field(..., min_length=1)
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class FAISSVectorStore:
    def __init__(self, dimension: int) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be greater than 0")

        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)
        self.metadata_by_position: list[dict[str, Any]] = []

    @property
    def size(self) -> int:
        return self.index.ntotal

    def add(
        self,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]],
    ) -> None:
        if not vectors:
            return

        if len(vectors) != len(metadata):
            raise ValueError("vectors and metadata must have the same length")

        vector_array = self._to_numpy_array(vectors)
        self.index.add(vector_array)
        self.metadata_by_position.extend(metadata)

    def search(
        self,
        query_vector: list[float],
        *,
        limit: int = 5,
    ) -> list[VectorSearchResult]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        if self.size == 0:
            return []

        query_array = self._to_numpy_array([query_vector])

        scores, positions = self.index.search(query_array, min(limit, self.size))

        results: list[VectorSearchResult] = []

        for score, position in zip(scores[0], positions[0], strict=True):
            if position < 0:
                continue

            metadata = self.metadata_by_position[position]

            results.append(
                VectorSearchResult(
                    item_id=str(metadata["item_id"]),
                    score=float(score),
                    metadata=metadata,
                )
            )

        return results

    def save(self, index_path: str | Path, metadata_path: str | Path) -> None:
        import json

        index_path = Path(index_path)
        metadata_path = Path(metadata_path)

        index_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, str(index_path))

        metadata_path.write_text(
            json.dumps(self.metadata_by_position, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(
        cls,
        index_path: str | Path,
        metadata_path: str | Path,
    ) -> FAISSVectorStore:
        import json

        index_path = Path(index_path)
        metadata_path = Path(metadata_path)

        index = faiss.read_index(str(index_path))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        store = cls(dimension=index.d)
        store.index = index
        store.metadata_by_position = metadata

        return store

    def _to_numpy_array(self, vectors: list[list[float]]) -> np.ndarray:
        vector_array = np.array(vectors, dtype="float32")

        if vector_array.ndim != 2:
            raise ValueError("vectors must be a 2D list")

        if vector_array.shape[1] != self.dimension:
            raise ValueError(
                f"Expected vectors with dimension {self.dimension}, "
                f"got {vector_array.shape[1]}"
            )

        faiss.normalize_L2(vector_array)

        return vector_array