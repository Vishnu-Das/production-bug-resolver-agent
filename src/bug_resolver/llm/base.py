from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)


@runtime_checkable
class LLMClient(Protocol):
    """Contract for LLM text and structured generation."""

    async def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        """Generate plain text from a prompt."""
        ...

    async def generate_structured(
        self,
        prompt: str,
        output_schema: type[StructuredOutputT],
        *,
        system_prompt: str | None = None,
    ) -> StructuredOutputT:
        """
        Generate a Pydantic-validated structured output.

        Example:
            result = await llm.generate_structured(prompt, RCAReport)
        """
        ...