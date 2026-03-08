"""tools package"""
from tools.arxiv_search import search_papers
from tools.pdf_parser import parse_paper_pdf
from tools.doi_validator import validate_citations, compute_hallucination_rate
from tools.rag_engine import RAGEngine

__all__ = [
    "search_papers", "parse_paper_pdf",
    "validate_citations", "compute_hallucination_rate",
    "RAGEngine",
]
