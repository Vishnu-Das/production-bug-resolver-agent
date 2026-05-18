from openai import AsyncOpenAI

from bug_resolver.embeddings.base import EmbeddingClient


class OpenAIEmbeddingClient(EmbeddingClient):
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required for OpenAIEmbeddingClient")

        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    async def embed_text(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Cannot embed empty text")

        embeddings = await self.embed_texts([text])
        return embeddings[0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        cleaned_texts = [text for text in texts if text.strip()]

        if not cleaned_texts:
            raise ValueError("Cannot embed empty text list")

        response = await self.client.embeddings.create(
            model=self.model,
            input=cleaned_texts,
        )

        return [item.embedding for item in response.data]