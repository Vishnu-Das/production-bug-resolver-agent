from __future__ import annotations


class HypothesisPromptBuilder:
    """
    Placeholder prompt builder for future LLM-based hypothesis generation.

    Current HypothesisAgent is deterministic.
    Later, this builder can create prompts for structured LLM output.
    """

    def build_prompt(self) -> str:
        return (
            "Generate evidence-backed root-cause hypotheses. "
            "Every hypothesis must cite supporting evidence IDs, avoid unsupported "
            "claims, include assumptions, and mark missing evidence as open questions."
        )