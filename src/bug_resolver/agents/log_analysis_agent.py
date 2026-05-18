from __future__ import annotations

from bug_resolver.agents.base import BaseAgent
from bug_resolver.rules.log_analysis_rules import LogAnalysisRules
from bug_resolver.schemas import LogAnalysisResult, LogEntry


class LogAnalysisAgent(BaseAgent[list[LogEntry], LogAnalysisResult]):
    """
    Coordinates log analysis.

    The agent owns the workflow:
    - validate logs
    - call deterministic log analysis rules
    - assemble LogAnalysisResult

    Parsing/extraction rules live in LogAnalysisRules.
    """

    name = "log_analysis_agent"

    def __init__(self, rules: LogAnalysisRules | None = None) -> None:
        self._rules = rules or LogAnalysisRules()

    async def _run(self, input_data: list[LogEntry]) -> LogAnalysisResult:
        stack_trace = self._rules.extract_stack_trace(input_data)
        exception_type, exception_message = self._rules.extract_exception(input_data)
        request_ids = self._rules.extract_request_ids(input_data)
        trace_ids = self._rules.extract_trace_ids(input_data)
        evidence_items = self._rules.build_evidence_items(input_data)

        suspected_file_paths = self._rules.unique(
            frame.file_path for frame in stack_trace if frame.file_path
        )
        suspected_function_names = self._rules.unique(
            frame.function_name for frame in stack_trace if frame.function_name
        )

        likely_failure_point = self._rules.build_likely_failure_point(stack_trace)
        summary = self._rules.build_summary(
            exception_type=exception_type,
            exception_message=exception_message,
            likely_failure_point=likely_failure_point,
            log_count=len(input_data),
        )

        return LogAnalysisResult(
            summary=summary,
            exception_type=exception_type,
            exception_message=exception_message,
            stack_trace=stack_trace,
            suspected_file_paths=suspected_file_paths,
            suspected_function_names=suspected_function_names,
            request_ids=request_ids,
            trace_ids=trace_ids,
            likely_failure_point=likely_failure_point,
            evidence_items=evidence_items,
        )

    def _validate_input(self, input_data: list[LogEntry]) -> None:
        super()._validate_input(input_data)

        if not input_data:
            raise ValueError(f"{self.name} received no logs to analyze.")