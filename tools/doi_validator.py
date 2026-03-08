"""
tools/doi_validator.py – Verify academic citations via DOI.org and arXiv APIs.
Detects hallucinated citations and assigns a confidence score to each.
"""

import re
import time
import logging
import requests
from typing import Any

logger = logging.getLogger("ai-coauthor.doi_validator")

DOI_API_BASE = "https://doi.org/api/handles/"
ARXIV_ABS_URL = "https://export.arxiv.org/abs/"
CROSSREF_API = "https://api.crossref.org/works/"
SEMANTIC_SCHOLAR_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper/"

ARXIV_ID_RE = re.compile(r"\b(\d{4}\.\d{4,5})(v\d+)?\b")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)


def _check_doi(doi: str) -> dict[str, Any]:
    """Query CrossRef to verify a DOI. Returns status dict."""
    url = CROSSREF_API + doi
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "ai-coauthor/1.0"})
        if resp.status_code == 200:
            data = resp.json().get("message", {})
            return {
                "valid": True,
                "title": " ".join(data.get("title", ["Unknown"])),
                "year": data.get("published", {}).get("date-parts", [[None]])[0][0],
                "type": data.get("type", ""),
            }
        elif resp.status_code == 404:
            return {"valid": False, "reason": "DOI not found"}
        else:
            return {"valid": None, "reason": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"valid": None, "reason": str(exc)}


def _check_arxiv(arxiv_id: str) -> dict[str, Any]:
    """Query arXiv to verify an arXiv ID. Returns status dict."""
    clean_id = arxiv_id.replace("arxiv:", "").split("v")[0]
    url = f"https://export.arxiv.org/api/query?id_list={clean_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200 and "<entry>" in resp.text:
            import feedparser
            feed = feedparser.parse(resp.text)
            if feed.entries:
                entry = feed.entries[0]
                if "error" not in entry.get("title", "").lower():
                    return {
                        "valid": True,
                        "title": entry.get("title", "").replace("\n", " ").strip(),
                        "year": entry.get("published", "")[:4],
                    }
        return {"valid": False, "reason": "arXiv ID not found"}
    except Exception as exc:
        return {"valid": None, "reason": str(exc)}


def extract_citations_from_text(text: str) -> list[dict[str, Any]]:
    """
    Extract potential citations (DOIs and arXiv IDs) from free text.
    Returns list of dicts with 'type', 'id', 'raw'.
    """
    citations = []
    seen: set[str] = set()

    for m in DOI_RE.finditer(text):
        doi = m.group().rstrip(".")
        if doi not in seen:
            citations.append({"type": "doi", "id": doi, "raw": doi})
            seen.add(doi)

    for m in ARXIV_ID_RE.finditer(text):
        aid = m.group(1)
        if aid not in seen:
            citations.append({"type": "arxiv", "id": aid, "raw": m.group()})
            seen.add(aid)

    return citations


def validate_citations(
    papers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Given a list of paper dicts (from discovery/search), validate each one.
    Returns the papers enriched with 'verified', 'confidence', and 'verify_reason'.
    """
    results: list[dict[str, Any]] = []
    for paper in papers:
        result = dict(paper)
        doi = paper.get("doi", "")
        arxiv_id = paper.get("arxiv_id", "")
        
        check: dict[str, Any] = {"valid": None, "reason": "no identifier"}

        if arxiv_id:
            check = _check_arxiv(arxiv_id)
            time.sleep(0.2)
        elif doi:
            check = _check_doi(doi)
            time.sleep(0.2)

        if check.get("valid") is True:
            result["verified"] = True
            result["confidence"] = 1.0
            result["verify_reason"] = "confirmed"
        elif check.get("valid") is False:
            result["verified"] = False
            result["confidence"] = 0.0
            result["verify_reason"] = check.get("reason", "invalid")
        else:
            # Couldn't verify (network error / no id) – give partial confidence
            result["verified"] = None
            result["confidence"] = 0.5
            result["verify_reason"] = check.get("reason", "unverified")

        results.append(result)

    verified = sum(1 for r in results if r.get("verified") is True)
    hallucinated = sum(1 for r in results if r.get("verified") is False)
    logger.info(
        "Citation validation complete: %d verified, %d hallucinated, %d unknown",
        verified, hallucinated, len(results) - verified - hallucinated
    )
    return results


def compute_hallucination_rate(validated_papers: list[dict]) -> float:
    """Return fraction of papers flagged as hallucinated (verified=False)."""
    if not validated_papers:
        return 0.0
    bad = sum(1 for p in validated_papers if p.get("verified") is False)
    return round(bad / len(validated_papers), 3)
