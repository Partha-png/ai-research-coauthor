"""
agents/reviewer_agent.py – Literature Review Agent.

Summarises each paper with the configured LLM, identifies themes,
gaps and quality scores using Retrieval-Augmented Generation.

Resilience: per-paper LLM failures fall back to the abstract —
the whole step never fails because one paper failed.
"""

import logging
from typing import Any

from agents.base_agent import BaseAgent
from tools.rag_engine import RAGEngine
from prompts import (
    PAPER_SUMMARY_SYSTEM,
    PAPER_SUMMARY_TEMPLATE,
    GAP_ANALYSIS_TEMPLATE,
    RELATED_WORK_TEMPLATE,
)

logger = logging.getLogger("ai-coauthor.reviewer")

MAX_PAPERS_TO_SUMMARISE = 7  # cap to avoid long hangs / cost blowout


class ReviewerAgent(BaseAgent):
    """
    Agent 2 – Generates literature summaries and identifies research gaps.

    Inputs:
        topic (str): Research topic
        papers (list[dict]): Papers from DiscoveryAgent

    Outputs:
        summaries (list[dict]): Per-paper summaries
        gaps (str): Research gap analysis
        related_work_section (str): Formatted Related Work section
        rag_engine (RAGEngine): Indexed engine for downstream agents
    """

    name = "reviewer"

    def _run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        from config import invoke_claude, MAX_TOKENS_SUMMARY

        topic: str = inputs["topic"]
        papers: list[dict] = inputs.get("papers", [])

        if not papers:
            return {
                "summaries": [],
                "gaps": "No papers available for analysis.",
                "related_work_section": "Literature review could not be completed.",
                "rag_engine": None,
            }

        # ── Step 1: Build RAG index ─────────────────────────────────────
        self._emit("🧠 Building knowledge index", f"Indexing {len(papers)} papers")
        rag = RAGEngine()
        rag.index_papers(papers)

        # ── Step 2: Summarise papers (capped, with per-paper fallback) ──
        papers_to_summarise = papers[:MAX_PAPERS_TO_SUMMARISE]
        summaries: list[dict] = []
        failed = 0

        for i, paper in enumerate(papers_to_summarise):
            self._emit(
                "📝 Summarising papers",
                f"Paper {i+1}/{len(papers_to_summarise)}: {paper.get('title', 'Unknown')[:55]}…",
            )
            # Use full text if we have it, fall back to abstract
            text_to_summarise = (paper.get("full_text") or paper.get("abstract", ""))[:1500]

            try:
                prompt = PAPER_SUMMARY_TEMPLATE.format(
                    title=paper.get("title", "Unknown"),
                    authors=", ".join(paper.get("authors", ["Unknown"])),
                    year=paper.get("year", "?"),
                    source=paper.get("source", ""),
                    abstract=text_to_summarise,
                )
                summary_text = invoke_claude(
                    prompt,
                    system=PAPER_SUMMARY_SYSTEM,
                    max_tokens=MAX_TOKENS_SUMMARY,
                )
            except Exception as exc:
                # Fallback: use the abstract directly so the pipeline continues
                logger.warning(
                    "LLM summarisation failed for '%s': %s — using abstract as fallback",
                    paper.get("title", "?"),
                    exc,
                )
                summary_text = text_to_summarise or "Summary unavailable."
                failed += 1

            summaries.append({
                "paper_id": paper.get("id", ""),
                "title": paper.get("title", ""),
                "authors": paper.get("authors", []),
                "year": paper.get("year", ""),
                "arxiv_id": paper.get("arxiv_id", ""),
                "doi": paper.get("doi", ""),
                "summary": summary_text,
                "citation_count": paper.get("citation_count", 0),
            })

        if failed:
            self._emit(
                "⚠️ Some summaries used fallback",
                f"{failed}/{len(papers_to_summarise)} papers used abstract text (LLM call failed)",
            )

        # ── Step 3: Gap analysis ────────────────────────────────────────
        self._emit("🔭 Analysing research gaps", "")
        summaries_text = "\n\n".join(
            f"**[{s['title']} ({s['year']})]** – {s['summary']}"
            for s in summaries
        )

        try:
            gaps = invoke_claude(
                GAP_ANALYSIS_TEMPLATE.format(topic=topic, summaries=summaries_text[:4000]),
                max_tokens=800,
            )
        except Exception as exc:
            logger.warning("Gap analysis failed: %s", exc)
            gaps = f"Gap analysis could not be completed automatically. Review the {len(summaries)} summarised papers for opportunities."

        # ── Step 4: Write Related Work section ──────────────────────────
        self._emit("✍️ Writing Related Work section", "")
        try:
            related_work = invoke_claude(
                RELATED_WORK_TEMPLATE.format(
                    topic=topic,
                    summaries=summaries_text[:5000],
                ),
                max_tokens=1200,
            )
        except Exception as exc:
            logger.warning("Related work section failed: %s", exc)
            related_work = summaries_text[:3000]  # Use raw summaries as fallback

        self._emit("✅ Review complete", f"Summarised {len(summaries)} papers")
        return {
            "summaries": summaries,
            "gaps": gaps,
            "related_work_section": related_work,
            "rag_engine": rag,
        }
