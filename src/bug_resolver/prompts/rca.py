"""Prompt helper for RCA generation experiments."""

from __future__ import annotations


class RCAPromptBuilder:
    """
    Standalone RCA prompt template for prompt experiments.

    The production RCAWriterAgent owns its runtime structured prompt directly;
    keep this helper for isolated prompt iteration and documentation.
    """

    def build_prompt(self) -> str:
        return (
            "Generate an evidence-backed root cause analysis. "
            "Distinguish symptoms from root cause, cite evidence IDs, "
            "avoid unsupported claims, include confidence reasoning, "
            "and list open questions when evidence is incomplete."
        )
