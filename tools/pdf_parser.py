"""
tools/pdf_parser.py – Download and extract text from academic PDFs.
Uses PyPDF2 for extraction with graceful fallback when PDFs are unavailable.
"""

import io
import logging
import requests
from typing import Optional

logger = logging.getLogger("ai-coauthor.pdf_parser")


def _download_pdf(pdf_url: str, timeout: int = 15) -> Optional[bytes]:
    """Download a PDF from a URL. Returns bytes or None on failure."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; AI-Research-CoAuthor/1.0; "
                "+https://github.com/ai-coauthor)"
            )
        }
        resp = requests.get(pdf_url, headers=headers, timeout=timeout, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "pdf" not in content_type and not pdf_url.endswith(".pdf"):
            logger.debug("URL %s does not appear to be a PDF (Content-Type: %s)", pdf_url, content_type)
        data = resp.content
        return data if data else None
    except Exception as exc:
        logger.warning("Failed to download PDF from %s: %s", pdf_url, exc)
        return None


def _extract_text_from_bytes(pdf_bytes: bytes, max_chars: int = 6000) -> str:
    """Extract raw text from PDF bytes using PyPDF2."""
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        texts: list[str] = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
                texts.append(text)
            except Exception:
                continue
        full_text = "\n".join(texts)
        # Clean up excessive whitespace
        import re
        full_text = re.sub(r"\n{3,}", "\n\n", full_text)
        full_text = re.sub(r"[ \t]{2,}", " ", full_text)
        return full_text[:max_chars].strip()
    except Exception as exc:
        logger.warning("PyPDF2 extraction failed: %s", exc)
        return ""


def extract_sections(text: str) -> dict[str, str]:
    """
    Attempt to identify common section headers and split the PDF text.
    Returns a dict with keys like 'abstract', 'introduction', 'methodology', etc.
    """
    import re
    section_patterns = {
        "abstract": r"abstract",
        "introduction": r"1\.?\s*introduction",
        "related_work": r"(2\.?\s*related work|background|literature review)",
        "methodology": r"(3\.?\s*method|approach|proposed|framework)",
        "experiments": r"(4\.?\s*experiment|evaluation|results)",
        "conclusion": r"(conclusion|summary|future work)",
    }
    sections: dict[str, str] = {}
    lower = text.lower()
    positions: list[tuple[str, int]] = []

    for name, pattern in section_patterns.items():
        m = re.search(pattern, lower)
        if m:
            positions.append((name, m.start()))

    positions.sort(key=lambda x: x[1])

    for i, (name, start) in enumerate(positions):
        end = positions[i + 1][1] if i + 1 < len(positions) else len(text)
        sections[name] = text[start:end].strip()[:2000]

    return sections


def parse_paper_pdf(paper: dict, max_chars: int = 6000) -> str:
    """
    Given a paper dict (with 'pdf_url' and 'abstract' fields),
    attempt to download and extract the PDF text.
    Falls back gracefully to the abstract.
    """
    pdf_url = paper.get("pdf_url", "")
    abstract = paper.get("abstract", "")

    if not pdf_url:
        logger.debug("No pdf_url for paper '%s' – using abstract", paper.get("title", ""))
        return abstract

    pdf_bytes = _download_pdf(pdf_url)
    if not pdf_bytes:
        return abstract

    full_text = _extract_text_from_bytes(pdf_bytes, max_chars=max_chars)
    if not full_text.strip():
        return abstract

    logger.info("Successfully extracted %d chars from '%s'", len(full_text), paper.get("title", "")[:60])
    return full_text


# ──────────────────────────────────────────────────────────
# Uploaded file parser  (for user-supplied PDFs / TXT files)
# ──────────────────────────────────────────────────────────

def _guess_title_from_text(text: str, filename: str) -> str:
    """
    Try to extract a title from the first non-empty lines of the document.
    Falls back to the filename stem if nothing looks good.
    """
    import re
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:10]:
        # Title-like: 5–15 words, no trailing punctuation patterns
        words = line.split()
        if 4 <= len(words) <= 18 and not line.endswith(":"):
            return line
    stem = re.sub(r"[_\-]+", " ", filename)
    return stem.rsplit(".", 1)[0].strip().title()


def parse_uploaded_pdf(file_bytes: bytes, filename: str) -> dict:
    """
    Parse a user-uploaded PDF or TXT file and return a paper dict
    compatible with the rest of the pipeline (same schema as arXiv search).

    Parameters
    ----------
    file_bytes : bytes
        Raw bytes of the uploaded file (from st.file_uploader or similar).
    filename : str
        Original filename (e.g. "my_paper.pdf").

    Returns
    -------
    dict with keys: id, title, authors, year, abstract, full_text,
                    source, arxiv_id, doi, citation_count, is_uploaded
    """
    import uuid as _uuid

    fname_lower = filename.lower()

    # ── Extract text ──────────────────────────────────────────────
    if fname_lower.endswith(".pdf"):
        full_text = _extract_text_from_bytes(file_bytes, max_chars=8000)
        if not full_text.strip():
            logger.warning("Could not extract text from uploaded PDF '%s'", filename)
            full_text = f"[Could not extract text from {filename}]"
    elif fname_lower.endswith(".txt"):
        try:
            full_text = file_bytes.decode("utf-8", errors="replace")[:8000]
        except Exception:
            full_text = f"[Could not decode {filename}]"
    else:
        full_text = f"[Unsupported format: {filename}]"

    # ── Detect metadata from content ─────────────────────────────
    title = _guess_title_from_text(full_text, filename)
    # Use first ~400 chars as the "abstract" displayed in the paper list
    abstract = " ".join(full_text.split()[:80])

    paper_id = f"upload:{_uuid.uuid4().hex[:8]}"
    logger.info(
        "Parsed uploaded file '%s' → %d chars | title='%s'",
        filename, len(full_text), title[:60],
    )

    return {
        "id": paper_id,
        "title": title,
        "authors": ["(Uploaded by user)"],
        "year": 2024,
        "abstract": abstract,
        "full_text": full_text,
        "pdf_url": "",
        "source": "Upload",
        "arxiv_id": "",
        "doi": "",
        "citation_count": 0,
        "is_uploaded": True,          # flag so UI can label it differently
        "filename": filename,
        "verified": True,             # user-provided papers are implicitly trusted
        "confidence": 1.0,
        "verify_reason": "user-uploaded",
    }
