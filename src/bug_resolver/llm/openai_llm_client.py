"""OpenAI-backed LLM client for text and structured model outputs."""

from openai import AsyncOpenAI

from bug_resolver.errors import LLMGenerationError
from bug_resolver.llm.base import LLMClient, StructuredOutputT
from bug_resolver.utils.observability import get_logger, log_debug_payload, traceable


logger = get_logger(__name__)


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

    @traceable(name="llm.generate_text", run_type="llm")
    async def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        messages = self._build_messages(prompt=prompt, system_prompt=system_prompt)
        logger.info("llm text generation started model=%s prompt_chars=%s", self.model, len(prompt))
        log_debug_payload(logger, "llm text prompt", payload=prompt)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
        except Exception as exc:
            raise LLMGenerationError(
                "OpenAI text generation failed.",
                component="openai_llm_client",
                context={"model": self.model},
            ) from exc

        content = response.choices[0].message.content

        if content is None:
            raise ValueError("OpenAI response did not contain text content")

        logger.info(
            "llm text generation finished model=%s response_chars=%s",
            self.model,
            len(content),
        )
        log_debug_payload(logger, "llm text response", payload=content)
        return content

    @traceable(name="llm.generate_structured", run_type="llm")
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
        logger.info(
            "llm structured generation started model=%s schema=%s prompt_chars=%s",
            self.model,
            output_schema.__name__,
            len(prompt),
        )
        log_debug_payload(logger, "llm structured prompt", payload=prompt)

        try:
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=output_schema,
            )
        except Exception as exc:
            raise LLMGenerationError(
                "OpenAI structured generation failed.",
                component="openai_llm_client",
                context={
                    "model": self.model,
                    "schema": output_schema.__name__,
                },
            ) from exc

        parsed = response.choices[0].message.parsed

        if parsed is None:
            raise ValueError("OpenAI response did not contain structured output")

        logger.info(
            "llm structured generation finished model=%s schema=%s",
            self.model,
            output_schema.__name__,
        )
        log_debug_payload(logger, "llm structured response", payload=parsed)
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
