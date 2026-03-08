"""
agents/methodology_agent.py – Proposes novel research methodology.
Uses the Related Work + identified gaps to suggest a coherent
experimental design, datasets, metrics, and contributions.

Resilience: if the LLM fails, returns a structured placeholder so the
writing agent can still produce a complete draft.
"""

import logging
from typing import Any

from agents.base_agent import BaseAgent
from prompts import METHODOLOGY_TEMPLATE, METHODOLOGY_SYSTEM

logger = logging.getLogger("ai-coauthor.methodology")


class MethodologyAgent(BaseAgent):
    """
    Agent 3 – Generates the Methodology section.

    Inputs:
        topic (str): Research topic
        summaries (list[dict]): Paper summaries from ReviewerAgent
        gaps (str): Research gaps from ReviewerAgent
        related_work_section (str): Related Work draft

    Outputs:
        methodology_section (str): Draft Methodology section
    """

    name = "methodology"

    def _run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        from config import invoke_claude, MAX_TOKENS_SECTION

        topic: str = inputs["topic"]
        summaries: list[dict] = inputs.get("summaries", [])
        gaps: str = inputs.get("gaps", "")
        related_work: str = inputs.get("related_work_section", "")

        # Compact summaries text for the prompt
        summaries_text = "\n\n".join(
            f"• [{s['title']} ({s['year']})] – {s['summary']}"
            for s in summaries[:8]
        )

        self._emit("⚗️ Designing methodology", "")
        try:
            methodology = invoke_claude(
                METHODOLOGY_TEMPLATE.format(
                    topic=topic,
                    related_work=related_work[:2000] if related_work else summaries_text[:2000],
                    gaps=gaps[:1000],
                ),
                system=METHODOLOGY_SYSTEM,
                max_tokens=MAX_TOKENS_SECTION,
                temperature=0.25,
            )
        except Exception as exc:
            logger.warning("Methodology generation failed: %s — using placeholder", exc)
            methodology = (
                f"## Proposed Methodology for: {topic}\n\n"
                "*(This section was auto-generated as a placeholder due to a temporary error.)*\n\n"
                "### 3.1 Overview\n"
                f"This study proposes a systematic approach to address the identified gaps in {topic}.\n\n"
                "### 3.2 Data Collection\n"
                "Relevant datasets will be identified from public repositories and the discovered literature.\n\n"
                "### 3.3 Evaluation\n"
                "Standard benchmarks and ablation studies will be used to measure performance.\n\n"
                f"**Identified gaps to address:** {gaps[:300] if gaps else 'See Related Work section.'}"
            )

        self._emit("✅ Methodology drafted", "")
        return {"methodology_section": methodology}
