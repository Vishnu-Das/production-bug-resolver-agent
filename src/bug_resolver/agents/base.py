"""Define the common template contract shared by all workflow agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from bug_resolver.utils.observability import get_logger, log_debug_payload, traceable


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")
logger = get_logger(__name__)


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """
    Base class for all agents.

    This gives every agent the same execution shape:

    public run()
        -> validate input
        -> execute agent-specific logic
        -> validate output
        -> return structured result

    Individual agents only implement _run().
    """

    name: str = "base_agent"

    @traceable(name="agent.run", run_type="chain")
    async def run(self, input_data: InputT) -> OutputT:
        logger.info("agent started agent=%s", self.name)
        log_debug_payload(
            logger,
            f"agent input agent={self.name}",
            payload=input_data,
        )
        self._validate_input(input_data)
        try:
            output = await self._run(input_data)
            self._validate_output(output)
        except Exception:
            logger.exception("agent failed agent=%s", self.name)
            raise

        logger.info("agent finished agent=%s output_type=%s", self.name, type(output).__name__)
        log_debug_payload(
            logger,
            f"agent output agent={self.name}",
            payload=output,
        )
        return output

    def _validate_input(self, input_data: InputT) -> None:
        if input_data is None:
            raise ValueError(f"{self.name} received empty input.")

    def _validate_output(self, output: OutputT) -> None:
        if output is None:
            raise ValueError(f"{self.name} produced empty output.")

    @abstractmethod
    async def _run(self, input_data: InputT) -> OutputT:
        """Execute the agent-specific logic."""
        raise NotImplementedError
