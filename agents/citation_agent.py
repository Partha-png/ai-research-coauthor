"""
agents/citation_agent.py – Citation verification and hallucination detection.
Validates all discovered papers through DOI and arXiv APIs,
flags hallucinated citations, and formats bibliography.
"""

import logging
from typing import Any

from agents.base_agent import BaseAgent
from tools.doi_validator import validate_citations, compute_hallucination_rate

logger = logging.getLogger("ai-coauthor.citation")


def _format_citation_ieee(paper: dict, index: int) -> str:
    """Format a single paper as an IEEE citation string."""
    authors = paper.get("authors", [])
    if len(authors) > 3:
        author_str = ", ".join(authors[:3]) + " et al."
    elif authors:
        author_str = ", ".join(authors)
    else:
        author_str = "Unknown"

    title = paper.get("title", "Unknown Title")
    year = paper.get("year", "n.d.")
    arxiv_id = paper.get("arxiv_id", "")
    doi = paper.get("doi", "")

    ref = f"[{index}] {author_str}, \"{title},\" {year}."
    if doi:
        ref += f" doi: {doi}"
    elif arxiv_id:
        ref += f" arXiv:{arxiv_id}"
    return ref


def _format_bibtex(paper: dict) -> str:
    """Format a paper as BibTeX."""
    key = _make_bibtex_key(paper)
    authors = " and ".join(paper.get("authors", ["Unknown"]))
    title = paper.get("title", "Unknown Title")
    year = paper.get("year", "2024")
    arxiv_id = paper.get("arxiv_id", "")
    doi = paper.get("doi", "")
    journal = "arXiv preprint" if arxiv_id else "Unknown Journal"

    lines = [
        f"@article{{{key},",
        f"  author  = {{{authors}}},",
        f"  title   = {{{title}}},",
        f"  year    = {{{year}}},",
        f"  journal = {{{journal}}},",
    ]
    if arxiv_id:
        lines.append(f"  eprint  = {{{arxiv_id}}},")
        lines.append(f"  archivePrefix = {{arXiv}},")
    if doi:
        lines.append(f"  doi     = {{{doi}}},")
    lines.append("}")
    return "\n".join(lines)


def _make_bibtex_key(paper: dict) -> str:
    """Generate a BibTeX citation key like 'Smith2024'."""
    import re
    authors = paper.get("authors", [])
    last_name = re.sub(r"\W", "", (authors[0].split()[-1] if authors else "Unknown"))
    year = str(paper.get("year", "2024"))
    title_words = re.findall(r"\w+", paper.get("title", ""))
    title_word = title_words[0].capitalize() if title_words else "Paper"
    return f"{last_name}{year}{title_word}"


class CitationAgent(BaseAgent):
    """
    Agent 4 – Verifies citations and generates bibliography.
    
    Inputs:
        papers (list[dict]): Papers from DiscoveryAgent
        summaries (list[dict]): Summaries from ReviewerAgent
        output_format (str): 'IEEE', 'ACM', 'APA', 'MLA'
        
    Outputs:
        validated_papers (list[dict]): Papers with verified/confidence fields
        hallucination_rate (float): Fraction of invalid citations
        ieee_references (list[str]): Formatted IEEE reference strings
        bibtex (str): Full BibTeX bibliography
        citation_stats (dict): Verification summary statistics
    """

    name = "citation"

    def _run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        papers: list[dict] = inputs.get("papers", [])
        summaries: list[dict] = inputs.get("summaries", [])
        output_format: str = inputs.get("output_format", "IEEE")

        # Use summaries as fallback if no papers
        source = papers if papers else summaries

        if not source:
            return {
                "validated_papers": [],
                "hallucination_rate": 0.0,
                "ieee_references": [],
                "bibtex": "",
                "citation_stats": {},
            }

        self._emit("🔬 Verifying citations", f"Checking {len(source)} papers via DOI/arXiv APIs")
        validated = validate_citations(source)
        hall_rate = compute_hallucination_rate(validated)

        verified_papers = [p for p in validated if p.get("verified") is not False]

        self._emit("📚 Formatting bibliography", f"Format: {output_format}")
        ieee_refs = [
            _format_citation_ieee(p, i + 1)
            for i, p in enumerate(verified_papers)
        ]
        bibtex = "\n\n".join(_format_bibtex(p) for p in verified_papers)

        stats = {
            "total_papers": len(validated),
            "verified": sum(1 for p in validated if p.get("verified") is True),
            "unverified": sum(1 for p in validated if p.get("verified") is None),
            "hallucinated": sum(1 for p in validated if p.get("verified") is False),
            "hallucination_rate_pct": round(hall_rate * 100, 1),
        }

        self._emit(
            "✅ Citations verified",
            f"{stats['verified']} confirmed | {stats['hallucinated']} flagged"
        )
        return {
            "validated_papers": validated,
            "hallucination_rate": hall_rate,
            "ieee_references": ieee_refs,
            "bibtex": bibtex,
            "citation_stats": stats,
        }
