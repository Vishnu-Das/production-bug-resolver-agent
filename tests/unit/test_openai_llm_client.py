from pydantic import BaseModel
import pytest

from bug_resolver.llm.openai_llm_client import OpenAILLMClient


class FakeStructuredOutput(BaseModel):
    answer: str


def test_openai_llm_client_requires_api_key():
    with pytest.raises(ValueError, match="OpenAI API key is required"):
        OpenAILLMClient(api_key="")


@pytest.mark.asyncio
async def test_openai_llm_client_rejects_empty_text_prompt():
    client = OpenAILLMClient(api_key="test-key")

    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        await client.generate_text("   ")


@pytest.mark.asyncio
async def test_openai_llm_client_rejects_empty_structured_prompt():
    client = OpenAILLMClient(api_key="test-key")

    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        await client.generate_structured("   ", FakeStructuredOutput)


@pytest.mark.asyncio
async def test_openai_llm_client_generates_text(monkeypatch):
    class FakeMessage:
        content = "This is a generated answer."

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        async def create(self, model: str, messages: list[dict[str, str]]) -> FakeResponse:
            assert model == "test-model"
            assert messages == [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Explain RCA."},
            ]
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    client = OpenAILLMClient(api_key="test-key", model="test-model")
    monkeypatch.setattr(client, "client", FakeClient())

    result = await client.generate_text(
        "Explain RCA.",
        system_prompt="You are helpful.",
    )

    assert result == "This is a generated answer."


@pytest.mark.asyncio
async def test_openai_llm_client_generates_structured_output(monkeypatch):
    expected_output = FakeStructuredOutput(answer="Structured answer")

    class FakeMessage:
        parsed = expected_output

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeParsedCompletions:
        async def parse(
            self,
            model: str,
            messages: list[dict[str, str]],
            response_format: type[FakeStructuredOutput],
        ) -> FakeResponse:
            assert model == "test-model"
            assert messages == [
                {"role": "user", "content": "Return structured answer."},
            ]
            assert response_format is FakeStructuredOutput
            return FakeResponse()

    class FakeBetaChat:
        completions = FakeParsedCompletions()

    class FakeBeta:
        chat = FakeBetaChat()

    class FakeClient:
        beta = FakeBeta()

    client = OpenAILLMClient(api_key="test-key", model="test-model")
    monkeypatch.setattr(client, "client", FakeClient())

    result = await client.generate_structured(
        "Return structured answer.",
        FakeStructuredOutput,
    )

    assert result == expected_output