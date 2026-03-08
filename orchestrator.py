"""
orchestrator.py – Multi-agent pipeline coordinator.

Runs the 5-agent pipeline sequentially:
  Discovery → Reviewer → Methodology → Citation → Writing

Handles:
  - Session lifecycle (create → update → complete)
  - Error recovery (fallback outputs when an agent fails)
  - Live progress callbacks for the Streamlit UI
  - Final metric aggregation
"""

import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger("ai-coauthor.orchestrator")


class ResearchPipeline:
    """
    Orchestrates the end-to-end research paper generation pipeline.
    
    Usage (blocking):
        pipeline = ResearchPipeline()
        result = pipeline.run(topic="AI drug discovery", max_papers=10)
    
    Usage (with live updates):
        def on_progress(step, detail):
            print(f"[{step}] {detail}")
        result = pipeline.run(topic="...", progress_callback=on_progress)
    """

    def __init__(self, progress_callback: Optional[Callable[[str, str], None]] = None):
        self._progress = progress_callback or (lambda step, detail="": None)
        from memory.session_manager import SessionManager
        self.session_manager = SessionManager()

    # ─────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────

    def run(
        self,
        topic: str,
        max_papers: int = 10,
        output_format: str = "IEEE",
        uploaded_papers: list[dict] | None = None,
        username: str = "anonymous",
    ) -> dict[str, Any]:
        """
        Execute the full multi-agent pipeline.

        Parameters
        ----------
        uploaded_papers : list[dict], optional
            Pre-parsed paper dicts from user-uploaded PDFs/TXTs.
        username : str
            Account username — stored on the session record.

        Returns a dict containing all agent outputs plus top-level metadata.
        """
        start_time = time.monotonic()
        session_id = self.session_manager.create_session(
            topic=topic,
            output_format=output_format,
            max_papers=max_papers,
            username=username,
        )
        self._emit("🚀 Pipeline started", f"Session: {session_id[:8]}…")

        context: dict[str, Any] = {
            "topic": topic,
            "max_papers": max_papers,
            "output_format": output_format,
            "session_id": session_id,
            "uploaded_papers": uploaded_papers or [],
        }

        pipeline_steps = [
            ("discovery",    self._run_discovery),
            ("reviewer",     self._run_reviewer),
            ("methodology",  self._run_methodology),
            ("citation",     self._run_citation),
            ("writing",      self._run_writing),
        ]

        agent_errors: list[dict] = []

        for step_name, step_fn in pipeline_steps:
            self.session_manager.update_session(session_id, f"running_{step_name}")
            result = step_fn(context)

            self.session_manager.update_session(
                session_id,
                status="success" if result.success else "failed",
                agent_name=step_name,
                outputs=result.outputs,
                latency_ms=result.latency_ms,
            )

            if result.success:
                context.update(result.outputs)
            else:
                err_msg = result.error or "Unknown error"
                logger.error("Step %s failed: %s", step_name, err_msg)
                # Surface the error to the live UI progress feed
                self._emit(
                    f"❌ {step_name.capitalize()} agent failed",
                    err_msg[:120],
                )
                agent_errors.append({"agent": step_name, "error": err_msg})

            # After discovery: bail out early if there are no papers at all
            if step_name == "discovery" and not context.get("papers"):
                self._emit(
                    "⚠️ No papers found",
                    "Try a broader or different research topic."
                )
                break

        context["agent_errors"] = agent_errors

        # ── Final metrics ────────────────────────────────────────────
        total_time_s = round(time.monotonic() - start_time, 1)
        citation_stats = context.get("citation_stats", {})
        metrics = {
            "total_time_seconds": total_time_s,
            "papers_retrieved": len(context.get("papers", [])),
            "papers_summarised": len(context.get("summaries", [])),
            "uploaded_papers_count": len(context.get("uploaded_papers", [])),
            "citations_verified": citation_stats.get("verified", 0),
            "hallucination_rate_pct": citation_stats.get("hallucination_rate_pct", 0.0),
            "word_count": context.get("word_count", 0),
            "output_format": output_format,
            "session_id": session_id,
            "s3_draft_url": context.get("s3_draft_url"),
            "s3_bibtex_url": context.get("s3_bibtex_url"),
        }

        self.session_manager.complete_session(session_id, metrics)
        self._emit("🎉 Pipeline complete", f"Draft ready in {total_time_s}s")

        context["metrics"] = metrics
        return context

    # ─────────────────────────────────────────────────────────────────
    # Step wrappers (inject progress_callback into each agent)
    # ─────────────────────────────────────────────────────────────────

    def _make_agent(self, AgentClass, session_id: str):
        from agents.base_agent import AgentResult
        return AgentClass(session_id=session_id, progress_callback=self._progress)

    def _run_discovery(self, ctx: dict):
        from agents.discovery_agent import DiscoveryAgent
        agent = self._make_agent(DiscoveryAgent, ctx["session_id"])
        result = agent.execute({"topic": ctx["topic"], "max_papers": ctx["max_papers"]})

        # Merge uploaded papers BEFORE discovered ones so they are prioritised
        # in the RAG index and literature review.
        if result.success and ctx.get("uploaded_papers"):
            uploaded = ctx["uploaded_papers"]
            discovered = result.outputs.get("papers", [])
            # Deduplicate by title to avoid double-counting
            existing_titles = {p.get("title", "").lower() for p in uploaded}
            deduped_discovered = [
                p for p in discovered
                if p.get("title", "").lower() not in existing_titles
            ]
            merged = uploaded + deduped_discovered
            result.outputs["papers"] = merged
            up_count = len(uploaded)
            self._emit(
                "📎 Merged uploaded papers",
                f"{up_count} uploaded + {len(deduped_discovered)} discovered = {len(merged)} total"
            )

        return result

    def _run_reviewer(self, ctx: dict):
        from agents.reviewer_agent import ReviewerAgent
        agent = self._make_agent(ReviewerAgent, ctx["session_id"])
        return agent.execute({"topic": ctx["topic"], "papers": ctx.get("papers", [])})

    def _run_methodology(self, ctx: dict):
        from agents.methodology_agent import MethodologyAgent
        agent = self._make_agent(MethodologyAgent, ctx["session_id"])
        return agent.execute({
            "topic": ctx["topic"],
            "summaries": ctx.get("summaries", []),
            "gaps": ctx.get("gaps", ""),
            "related_work_section": ctx.get("related_work_section", ""),
        })

    def _run_citation(self, ctx: dict):
        from agents.citation_agent import CitationAgent
        agent = self._make_agent(CitationAgent, ctx["session_id"])
        return agent.execute({
            "papers": ctx.get("papers", []),
            "summaries": ctx.get("summaries", []),
            "output_format": ctx.get("output_format", "IEEE"),
        })

    def _run_writing(self, ctx: dict):
        from agents.writing_agent import WritingAgent
        agent = self._make_agent(WritingAgent, ctx["session_id"])
        return agent.execute({
            "topic": ctx["topic"],
            "related_work_section": ctx.get("related_work_section", ""),
            "methodology_section": ctx.get("methodology_section", ""),
            "gaps": ctx.get("gaps", ""),
            "summaries": ctx.get("summaries", []),
            "ieee_references": ctx.get("ieee_references", []),
            "bibtex": ctx.get("bibtex", ""),
        })

    def _emit(self, step: str, detail: str = ""):
        self._progress(step, detail)
