"""Embedding provider protocol used by code and knowledge retrieval adapters."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingClient(Protocol):
    """Contract for text embedding providers."""

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text input."""
        ...

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text inputs."""
        ...
