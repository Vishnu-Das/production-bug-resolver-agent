from __future__ import annotations


class SolutionPromptBuilder:
    """
    Placeholder prompt builder for future LLM-based solution recommendation.

    Current SolutionRecommendationAgent is deterministic.
    Later, this builder can create prompts for structured SolutionRecommendation output.
    """

    def build_prompt(self) -> str:
        return (
            "Generate an analyze-only solution recommendation from the RCA. "
            "Include immediate steps, long-term prevention, tests to add, "
            "monitoring improvements, risks, confidence, and evidence IDs. "
            "Do not generate or apply code patches."
        )