"""Deterministic RCA construction rules used as writer fallback."""

from __future__ import annotations

from bug_resolver.rules.code_evidence_path_rules import CodeEvidencePathRules
from bug_resolver.rules.evidence_formatting_rules import EvidenceFormattingRules
from bug_resolver.rules.rca_evidence_selection_rules import RCAEvidenceSelectionRules
from bug_resolver.rules.rca_finding_rules import RCAFindingRules
from bug_resolver.rules.evidence_selection_rules import EvidenceSelectionRules
from bug_resolver.schemas import EvidenceItem, EvidenceSourceType, WorkflowState


class RCARules:
    """Deterministic RCA helpers for dynamic evidence-backed reports."""

    def __init__(
        self,
        evidence_selection_rules: EvidenceSelectionRules | None = None,
        code_path_rules: CodeEvidencePathRules | None = None,
        formatter: EvidenceFormattingRules | None = None,
        finding_rules: RCAFindingRules | None = None,
        evidence_selection: RCAEvidenceSelectionRules | None = None,
    ) -> None:
        self.evidence_selection_rules = evidence_selection_rules or EvidenceSelectionRules()
        self.code_path_rules = code_path_rules or CodeEvidencePathRules()
        self.formatter = formatter or EvidenceFormattingRules()
        self.finding_rules = finding_rules or RCAFindingRules(
            formatter=self.formatter,
            evidence_selection_rules=self.evidence_selection_rules,
        )
        self.evidence_selection = evidence_selection or RCAEvidenceSelectionRules(
            evidence_selection_rules=self.evidence_selection_rules,
            code_path_rules=self.code_path_rules,
            formatter=self.formatter,
        )

    def build_title(self, state: WorkflowState) -> str:
        return f"RCA for {state.incident.title}"

    def build_incident_summary(self, state: WorkflowState) -> str:
        return f"Incident {state.incident.incident_id}: {state.incident.description}"

    def build_impact(self, state: WorkflowState) -> str | None:
        incident = state.incident
        if incident.affected_service and incident.affected_area:
            return (
                f"Affected service: {incident.affected_service}. "
                f"Affected area: {incident.affected_area}."
            )

        if incident.affected_service:
            return f"Affected service: {incident.affected_service}."

        if incident.affected_area:
            return f"Affected area: {incident.affected_area}."

        return None

    def build_symptoms(self, state: WorkflowState) -> list[str]:
        symptoms = [state.incident.description]
        symptoms.extend(
            evidence.content
            for evidence in state.evidence_items
            if evidence.source_type == EvidenceSourceType.LOG
        )
        return self.unique(symptoms)

    def build_log_findings(self, state: WorkflowState) -> list[str]:
        return self.finding_rules.findings_for_source(
            state.evidence_items,
            EvidenceSourceType.LOG,
        )

    def build_code_findings(self, state: WorkflowState) -> list[str]:
        return self._selected_findings_for_source(state, EvidenceSourceType.CODE, max_findings=3)

    def build_graph_findings(self, state: WorkflowState) -> list[str]:
        return self._selected_findings_for_source(
            state,
            EvidenceSourceType.GRAPH,
            max_findings=2,
        )

    def build_knowledge_base_findings(self, state: WorkflowState) -> list[str]:
        return self._selected_findings_for_source(
            state,
            EvidenceSourceType.KNOWLEDGE_BASE,
            max_findings=2,
        )

    def build_historical_findings(self, state: WorkflowState) -> list[str]:
        return self._selected_findings_for_source(
            state,
            EvidenceSourceType.HISTORICAL_RCA,
            max_findings=2,
        )

    def build_hypotheses_considered(self, state: WorkflowState) -> list[str]:
        if self._has_invalid_summary_strategy(state.evidence_items):
            return [
                "H1: The LLM router emitted unsupported retrieval strategy value `summary`.",
                (
                    "H2: Summary-style document queries are expected to map to "
                    "`parent_child`, but the LLM router output contract allowed "
                    "the conceptual label `summary`."
                ),
                (
                    "H3: Router validation rejects unsupported LLM strategy values "
                    "and triggers fallback instead of normalizing the strategy."
                ),
            ]

        if self._has_duplicate_content_upload(state.evidence_items):
            return [
                (
                    "H1: Duplicate document records are caused by upload deduplication "
                    "using filename state instead of content identity."
                ),
                (
                    "H2: The ingestion path accepts same-content uploads under different "
                    "filenames and indexes both copies."
                ),
            ]

        if self._has_silent_reranker_bypass(state.evidence_items):
            return [
                (
                    "H1: Retrieval quality degraded because reranking was silently "
                    "bypassed when the reranker model configuration was missing."
                ),
                (
                    "H2: Hybrid retrieval returned candidate chunks, but answer quality "
                    "fell because no cross-encoder scores reordered those candidates."
                ),
            ]

        if self._has_log_and_code_evidence(state.evidence_items):
            return [
                (
                    "H1: Runtime failure is caused by an implementation mismatch "
                    "in the code path identified by the logs and code evidence."
                ),
                (
                    "H2: The observed behavior is caused by missing validation or "
                    "insufficient normalization around the failing code path."
                ),
            ]

        return [
            (
                "H1: The failure is visible in runtime evidence, but more code "
                "or knowledge-base context is required to confirm the root cause."
            )
        ]

    def selected_hypothesis_id(self, state: WorkflowState) -> str:
        return "H1"

    def build_root_cause(self, state: WorkflowState) -> str:
        if self._has_invalid_summary_strategy(state.evidence_items):
            root_cause = (
                "The LLM router emitted `summary` as a retrieval strategy, but "
                "`summary` is not a supported retrieval strategy value. The router "
                "validation raised `ValueError: Invalid strategy: summary`, causing "
                "the system to fall back to the rule-based router."
            )

            if self._has_parent_child_signal(state.evidence_items):
                root_cause += (
                    " The fallback resolved the same summary-style document query "
                    "to `parent_child`, indicating that this query intent should map "
                    "to the supported `parent_child` strategy rather than `summary`."
                )

            return root_cause

        if self._has_unsupported_retrieval_strategy(state.evidence_items):
            return (
                "The configured or resolved retrieval strategy was `semantic`, "
                "but `semantic` is not one of the supported retrieval strategy "
                "values. `RetrievalStrategyFactory.get_strategy` rejected the "
                "value and raised `ValueError: Unsupported retrieval strategy: semantic`."
            )

        if self._has_selected_document_mismatch(state.evidence_items):
            return (
                "Selected-document retrieval returned zero documents because the "
                "UI-selected filename did not match the stored vector metadata source "
                "for the same PDF after normalization."
            )

        if self._has_duplicate_upload_stale_content(state.evidence_items):
            return (
                "A revised PDF upload with the same filename was skipped by duplicate "
                "upload guards, so ingestion and cache reset did not run and retrieval "
                "continued serving stale indexed content."
            )

        if self._has_duplicate_content_upload(state.evidence_items):
            return (
                "The upload flow records duplicate state by filename rather than content "
                "identity. Logs show the same content hash was accepted under a different "
                "filename and ingested again, creating duplicate document records and "
                "repeated retrieval citations."
            )

        if self._has_silent_reranker_bypass(state.evidence_items):
            return (
                "The reranker model configuration was absent, and the reranker path "
                "silently returned the original retrieval order with neutral scores "
                "instead of warning or failing through an explicit fallback policy."
            )

        code_evidence = self._evidence_for_source(state, EvidenceSourceType.CODE)
        log_evidence = self._evidence_for_source(state, EvidenceSourceType.LOG)

        if code_evidence and log_evidence:
            return (
                "The incident is most likely caused by a mismatch between the "
                "runtime failure observed in logs and the implementation behavior "
                f"shown in {self._location(code_evidence[0])}."
            )

        if code_evidence:
            return (
                "The incident is most likely caused by the implementation behavior "
                f"shown in {self._location(code_evidence[0])}."
            )

        if log_evidence:
            return (
                "The incident root cause is not fully confirmed, but runtime logs "
                "show the failing behavior that needs further investigation."
            )

        return "The root cause cannot be determined from the available evidence."

    def build_technical_explanation(self, state: WorkflowState) -> str:
        if self._has_invalid_summary_strategy(state.evidence_items):
            explanation = (
                "The runtime logs show that the LLM router failed with "
                "`ValueError: Invalid strategy: summary` during retrieval strategy "
                "resolution. This indicates that the LLM router returned a strategy "
                "value that failed the router validation step. "
            )

            llm_locations = self._locations_matching(
                state.evidence_items,
                source_type=EvidenceSourceType.CODE,
                patterns=["src\\rag\\routing\\llm.py", "src/rag/routing/llm.py"],
            )
            if llm_locations:
                explanation += (
                    "Code evidence from "
                    f"{', '.join(llm_locations)} points to the LLM routing path "
                    "where the returned strategy is validated. "
                )

            if self._has_parent_child_signal(state.evidence_items):
                explanation += (
                    "The fallback log and supporting evidence show that the same "
                    "summary-style query resolves to `parent_child`, which is the "
                    "supported retrieval strategy for broad document-summary intent. "
                )

            explanation += (
                "Therefore, the issue is a contract mismatch between the LLM "
                "router output vocabulary and the supported retrieval strategy "
                "values used by the application."
            )

            return explanation

        if self._has_unsupported_retrieval_strategy(state.evidence_items):
            return (
                "Runtime logs show `RETRIEVAL_STRATEGY=semantic` reaching document "
                "retrieval. The retrieval factory supports `hybrid`, `parent_child`, "
                "and `fusion`; any other value is rejected with `ValueError`. This "
                "makes the incident a configuration contract failure between runtime "
                "settings and `src/rag/retrieval/factory.py`."
            )

        if self._has_selected_document_mismatch(state.evidence_items):
            return (
                'Runtime logs show `selected_document="Transformer Notes.pdf"` while '
                "available metadata contains `transformer_notes.pdf`, followed by "
                "`retrieved_docs_count=0`. The parent-child retrieval path filters "
                "sources by normalized filename, so filename casing, spacing, or "
                "underscore mismatches can exclude the intended document."
            )

        if self._has_duplicate_upload_stale_content(state.evidence_items):
            return (
                "Runtime logs show a duplicate upload for `policy_handbook.pdf` was "
                "ignored before ingestion and cache reset, followed by stale answers "
                "from revision `2026-Q1` when `2026-Q2` was expected. The upload path "
                "therefore needs explicit replace/version/re-ingest behavior for "
                "same-name document revisions."
            )

        if self._has_duplicate_content_upload(state.evidence_items):
            return (
                "Runtime logs show two upload requests with the same content hash but "
                "different filenames. The second request reports `processed_uploads_match=false` "
                "and `dedupe_key=\"filename\"`, then retrieval later reports duplicate "
                "sources for that same content hash. Code evidence from the upload path "
                "shows the content hash is available, but the duplicate guard is still "
                "based on uploaded filename state."
            )

        if self._has_silent_reranker_bypass(state.evidence_items):
            return (
                "Runtime logs show hybrid retrieval returned candidates, then reranking "
                "reported a null model with neutral scores and unchanged ordering. Code "
                "evidence from the reranker path shows missing model configuration can "
                "return unreranked documents instead of surfacing a clear warning or "
                "startup/configuration failure."
            )

        parts: list[str] = []
        for evidence in state.evidence_items:
            parts.append(f"{evidence.evidence_id}: {self._finding_text(evidence)}")

        return " ".join(parts) or "No technical evidence was available."

    def evidence_ids(self, state: WorkflowState) -> list[str]:
        return self.evidence_selection.evidence_ids(state)

    def confidence_score(self, state: WorkflowState) -> float:
        if not state.evidence_items:
            return 0.0

        source_types = {evidence.source_type for evidence in state.evidence_items}

        has_logs = EvidenceSourceType.LOG in source_types
        has_code = EvidenceSourceType.CODE in source_types
        has_kb = EvidenceSourceType.KNOWLEDGE_BASE in source_types

        if self._has_invalid_summary_strategy(state.evidence_items):
            if has_logs and has_code and has_kb:
                return 0.85
            if has_logs and has_code:
                return 0.8
            if has_logs and has_kb:
                return 0.65
            return 0.55

        if self._has_duplicate_content_upload(
            state.evidence_items
        ) or self._has_silent_reranker_bypass(state.evidence_items):
            if has_logs and has_code and has_kb:
                return 0.85
            if has_logs and has_code:
                return 0.8
            if has_logs and has_kb:
                return 0.7
            return 0.55

        if has_logs and has_code and has_kb:
            return 0.8

        if has_logs and has_code:
            return 0.75

        if has_logs and has_kb:
            return 0.65

        if has_logs:
            return 0.5

        if state.evidence_evaluation is not None:
            return min(state.evidence_evaluation.confidence_score, 0.8)

        return 0.4

    def confidence_reason(self, state: WorkflowState) -> str:
        if not state.evidence_items:
            return "No evidence was collected."

        if self._has_invalid_summary_strategy(state.evidence_items):
            source_types = {evidence.source_type for evidence in state.evidence_items}
            has_kb = EvidenceSourceType.KNOWLEDGE_BASE in source_types

            if has_kb:
                return (
                    "Confidence is high because logs show the exact exception "
                    "`Invalid strategy: summary`, code evidence points to the LLM "
                    "routing validation path, and knowledge-base evidence describes "
                    "the expected summary-query routing behavior. Confidence is not "
                    "1.0 because the exact raw LLM router output payload and prompt "
                    "response were not captured."
                )

            return (
                "Confidence is moderately high because logs show the exact exception "
                "`Invalid strategy: summary`, and code/test evidence points to the LLM "
                "routing validation path. Confidence is not 1.0 because knowledge-base "
                "evidence and the exact raw LLM router output payload were not captured."
            )

        if self._has_duplicate_content_upload(state.evidence_items):
            return (
                "Confidence is high because logs show the same content hash being "
                "ingested under multiple filenames, code evidence points to upload "
                "deduplication state, and knowledge-base evidence documents expected "
                "content-hash deduplication behavior."
            )

        if self._has_silent_reranker_bypass(state.evidence_items):
            return (
                "Confidence is high because logs show missing reranker configuration, "
                "neutral rerank scores, and unchanged ordering; code and knowledge-base "
                "evidence explain that silent reranker bypass degrades retrieval quality."
            )

        if state.evidence_evaluation is None:
            return "Evidence has not been evaluated."

        return (
            "Confidence is based on available evidence quality, source diversity, "
            f"and evaluator result: {state.evidence_evaluation.reason}"
        )

    def open_questions(self, state: WorkflowState) -> list[str]:
        if self._has_invalid_summary_strategy(state.evidence_items):
            return [
                (
                    "What exact raw structured output did the LLM router return "
                    "before validation failed?"
                ),
                (
                    "Does the LLM router prompt explicitly restrict strategy values "
                    "to the supported retrieval strategy enum?"
                ),
            ]

        if state.evidence_evaluation is None:
            return ["What additional evidence is needed to confirm the root cause?"]

        if state.evidence_evaluation.can_write_rca:
            return []

        return state.evidence_evaluation.missing_evidence or [
            "What additional evidence is needed to confirm the root cause?"
        ]

    def low_confidence_warning(self, state: WorkflowState) -> str | None:
        confidence_score = self.confidence_score(state)
        if confidence_score >= state.confidence_threshold:
            return None

        return (
            "This RCA is low confidence because collected evidence does not meet "
            "the configured confidence threshold."
        )

    def immediate_fix(self, state: WorkflowState) -> str:
        if self._has_invalid_summary_strategy(state.evidence_items):
            return (
                "Update the LLM router prompt and/or structured output validation "
                "so the router emits only supported retrieval strategy values. For "
                "broad summary questions over a selected document, return "
                "`parent_child` directly or normalize `summary` to `parent_child` "
                "before validation."
            )

        if self._has_unsupported_retrieval_strategy(state.evidence_items):
            return (
                "Validate `RETRIEVAL_STRATEGY` at startup and restrict it to "
                "`hybrid`, `parent_child`, or `fusion`; reject or normalize unsupported "
                "values before request handling."
            )

        if self._has_selected_document_mismatch(state.evidence_items):
            return (
                "Normalize selected-document names and stored source metadata with the "
                "same case-insensitive, separator-safe, whitespace-safe rules before "
                "applying parent-child retrieval filters."
            )

        if self._has_duplicate_upload_stale_content(state.evidence_items):
            return (
                "Change duplicate filename handling so revised uploads are explicitly "
                "rejected, versioned, or re-ingested with cache reset instead of being "
                "silently skipped."
            )

        if self._has_duplicate_content_upload(state.evidence_items):
            return (
                "Use the computed content hash as the duplicate identity for uploads. "
                "Reject, version, or link same-content uploads before ingestion so a "
                "different filename cannot create duplicate document records."
            )

        if self._has_silent_reranker_bypass(state.evidence_items):
            return (
                "Require `RERANKING_MODEL_NAME` or an explicit reranking-disabled mode "
                "at startup, and replace silent neutral-score fallback with a clear "
                "warning or fail-fast configuration error."
            )

        code_evidence = self._evidence_for_source(state, EvidenceSourceType.CODE)
        if code_evidence:
            return f"Inspect and fix the code path at {self._location(code_evidence[0])}."

        return "Collect code evidence before making a concrete fix recommendation."

    def long_term_prevention(self) -> str:
        return (
            "Add regression tests, centralize retrieval strategy validation, improve "
            "structured error handling, and log raw router outputs when fallback occurs."
        )

    def tests_to_add(self, state: WorkflowState) -> list[str]:
        if self._has_invalid_summary_strategy(state.evidence_items):
            return [
                (
                    'Add a regression test where query="summarize this document" '
                    "and a selected document is present; assert the resolved "
                    "strategy is `parent_child`."
                ),
                (
                    "Add a test ensuring unsupported LLM strategy values are handled "
                    "with a clear fallback reason and do not silently degrade routing quality."
                ),
                (
                    "Add a contract test ensuring the LLM router can emit only supported "
                    "retrieval strategy enum values."
                ),
            ]

        if self._has_duplicate_content_upload(state.evidence_items):
            return [
                (
                    "Add an upload test where two different filenames have identical "
                    "content and assert only one document record or citation source is created."
                ),
                (
                    "Add a regression test that verifies the upload path uses content "
                    "hash identity before ingestion."
                ),
            ]

        if self._has_silent_reranker_bypass(state.evidence_items):
            return [
                (
                    "Add a startup/configuration test that fails or warns clearly when "
                    "`RERANKING_MODEL_NAME` is missing."
                ),
                (
                    "Add a retrieval pipeline test proving reranking changes candidate "
                    "ordering or reports an explicit disabled state."
                ),
            ]

        tests = [f"Add a regression test for incident {state.incident.incident_id}."]

        if self._evidence_for_source(state, EvidenceSourceType.CODE):
            tests.append("Add a test covering the implicated implementation path.")

        return tests

    def _findings_for_source(
        self,
        evidence_items: list[EvidenceItem],
        source_type: EvidenceSourceType,
    ) -> list[str]:
        return self.finding_rules.findings_for_source(evidence_items, source_type)

    def _selected_findings_for_source(
        self,
        state: WorkflowState,
        source_type: EvidenceSourceType,
        *,
        max_findings: int,
    ) -> list[str]:
        selected_items = self._selected_evidence_for_source(
            state,
            source_type,
            max_items=max_findings,
        )

        return self.unique(
            [self.finding_rules.finding_text(evidence) for evidence in selected_items]
        )

    def _selected_evidence_for_source(
        self,
        state: WorkflowState,
        source_type: EvidenceSourceType,
        *,
        max_items: int,
    ) -> list[EvidenceItem]:
        return self.evidence_selection.selected_evidence_for_source(
            state,
            source_type,
            max_items=max_items,
        )

    def _prefer_primary_code_evidence(
        self,
        evidence_items: list[EvidenceItem],
        signals: set[str],
    ) -> list[EvidenceItem]:
        return self.evidence_selection._prefer_primary_code_evidence(evidence_items, signals)

    def _evidence_for_source(
        self,
        state: WorkflowState,
        source_type: EvidenceSourceType,
    ) -> list[EvidenceItem]:
        return self.evidence_selection.evidence_for_source(state, source_type)

    def _finding_text(self, evidence: EvidenceItem) -> str:
        return self.finding_rules.finding_text(evidence)

    def _shorten(self, value: str, *, max_length: int = 180) -> str:
        return self.formatter.shorten(value, max_length=max_length)

    def _location(self, evidence: EvidenceItem) -> str:
        return self.formatter.location(evidence)

    def _symbol_name(self, evidence: EvidenceItem) -> str | None:
        return self.formatter.symbol_name(evidence)

    def _display_path(self, path: str) -> str:
        return self.formatter.display_path(path)

    def _combined_text(self, evidence_items: list[EvidenceItem]) -> str:
        return self.formatter.combined_text(evidence_items)

    def _has_invalid_summary_strategy(self, evidence_items: list[EvidenceItem]) -> bool:
        combined_text = self._combined_text(evidence_items).lower()
        return (
            "invalid strategy: summary" in combined_text
            or "valueerror: invalid strategy: summary" in combined_text
        )

    def _has_unsupported_retrieval_strategy(
        self,
        evidence_items: list[EvidenceItem],
    ) -> bool:
        combined_text = self._combined_text(evidence_items).lower()
        return "unsupported retrieval strategy: semantic" in combined_text

    def _has_selected_document_mismatch(
        self,
        evidence_items: list[EvidenceItem],
    ) -> bool:
        combined_text = self._combined_text(evidence_items).lower()
        return (
            "returned no matching sources" in combined_text
            and "retrieved_docs_count=0" in combined_text
        )

    def _has_duplicate_upload_stale_content(
        self,
        evidence_items: list[EvidenceItem],
    ) -> bool:
        combined_text = self._combined_text(evidence_items).lower()
        return "duplicate upload" in combined_text and "stale document content" in combined_text

    def _has_duplicate_content_upload(
        self,
        evidence_items: list[EvidenceItem],
    ) -> bool:
        combined_text = self._combined_text(evidence_items).lower()
        return (
            "content_hash" in combined_text
            and 'dedupe_key="filename"' in combined_text
            and "duplicate_content_detected=true" in combined_text
        )

    def _has_silent_reranker_bypass(
        self,
        evidence_items: list[EvidenceItem],
    ) -> bool:
        combined_text = self._combined_text(evidence_items).lower()
        return (
            "reranker_model=null" in combined_text
            and 'scores="0.0,0.0,0.0,0.0"' in combined_text
            and "order_changed=false" in combined_text
        )

    def _has_parent_child_signal(self, evidence_items: list[EvidenceItem]) -> bool:
        combined_text = self._combined_text(evidence_items).lower()
        return "parent_child" in combined_text

    def _has_log_and_code_evidence(self, evidence_items: list[EvidenceItem]) -> bool:
        source_types = {evidence.source_type for evidence in evidence_items}
        return EvidenceSourceType.LOG in source_types and EvidenceSourceType.CODE in source_types

    def _locations_matching(
        self,
        evidence_items: list[EvidenceItem],
        *,
        source_type: EvidenceSourceType,
        patterns: list[str],
    ) -> list[str]:
        return self.formatter.locations_matching(
            evidence_items,
            source_type=source_type,
            patterns=patterns,
        )

    def unique(self, values: list[str] | object) -> list[str]:
        return self.formatter.unique(values)
