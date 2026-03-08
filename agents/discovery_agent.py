"""
agents/discovery_agent.py – Paper discovery via arXiv + Semantic Scholar.
Uses LLM to expand the research query into multiple search queries,
then retrieves and deduplicates papers.
"""

import json
import logging
from typing import Any

from agents.base_agent import BaseAgent
from tools.arxiv_search import search_papers
from tools.pdf_parser import parse_paper_pdf
from prompts import QUERY_EXPANSION_TEMPLATE

logger = logging.getLogger("ai-coauthor.discovery")


class DiscoveryAgent(BaseAgent):
    """
    Agent 1 – Discovers relevant academic papers.
    
    Inputs:
        topic (str): Research topic or question
        max_papers (int): Max papers to retrieve
        
    Outputs:
        papers (list[dict]): Enriched paper records
        queries_used (list[str]): Queries that were executed
    """

    name = "discovery"

    def _run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        from config import invoke_claude, MAX_PAPERS

        topic: str = inputs["topic"]
        max_papers: int = inputs.get("max_papers", MAX_PAPERS)

        # ── Step 1: Expand query ────────────────────────────────────────
        self._emit("🔍 Generating search queries", f"Topic: {topic[:80]}")
        extra_queries = self._expand_queries(topic, invoke_claude)

        # ── Step 2: Search both sources ─────────────────────────────────
        self._emit("📡 Searching arXiv + Semantic Scholar", f"~{max_papers} papers")
        papers = search_papers(
            query=topic,
            max_total=max_papers,
            extra_queries=extra_queries[:2],
        )

        if not papers:
            self._emit("⚠️ No papers found", "Try a broader topic")
            return {"papers": [], "queries_used": [topic] + extra_queries}

        # ── Step 3: Optional PDF parsing (best-effort, time-capped) ─────
        self._emit("📄 Parsing PDFs", f"Extracting full text from top papers")
        for i, paper in enumerate(papers[:5]):  # only top-5 to save time
            self._emit("📄 Parsing PDF", f"{i+1}/5: {paper['title'][:60]}")
            full_text = parse_paper_pdf(paper, max_chars=5000)
            paper["full_text"] = full_text

        self._emit(
            "✅ Discovery complete",
            f"Found {len(papers)} papers"
        )
        return {
            "papers": papers,
            "queries_used": [topic] + extra_queries,
        }

    def _expand_queries(self, topic: str, invoke_claude) -> list[str]:
        """Use Claude to generate diverse search queries for the topic."""
        try:
            prompt = QUERY_EXPANSION_TEMPLATE.format(topic=topic)
            raw = invoke_claude(prompt, max_tokens=300, temperature=0.4)
            # Try to parse JSON
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                queries = json.loads(raw[start:end])
                if isinstance(queries, list):
                    return [str(q) for q in queries if q][:5]
        except Exception as exc:
            logger.warning("Query expansion failed: %s", exc)
        return []
