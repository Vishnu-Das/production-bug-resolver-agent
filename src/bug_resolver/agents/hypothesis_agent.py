from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.rules.hypothesis_rules import HypothesisRules
from bug_resolver.schemas import (
    CodeContext,
    Hypothesis,
    Incident,
    KnowledgeContext,
    LogAnalysisResult,
)
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.utils.ids import new_hypothesis_id


class HypothesisInput(StrictBaseModel):
    incident: Incident
    log_analysis: LogAnalysisResult
    code_contexts: list[CodeContext] = Field(default_factory=list)
    knowledge_contexts: list[KnowledgeContext] = Field(default_factory=list)


class HypothesisAgent(BaseAgent[HypothesisInput, list[Hypothesis]]):
    """
    Coordinates evidence-backed hypothesis generation.

    Current version is deterministic.
    Later version can use HypothesisPromptBuilder + LLMClient for structured output.
    """

    name = "hypothesis_agent"

    def __init__(self, rules: HypothesisRules | None = None) -> None:
        self._rules = rules or HypothesisRules()

    async def _run(self, input_data: HypothesisInput) -> list[Hypothesis]:
        evidence_items = self._rules.build_evidence_items(
            log_analysis=input_data.log_analysis,
            code_contexts=input_data.code_contexts,
            knowledge_contexts=input_data.knowledge_contexts,
        )

        confidence_score = self._rules.confidence_score(
            log_analysis=input_data.log_analysis,
            code_contexts=input_data.code_contexts,
            knowledge_contexts=input_data.knowledge_contexts,
        )

        hypothesis = Hypothesis(
            hypothesis_id=new_hypothesis_id(),
            title=self._rules.build_title(input_data.log_analysis),
            description=self._rules.build_description(
                incident=input_data.incident,
                log_analysis=input_data.log_analysis,
                code_contexts=input_data.code_contexts,
                knowledge_contexts=input_data.knowledge_contexts,
            ),
            suspected_root_cause=self._rules.build_suspected_root_cause(
                log_analysis=input_data.log_analysis,
                code_contexts=input_data.code_contexts,
            ),
            supporting_evidence_ids=self._rules.supporting_evidence_ids(evidence_items),
            contradicting_evidence_ids=[],
            confidence_score=confidence_score,
            status=self._rules.status_for_confidence(confidence_score),
            assumptions=self._rules.build_assumptions(
                code_contexts=input_data.code_contexts,
                knowledge_contexts=input_data.knowledge_contexts,
            ),
            open_questions=self._rules.build_open_questions(
                log_analysis=input_data.log_analysis,
                code_contexts=input_data.code_contexts,
                knowledge_contexts=input_data.knowledge_contexts,
            ),
        )

        return [hypothesis]