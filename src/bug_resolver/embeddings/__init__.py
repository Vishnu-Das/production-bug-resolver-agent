"""Export embedding client implementations."""

from bug_resolver.embeddings.base import EmbeddingClient
from bug_resolver.embeddings.openai_embedding_client import OpenAIEmbeddingClient

__all__ = [
    "EmbeddingClient",
    "OpenAIEmbeddingClient",
]
