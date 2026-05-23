"""OpenAI-backed embedding client for indexing and retrieval."""

from openai import AsyncOpenAI

from bug_resolver.embeddings.base import EmbeddingClient
from bug_resolver.utils.observability import get_logger, log_debug_payload, traceable


logger = get_logger(__name__)


class OpenAIEmbeddingClient(EmbeddingClient):
    """Embedding client adapter around the OpenAI embeddings API."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required for OpenAIEmbeddingClient")

        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    @traceable(name="embeddings.embed_text", run_type="embedding")
    async def embed_text(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Cannot embed empty text")

        embeddings = await self.embed_texts([text])
        return embeddings[0]

    @traceable(name="embeddings.embed_texts", run_type="embedding")
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        cleaned_texts = [text for text in texts if text.strip()]

        if not cleaned_texts:
            raise ValueError("Cannot embed empty text list")

        logger.info(
            "embedding request started model=%s text_count=%s",
            self.model,
            len(cleaned_texts),
        )
        log_debug_payload(logger, "embedding input texts", payload=cleaned_texts)

        response = await self.client.embeddings.create(
            model=self.model,
            input=cleaned_texts,
        )

        embeddings = [item.embedding for item in response.data]
        logger.info(
            "embedding request finished model=%s vector_count=%s",
            self.model,
            len(embeddings),
        )
        return embeddings
