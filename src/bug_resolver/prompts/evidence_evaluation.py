from __future__ import annotations


class EvidenceEvaluationPromptBuilder:
    """
    Placeholder prompt builder for future LLM-based evidence evaluation.

    Current EvidenceEvaluatorAgent is deterministic.
    Later, this builder can create prompts for structured EvidenceEvaluationResult output.
    """

    def build_prompt(self) -> str:
        return (
            "Evaluate whether the RCA is sufficiently supported by evidence. "
            "Check confidence, missing evidence, conflicting evidence, generic claims, "
            "and whether retry is required. Return structured evaluation only."
        )