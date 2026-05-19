"""OpenAI-backed LLM client for text and structured model outputs."""

from openai import AsyncOpenAI

from bug_resolver.llm.base import LLMClient, StructuredOutputT


class OpenAILLMClient(LLMClient):
    """LLM client adapter around OpenAI text and structured responses."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required for OpenAILLMClient")

        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        messages = self._build_messages(prompt=prompt, system_prompt=system_prompt)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        content = response.choices[0].message.content

        if content is None:
            raise ValueError("OpenAI response did not contain text content")

        return content

    async def generate_structured(
        self,
        prompt: str,
        output_schema: type[StructuredOutputT],
        *,
        system_prompt: str | None = None,
    ) -> StructuredOutputT:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        messages = self._build_messages(prompt=prompt, system_prompt=system_prompt)

        response = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=output_schema,
        )

        parsed = response.choices[0].message.parsed

        if parsed is None:
            raise ValueError("OpenAI response did not contain structured output")

        return parsed

    def _build_messages(
        self,
        prompt: str,
        system_prompt: str | None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        return messages
