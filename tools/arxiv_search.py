"""
tools/arxiv_search.py – Academic paper search via arXiv API and Semantic Scholar.
Returns structured paper dicts ready for downstream agents.
"""

import re
import time
import logging
import requests
import feedparser
from typing import Any

logger = logging.getLogger("ai-coauthor.arxiv")

ARXIV_API = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"

PAPER_FIELDS = "title,authors,year,abstract,externalIds,openAccessPdf,citationCount,tldr"


def search_arxiv(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Search arXiv and return structured paper records."""
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    try:
        resp = requests.get(ARXIV_API, params=params, timeout=20)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as exc:
        logger.warning("arXiv search failed for query '%s': %s", query, exc)
        return []

    papers = []
    for entry in feed.entries:
        arxiv_id = entry.get("id", "").split("/abs/")[-1].split("v")[0]
        pdf_url = entry.get("link", "").replace("/abs/", "/pdf/") + ".pdf"
        year = entry.get("published", "")[:4]
        authors = [a.get("name", "") for a in entry.get("authors", [])]
        papers.append({
            "id": f"arxiv:{arxiv_id}",
            "title": entry.get("title", "").replace("\n", " ").strip(),
            "authors": authors[:5],  # cap to 5 authors
            "year": int(year) if year.isdigit() else 2024,
            "abstract": entry.get("summary", "").replace("\n", " ").strip(),
            "pdf_url": pdf_url,
            "source": "arXiv",
            "arxiv_id": arxiv_id,
            "doi": entry.get("arxiv_doi", None),
            "citation_count": 0,
        })
    return papers


def search_semantic_scholar(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Search Semantic Scholar and return structured paper records."""
    params = {
        "query": query,
        "fields": PAPER_FIELDS,
        "limit": max_results,
    }
    try:
        resp = requests.get(
            SEMANTIC_SCHOLAR_API, params=params, timeout=20,
            headers={"Accept": "application/json"}
        )
        if resp.status_code == 429:
            logger.warning("Semantic Scholar rate limited – skipping")
            return []
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Semantic Scholar search failed: %s", exc)
        return []

    papers = []
    for p in data.get("data", []):
        ext_ids = p.get("externalIds", {}) or {}
        arxiv_id = ext_ids.get("ArXiv", "")
        doi = ext_ids.get("DOI", "")
        authors = [a.get("name", "") for a in (p.get("authors") or [])[:5]]
        pdf_url = ""
        oap = p.get("openAccessPdf")
        if oap and isinstance(oap, dict):
            pdf_url = oap.get("url", "")
        tldr = p.get("tldr") or {}
        abstract = tldr.get("text") or p.get("abstract") or ""
        papers.append({
            "id": f"s2:{p.get('paperId', '')}",
            "title": (p.get("title") or "").strip(),
            "authors": authors,
            "year": p.get("year") or 2024,
            "abstract": abstract,
            "pdf_url": pdf_url,
            "source": "SemanticScholar",
            "arxiv_id": arxiv_id,
            "doi": doi,
            "citation_count": p.get("citationCount", 0),
        })
    return papers


def deduplicate_papers(papers: list[dict]) -> list[dict]:
    """Remove duplicate papers (by arxiv_id or normalised title)."""
    seen_arxiv: set[str] = set()
    seen_titles: set[str] = set()
    unique = []
    for p in papers:
        aid = p.get("arxiv_id", "").strip()
        title_key = re.sub(r"\W+", "", (p.get("title") or "").lower())
        if (aid and aid in seen_arxiv) or (title_key and title_key in seen_titles):
            continue
        if aid:
            seen_arxiv.add(aid)
        if title_key:
            seen_titles.add(title_key)
        unique.append(p)
    return unique


def search_papers(
    query: str,
    max_total: int = 15,
    extra_queries: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Main entry point: search both arXiv and Semantic Scholar,
    merge, deduplicate, and return up to max_total papers.
    """
    half = max(max_total // 2, 5)
    all_papers: list[dict] = []

    queries = [query] + (extra_queries or [])[:2]  # primary + up to 2 expansions

    for q in queries:
        all_papers.extend(search_arxiv(q, half))
        time.sleep(0.3)  # be polite to arXiv
        all_papers.extend(search_semantic_scholar(q, half))

    # Sort by citation count (higher is more influential)
    all_papers.sort(key=lambda p: p.get("citation_count", 0), reverse=True)

    unique = deduplicate_papers(all_papers)
    logger.info("Found %d unique papers for query '%s'", len(unique), query)
    return unique[:max_total]


def get_paper_influence(paper: dict, limit: int = 5) -> dict:
    """
    Fetch citation influence data for a paper from Semantic Scholar.

    Returns a dict with:
        "cited_by"   – list of papers that cite this paper  (up to `limit`)
        "references" – list of papers this paper references (up to `limit`)
    Each entry: {"title", "year", "authors", "citation_count"}

    Falls back to empty lists silently on any error or rate-limit.
    """
    result = {"cited_by": [], "references": []}

    # Build the Semantic Scholar paper ID
    s2_id = ""
    if paper.get("id", "").startswith("s2:"):
        s2_id = paper["id"][3:]
    elif paper.get("arxiv_id"):
        s2_id = f"ArXiv:{paper['arxiv_id']}"
    else:
        return result  # can't look up without an ID

    fields = "title,year,authors,citationCount"
    base = "https://api.semanticscholar.org/graph/v1/paper"
    headers = {"Accept": "application/json"}

    def _fetch(endpoint: str) -> list[dict]:
        try:
            url = f"{base}/{s2_id}/{endpoint}"
            resp = requests.get(
                url,
                params={"fields": fields, "limit": limit},
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 429:
                logger.warning("S2 influence rate-limited for %s", s2_id)
                return []
            resp.raise_for_status()
            raw = resp.json().get("data", [])
            items = []
            for entry in raw:
                # citations wraps in {"citingPaper": {...}}, references in {"citedPaper": {...}}
                p = entry.get("citingPaper") or entry.get("citedPaper") or {}
                if not p.get("title"):
                    continue
                items.append({
                    "title": p.get("title", ""),
                    "year": p.get("year") or "?",
                    "authors": [a.get("name", "") for a in (p.get("authors") or [])[:3]],
                    "citation_count": p.get("citationCount", 0),
                })
            return items
        except Exception as exc:
            logger.debug("S2 %s fetch failed for %s: %s", endpoint, s2_id, exc)
            return []

    result["cited_by"] = _fetch("citations")
    result["references"] = _fetch("references")
    return result

