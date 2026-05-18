from __future__ import annotations

from bug_resolver.schemas import Incident, LogAnalysisResult


class ContextPlanningRules:
    """
    Deterministic rules for generating code and knowledge-base search queries.

    This keeps business/search-planning logic outside the agent.
    The agent coordinates; rules decide what useful context should be searched.
    """

    def build_code_search_queries(
        self,
        incident: Incident,
        log_analysis: LogAnalysisResult,
    ) -> list[str]:
        queries: list[str] = []

        queries.extend(self._incident_queries(incident))

        if log_analysis.exception_type:
            queries.append(log_analysis.exception_type)

        if log_analysis.exception_message:
            queries.append(log_analysis.exception_message)

        if log_analysis.likely_failure_point:
            queries.append(log_analysis.likely_failure_point)

        queries.extend(log_analysis.suspected_file_paths)
        queries.extend(log_analysis.suspected_function_names)

        for file_path, function_name in zip(
            log_analysis.suspected_file_paths,
            log_analysis.suspected_function_names,
            strict=False,
        ):
            queries.append(f"{file_path} {function_name}")

        return self.unique(queries)

    def build_knowledge_search_queries(
        self,
        incident: Incident,
        log_analysis: LogAnalysisResult,
    ) -> list[str]:
        queries: list[str] = []

        queries.extend(self._incident_queries(incident))

        if incident.affected_service:
            queries.append(incident.affected_service)

        if incident.affected_area:
            queries.append(incident.affected_area)

        if log_analysis.exception_type:
            queries.append(f"{log_analysis.exception_type} troubleshooting")

        if log_analysis.exception_message:
            queries.append(f"{log_analysis.exception_message} expected behavior")

        return self.unique(queries)

    def files_to_prioritize(self, log_analysis: LogAnalysisResult) -> list[str]:
        return self.unique(log_analysis.suspected_file_paths)

    def functions_to_prioritize(self, log_analysis: LogAnalysisResult) -> list[str]:
        return self.unique(log_analysis.suspected_function_names)

    def build_missing_evidence_hints(
        self,
        incident: Incident,
        log_analysis: LogAnalysisResult,
    ) -> list[str]:
        hints: list[str] = []

        if not log_analysis.exception_type:
            hints.append("No exception type was found in logs.")

        if not log_analysis.exception_message:
            hints.append("No exception message was found in logs.")

        if not log_analysis.stack_trace:
            hints.append("No stack trace frames were found in logs.")

        if not log_analysis.suspected_file_paths:
            hints.append("No suspected source files were identified from logs.")

        if not log_analysis.suspected_function_names:
            hints.append("No suspected function names were identified from logs.")

        if not incident.affected_area:
            hints.append("Incident affected area was not provided.")

        return hints

    def build_generated_from(
        self,
        incident: Incident,
        log_analysis: LogAnalysisResult,
    ) -> str:
        signals: list[str] = ["incident"]

        if log_analysis.exception_type or log_analysis.exception_message:
            signals.append("exception")

        if log_analysis.stack_trace:
            signals.append("stack_trace")

        if log_analysis.suspected_file_paths:
            signals.append("suspected_files")

        if log_analysis.suspected_function_names:
            signals.append("suspected_functions")

        return "+".join(signals)

    def _incident_queries(self, incident: Incident) -> list[str]:
        queries = [
            incident.title,
            incident.description,
        ]

        if incident.affected_service:
            queries.append(incident.affected_service)

        if incident.affected_area:
            queries.append(incident.affected_area)

        return self.unique(queries)

    def unique(self, values: list[str] | object) -> list[str]:
        unique_values: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not isinstance(value, str):
                continue

            normalized = value.strip()
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            unique_values.append(normalized)

        return unique_values