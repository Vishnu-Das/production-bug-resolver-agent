"""Prompt helper for solution recommendation experiments."""

from __future__ import annotations


class SolutionPromptBuilder:
    """
    Standalone solution recommendation prompt template for prompt experiments.

    The production SolutionRecommendationAgent owns its runtime structured prompt
    directly; keep this helper for isolated prompt iteration and documentation.
    """

    def build_prompt(self) -> str:
        return (
            "Generate an analyze-only solution recommendation from the RCA. "
            "Include immediate steps, long-term prevention, tests to add, "
            "monitoring improvements, risks, confidence, and evidence IDs. "
            "Do not generate or apply code patches."
        )
