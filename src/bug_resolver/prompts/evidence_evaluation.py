"""Prompt helper for evidence evaluation language-model experiments."""

from __future__ import annotations


class EvidenceEvaluationPromptBuilder:
    """
    Standalone evidence evaluation prompt template for prompt experiments.

    The production EvidenceEvaluatorAgent is deterministic; keep this helper for
    isolated prompt iteration if LLM evaluation is explored later.
    """

    def build_prompt(self) -> str:
        return (
            "Evaluate whether the RCA is sufficiently supported by evidence. "
            "Check confidence, missing evidence, conflicting evidence, generic claims, "
            "and whether retry is required. Return structured evaluation only."
        )
