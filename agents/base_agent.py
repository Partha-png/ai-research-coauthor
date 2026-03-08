"""
agents/base_agent.py – Abstract base class for all research agents.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("ai-coauthor.agent")


class AgentResult:
    """Structured output from an agent execution."""

    def __init__(
        self,
        agent_name: str,
        outputs: dict[str, Any],
        latency_ms: int,
        success: bool = True,
        error: str = "",
    ):
        self.agent_name = agent_name
        self.outputs = outputs
        self.latency_ms = latency_ms
        self.success = success
        self.error = error

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "error": self.error,
            **self.outputs,
        }


class BaseAgent(ABC):
    """
    Abstract base class for all research pipeline agents.
    
    Every concrete agent must implement `_run(inputs)`.
    The public `execute(inputs)` method wraps it with timing,
    error handling, and structured result packaging.
    """

    name: str = "base"

    def __init__(self, session_id: str = "", progress_callback=None):
        """
        Parameters
        ----------
        session_id : str
            Active research session ID (for logging / storage).
        progress_callback : callable, optional
            Called with (step: str, detail: str) for live UI updates.
        """
        self.session_id = session_id
        self._progress = progress_callback or (lambda step, detail="": None)
        self._logger = logging.getLogger(f"ai-coauthor.{self.name}")

    def execute(self, inputs: dict[str, Any]) -> AgentResult:
        """Public entry point – wraps _run with timing and error handling."""
        self._logger.info("[%s] Starting | session=%s", self.name, self.session_id)
        start = time.monotonic()
        try:
            outputs = self._run(inputs)
            latency_ms = int((time.monotonic() - start) * 1000)
            self._logger.info(
                "[%s] Completed in %.1fs | session=%s",
                self.name, latency_ms / 1000, self.session_id
            )
            return AgentResult(
                agent_name=self.name,
                outputs=outputs,
                latency_ms=latency_ms,
                success=True,
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            self._logger.error("[%s] Failed: %s", self.name, exc, exc_info=True)
            return AgentResult(
                agent_name=self.name,
                outputs={},
                latency_ms=latency_ms,
                success=False,
                error=str(exc),
            )

    @abstractmethod
    def _run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Agent-specific logic. Must return a dict of outputs."""
        ...

    def _emit(self, step: str, detail: str = ""):
        """Emit a progress update to the UI callback."""
        self._progress(step, detail)
