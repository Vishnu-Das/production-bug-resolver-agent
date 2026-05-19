from __future__ import annotations


class RCAPromptBuilder:
    """
    Placeholder prompt builder for future LLM-based RCA generation.

    Current RCAWriterAgent is deterministic.
    Later, this builder can create prompts for structured RCAReport output.
    """

    def build_prompt(self) -> str:
        return (
            "Generate an evidence-backed root cause analysis. "
            "Distinguish symptoms from root cause, cite evidence IDs, "
            "avoid unsupported claims, include confidence reasoning, "
            "and list open questions when evidence is incomplete."
        )
