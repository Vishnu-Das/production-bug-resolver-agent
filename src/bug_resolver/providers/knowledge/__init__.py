"""Export knowledge-base provider implementations."""

from bug_resolver.providers.knowledge.base import KnowledgeBaseProvider
from bug_resolver.providers.knowledge.local_knowledge_base_provider import (
    LocalKnowledgeBaseProvider,
)

__all__ = [
    "KnowledgeBaseProvider",
    "LocalKnowledgeBaseProvider",
]
