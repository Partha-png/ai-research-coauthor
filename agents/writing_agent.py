"""
agents/writing_agent.py – Final draft assembly agent.
Generates Abstract, Introduction, Limitations, Future Work, and Conclusion
sections, then assembles the full paper in Markdown (+ optional LaTeX).
"""

import logging
from typing import Any

from agents.base_agent import BaseAgent
from prompts import (
    ABSTRACT_TEMPLATE,
    INTRO_TEMPLATE,
    FUTURE_WORK_TEMPLATE,
    LIMITATIONS_TEMPLATE,
    CONCLUSION_TEMPLATE,
)
from tools.s3_uploader import upload_draft as s3_upload_draft

logger = logging.getLogger("ai-coauthor.writing")


def _section(title: str, content: str) -> str:
    """Wrap content in a Markdown section with a heading."""
    return f"## {title}\n\n{content.strip()}\n"


def _assemble_markdown(
    topic: str,
    abstract: str,
    introduction: str,
    related_work: str,
    methodology: str,
    limitations: str,
    future_work: str,
    conclusion: str,
    references: list[str],
) -> str:
    """Assemble all sections into a full Markdown document."""
    parts = [
        f"# {topic}\n",
        "---\n",
        _section("Abstract", abstract),
        _section("1. Introduction", introduction),
        _section("2. Related Work", related_work),
        _section("3. Methodology", methodology),
        _section("4. Limitations", limitations),
        _section("5. Future Work", future_work),
        _section("6. Conclusion", conclusion),
    ]
    if references:
        refs_text = "\n".join(f"{r}" for r in references)
        parts.append(_section("References", refs_text))

    return "\n\n".join(parts)


class WritingAgent(BaseAgent):
    """
    Agent 5 – Assembles the complete research paper draft.
    
    Inputs:
        topic (str)
        related_work_section (str)
        methodology_section (str)
        gaps (str)
        summaries (list[dict])
        ieee_references (list[str])
        bibtex (str)
        
    Outputs:
        abstract (str)
        introduction (str)
        limitations (str)
        future_work (str)
        conclusion (str)
        full_draft_markdown (str)
        bibtex (str)
        word_count (int)
    """

    name = "writing"

    def _run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        from config import invoke_claude, MAX_TOKENS_SECTION

        topic: str = inputs["topic"]
        related_work: str = inputs.get("related_work_section", "")
        methodology: str = inputs.get("methodology_section", "")
        gaps: str = inputs.get("gaps", "")
        summaries: list[dict] = inputs.get("summaries", [])
        ieee_refs: list[str] = inputs.get("ieee_references", [])
        bibtex: str = inputs.get("bibtex", "")

        # Excerpts for prompts
        rw_excerpt = related_work[:800] if related_work else ""
        meth_excerpt = methodology[:800] if methodology else ""
        gaps_summary = gaps[:500] if gaps else ""
        contributions = f"A systematic review and methodology proposal for: {topic}"

        # ── 1. Abstract ────────────────────────────────────────────────
        self._emit("✍️ Writing Abstract", "")
        abstract = invoke_claude(
            ABSTRACT_TEMPLATE.format(
                topic=topic,
                related_work_excerpt=rw_excerpt,
                methodology_excerpt=meth_excerpt,
                gaps_summary=gaps_summary,
            ),
            max_tokens=400,
            temperature=0.2,
        )

        # ── 2. Introduction ──────────────────────────────────────────
        self._emit("✍️ Writing Introduction", "")
        introduction = invoke_claude(
            INTRO_TEMPLATE.format(
                topic=topic,
                abstract=abstract[:400],
                gaps=gaps_summary,
            ),
            max_tokens=700,
            temperature=0.2,
        )

        # ── 3. Limitations ───────────────────────────────────────────
        self._emit("✍️ Writing Limitations", "")
        limitations = invoke_claude(
            LIMITATIONS_TEMPLATE.format(
                topic=topic,
                methodology_excerpt=meth_excerpt,
            ),
            max_tokens=300,
            temperature=0.2,
        )

        # ── 4. Future Work ───────────────────────────────────────────
        self._emit("✍️ Writing Future Work", "")
        future_work = invoke_claude(
            FUTURE_WORK_TEMPLATE.format(
                topic=topic,
                methodology_excerpt=meth_excerpt,
                gaps=gaps_summary,
            ),
            max_tokens=400,
            temperature=0.3,
        )

        # ── 5. Conclusion ─────────────────────────────────────────────
        self._emit("✍️ Writing Conclusion", "")
        conclusion = invoke_claude(
            CONCLUSION_TEMPLATE.format(
                topic=topic,
                contributions=contributions,
                future_work=future_work[:300],
            ),
            max_tokens=350,
            temperature=0.2,
        )

        # ── 6. Assemble full document ─────────────────────────────────
        self._emit("📎 Assembling full draft", "")
        full_draft = _assemble_markdown(
            topic=topic,
            abstract=abstract,
            introduction=introduction,
            related_work=related_work,
            methodology=methodology,
            limitations=limitations,
            future_work=future_work,
            conclusion=conclusion,
            references=ieee_refs,
        )

        word_count = len(full_draft.split())
        self._emit("✅ Draft complete", f"~{word_count:,} words")

        # ── 7. Upload to S3 ───────────────────────────────────────────
        self._emit("☁️ Uploading to S3", "Saving draft + BibTeX…")
        s3_urls = s3_upload_draft(
            session_id=self.session_id,
            markdown_text=full_draft,
            bibtex_text=bibtex,
        )
        if s3_urls.get("draft_url"):
            self._emit("✅ S3 upload complete", "Draft available via pre-signed URL")
        else:
            self._emit("⚠️ S3 upload skipped", "Check credentials / bucket name")

        return {
            "abstract": abstract,
            "introduction": introduction,
            "limitations": limitations,
            "future_work": future_work,
            "conclusion": conclusion,
            "full_draft_markdown": full_draft,
            "bibtex": bibtex,
            "word_count": word_count,
            "s3_draft_url": s3_urls.get("draft_url"),
            "s3_bibtex_url": s3_urls.get("bibtex_url"),
        }
