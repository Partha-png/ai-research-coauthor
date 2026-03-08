"""
tools/rag_engine.py – Retrieval-Augmented Generation engine.
Builds a FAISS index over paper embeddings (Bedrock Titan or mock),
then retrieves the top-k most relevant chunks for any query.
"""

import json
import logging
from typing import Any

import numpy as np

logger = logging.getLogger("ai-coauthor.rag")


class RAGEngine:
    """
    Lightweight in-memory RAG engine using FAISS + Bedrock embeddings.
    
    Usage:
        rag = RAGEngine()
        rag.index_papers(papers)                   # embed + index
        chunks = rag.retrieve(query, top_k=5)      # retrieve
        answer = rag.answer(query, context_chunks)  # generate
    """

    def __init__(self, embed_fn=None, llm_fn=None, top_k: int = 5):
        """
        Parameters
        ----------
        embed_fn : callable (text -> list[float])
            Defaults to config.get_embedding
        llm_fn : callable (prompt, system) -> str
            Defaults to config.invoke_claude
        top_k : int
            Number of chunks to retrieve
        """
        from config import get_embedding, invoke_claude, EMBEDDING_DIM, FAISS_TOP_K
        self._embed = embed_fn or get_embedding
        self._llm = llm_fn or invoke_claude
        self._dim = EMBEDDING_DIM
        self._top_k = top_k or FAISS_TOP_K
        self._chunks: list[dict[str, Any]] = []
        self._index = None  # FAISS index, built lazily

    # ──────────────────────────────────────────
    # Indexing
    # ──────────────────────────────────────────

    def _build_faiss_index(self, vectors: np.ndarray):
        try:
            import faiss
            index = faiss.IndexFlatIP(vectors.shape[1])  # Inner-product (cosine if normalised)
            faiss.normalize_L2(vectors)
            index.add(vectors)
            return index
        except ImportError:
            logger.warning("FAISS not installed – falling back to numpy cosine search")
            return None

    def index_papers(self, papers: list[dict[str, Any]]):
        """Embed each paper's text and build the retrieval index."""
        self._chunks = []
        vectors_list: list[list[float]] = []

        for paper in papers:
            text = paper.get("full_text") or paper.get("abstract") or ""
            if not text.strip():
                continue
            # Chunk long texts into overlapping segments
            chunks = _chunk_text(text, max_chars=800, overlap=100)
            for chunk in chunks:
                embedding = self._embed(chunk)
                self._chunks.append({
                    "text": chunk,
                    "paper_id": paper.get("id", ""),
                    "title": paper.get("title", ""),
                    "authors": paper.get("authors", []),
                    "year": paper.get("year", ""),
                    "source": paper.get("source", ""),
                })
                vectors_list.append(embedding)

        if not vectors_list:
            logger.warning("No chunks indexed – RAG will return empty results")
            return

        matrix = np.array(vectors_list, dtype=np.float32)
        self._index = self._build_faiss_index(matrix)
        self._vectors = matrix  # keep for numpy fallback
        logger.info("Indexed %d chunks from %d papers", len(self._chunks), len(papers))

    # ──────────────────────────────────────────
    # Retrieval
    # ──────────────────────────────────────────

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Return the top-k most relevant chunks for a query."""
        k = top_k or self._top_k
        if not self._chunks:
            return []

        q_vec = np.array([self._embed(query)], dtype=np.float32)

        if self._index is not None:
            import faiss
            faiss.normalize_L2(q_vec)
            distances, indices = self._index.search(q_vec, min(k, len(self._chunks)))
            return [self._chunks[i] for i in indices[0] if i < len(self._chunks)]
        else:
            # Numpy fallback: cosine similarity
            mat = self._vectors.copy()
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            norms[norms == 0] = 1
            mat /= norms
            q_norm = q_vec / (np.linalg.norm(q_vec) + 1e-9)
            scores = mat @ q_norm.T
            top_idx = np.argsort(scores[:, 0])[::-1][:k]
            return [self._chunks[i] for i in top_idx]

    # ──────────────────────────────────────────
    # Generation (RAG answer)
    # ──────────────────────────────────────────

    def answer(self, query: str, retrieved_chunks: list[dict] | None = None) -> str:
        """Retrieve relevant chunks and generate an answer using the LLM."""
        chunks = retrieved_chunks or self.retrieve(query)
        if not chunks:
            return self._llm(query)

        context = "\n\n---\n\n".join(
            f"[{c.get('title', 'Unknown')} ({c.get('year', '?')})]\n{c['text']}"
            for c in chunks
        )
        prompt = (
            f"Using ONLY the following research paper excerpts as context, answer the query.\n\n"
            f"### Context\n{context}\n\n"
            f"### Query\n{query}\n\n"
            f"### Answer\nBe concise and cite the paper titles in your response."
        )
        system = (
            "You are a scientific research assistant. "
            "Only use information from the provided context. "
            "Never fabricate citations or data."
        )
        return self._llm(prompt, system=system)


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────

def _chunk_text(text: str, max_chars: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping character-level chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        start += max_chars - overlap
    return [c.strip() for c in chunks if c.strip()]
