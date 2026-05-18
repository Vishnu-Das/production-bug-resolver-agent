import pytest

from bug_resolver.embeddings.openai_embedding_client import OpenAIEmbeddingClient


def test_openai_embedding_client_requires_api_key():
    with pytest.raises(ValueError, match="OpenAI API key is required"):
        OpenAIEmbeddingClient(api_key="")


@pytest.mark.asyncio
async def test_openai_embedding_client_rejects_empty_text():
    client = OpenAIEmbeddingClient(api_key="test-key")

    with pytest.raises(ValueError, match="Cannot embed empty text"):
        await client.embed_text("   ")


@pytest.mark.asyncio
async def test_openai_embedding_client_rejects_empty_text_list():
    client = OpenAIEmbeddingClient(api_key="test-key")

    with pytest.raises(ValueError, match="Cannot embed empty text list"):
        await client.embed_texts(["   ", ""])


@pytest.mark.asyncio
async def test_openai_embedding_client_embeds_texts(monkeypatch):
    class FakeEmbeddingItem:
        def __init__(self, embedding: list[float]) -> None:
            self.embedding = embedding

    class FakeEmbeddingResponse:
        data = [
            FakeEmbeddingItem([0.1, 0.2, 0.3]),
            FakeEmbeddingItem([0.4, 0.5, 0.6]),
        ]

    class FakeEmbeddingsResource:
        async def create(self, model: str, input: list[str]) -> FakeEmbeddingResponse:
            assert model == "test-embedding-model"
            assert input == ["hello", "world"]
            return FakeEmbeddingResponse()

    class FakeAsyncOpenAI:
        embeddings = FakeEmbeddingsResource()

    client = OpenAIEmbeddingClient(
        api_key="test-key",
        model="test-embedding-model",
    )
    monkeypatch.setattr(client, "client", FakeAsyncOpenAI())

    result = await client.embed_texts(["hello", "world"])

    assert result == [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
    ]


@pytest.mark.asyncio
async def test_openai_embedding_client_embeds_single_text(monkeypatch):
    class FakeEmbeddingItem:
        def __init__(self, embedding: list[float]) -> None:
            self.embedding = embedding

    class FakeEmbeddingResponse:
        data = [
            FakeEmbeddingItem([0.1, 0.2, 0.3]),
        ]

    class FakeEmbeddingsResource:
        async def create(self, model: str, input: list[str]) -> FakeEmbeddingResponse:
            assert input == ["hello"]
            return FakeEmbeddingResponse()

    class FakeAsyncOpenAI:
        embeddings = FakeEmbeddingsResource()

    client = OpenAIEmbeddingClient(api_key="test-key")
    monkeypatch.setattr(client, "client", FakeAsyncOpenAI())

    result = await client.embed_text("hello")

    assert result == [0.1, 0.2, 0.3]