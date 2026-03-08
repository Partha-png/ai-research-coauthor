# AI Research Co-Author: System Design Document

**Version:** 3.0 (Final — Deployed)  
**Date:** March 2026  
**Project:** AI Research Co-Author Platform  
**Target:** AWS AI for Bharat Hackathon 2026  
**Live URL:** http://44.221.85.33:8501

---

## 1. Design Philosophy

### 1.1 Core Principles

| Principle | Implementation |
|---|---|
| **AWS-Native** | Every component uses a managed AWS service |
| **Fallback-Ready** | Every agent has a graceful fallback — pipeline never crashes |
| **Hallucination-Aware** | All citations verified via real APIs before output |
| **Session Persistence** | DynamoDB first, local JSON fallback automatically |
| **Zero Config** | DynamoDB table + S3 bucket auto-created on startup |

### 1.2 Technology Choices

| Decision | Choice | Reason |
|---|---|---|
| LLM | Amazon Bedrock (Nova Lite) | No Marketplace approval needed; AWS-native |
| Embeddings | Titan Embeddings v1 | Native Bedrock, no extra setup |
| Vector Store | FAISS (local) | Fast, no extra AWS service, runs on EC2 |
| UI | Streamlit | Fastest path to demo-ready UI |
| Hosting | EC2 t3.small | Full control, systemd auto-restart |
| Sessions | DynamoDB | Managed, serverless, auto-scale |
| Storage | S3 | Cheap, durable, pre-signed URL sharing |

---

## 2. System Architecture

### 2.1 Layer Diagram

```
┌──────────────────────────────────────────────────────────┐
│              PRESENTATION LAYER                          │
│                 Streamlit (app.py)                       │
│  Sidebar: username, My Projects, share links             │
│  Tabs: Papers · Analysis · Methodology · Draft · Edit    │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│              ORCHESTRATION LAYER                         │
│               orchestrator.py                            │
│  Sequential pipeline: runs 5 agents, tracks progress,   │
│  saves session to DynamoDB, emits live status events     │
└──┬───────────────────────────────────────────────────────┘
   │
   ├── 🔍 DiscoveryAgent    (agents/discovery_agent.py)
   ├── 📚 ReviewerAgent     (agents/reviewer_agent.py)
   ├── ⚗️  MethodologyAgent  (agents/methodology_agent.py)
   ├── 🔬 CitationAgent     (agents/citation_agent.py)
   └── ✍️  WritingAgent      (agents/writing_agent.py)
        │
┌───────▼───────────────────────────────────────────────────┐
│              TOOL LAYER                                   │
│  arxiv_search.py   → arXiv + Semantic Scholar APIs        │
│  pdf_parser.py     → HTTP download + PyPDF2 extraction    │
│  doi_validator.py  → CrossRef + arXiv ID verification     │
│  rag_engine.py     → FAISS + Titan Embeddings             │
│  s3_uploader.py    → S3 put + pre-signed URL generation   │
└──────────────────────┬────────────────────────────────────┘
                       │
┌──────────────────────▼────────────────────────────────────┐
│              AWS SERVICES LAYER                           │
│  Amazon Bedrock    → LLM + Embeddings inference           │
│  Amazon DynamoDB   → Session read/write                   │
│  Amazon S3         → Draft + BibTeX storage               │
│  Amazon EC2        → App hosting (systemd service)        │
└───────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
User inputs topic
      │
      ▼
DiscoveryAgent
  → query arXiv (feedparser)
  → query Semantic Scholar (requests)
  → download PDFs (requests + PyPDF2)
  → output: papers[] with full_text
      │
      ▼
ReviewerAgent
  → embed papers (Bedrock Titan Embeddings)
  → index into FAISS
  → LLM summarise each paper (Bedrock Nova Lite)
  → LLM identify research gaps
  → output: summaries[], gaps[], related_work_section
      │
      ▼
MethodologyAgent
  → LLM propose experimental design
  → output: methodology_section, contributions[]
      │
      ▼
CitationAgent
  → verify DOIs via CrossRef API
  → verify arXiv IDs via arXiv API
  → score each citation 0–100%
  → output: verified_citations[], hallucination_count
      │
      ▼
WritingAgent
  → LLM assemble full Markdown paper
  → upload draft.md + references.bib to S3
  → generate pre-signed download URLs
  → output: full_draft, bibtex, s3_urls
      │
      ▼
Orchestrator saves session → DynamoDB
UI renders results, share link, edit bar
```

---

## 3. Agent Detailed Design

### Agent 1: DiscoveryAgent

```python
# Key logic in agents/discovery_agent.py
inputs:  { topic: str }
outputs: { papers: List[Dict] }

steps:
  1. LLM generates 3 diverse search queries from topic
  2. Query arXiv API via feedparser for each query
  3. Query Semantic Scholar API for additional papers
  4. Fetch influence data (cited_by, references) per paper
  5. Download PDF → extract text via PyPDF2
  6. Fallback: use abstract if PDF fails

resilience: per-paper PDF failures silently use abstract
```

### Agent 2: ReviewerAgent

```python
# Key logic in agents/reviewer_agent.py
inputs:  { papers: List[Dict] }
outputs: { summaries, gaps, related_work_section }

steps:
  1. Embed each paper chunk via Titan Embeddings
  2. Index all chunks into FAISS vector store
  3. LLM summarises each paper (with RAG context)
  4. LLM identifies cross-paper research gaps
  5. LLM writes Related Work section

resilience: LLM failure per paper → use abstract as summary
```

### Agent 3: MethodologyAgent

```python
# Key logic in agents/methodology_agent.py
inputs:  { related_work_section, gaps }
outputs: { methodology_section, contributions }

steps:
  1. LLM proposes datasets + metrics + approach
  2. LLM lists novel contributions vs existing work

resilience: returns structured placeholder if LLM fails
```

### Agent 4: CitationAgent

```python
# Key logic in agents/citation_agent.py
inputs:  { papers: List[Dict] }
outputs: { verified_citations, bibtex_entries, hallucination_count }

steps:
  1. For each DOI → query CrossRef API → verify title match
  2. For each arXiv ID → query arXiv API → verify exists
  3. Assign confidence score 0–100%
  4. Generate BibTeX entry per verified citation
  5. Count and report hallucinated citations

resilience: unverifiable citations marked with low confidence (not removed)
```

### Agent 5: WritingAgent

```python
# Key logic in agents/writing_agent.py
inputs:  { all prior agent outputs }
outputs: { full_draft_markdown, bibtex, s3_draft_url, s3_bibtex_url }

steps:
  1. LLM assembles: Abstract, Intro, Related Work,
     Methodology, Experiments (placeholder), Conclusion
  2. Appends BibTeX references
  3. Uploads draft.md + references.bib to S3
  4. Returns pre-signed URLs (valid 7 days)

resilience: returns draft without S3 URL if upload fails
```

---

## 4. Session Management Design

```python
# memory/session_manager.py

Session schema (DynamoDB / JSON):
{
  "session_id": str (UUID),
  "username": str,
  "topic": str,
  "status": "running" | "completed" | "failed",
  "papers": List[Dict],        # floats → Decimal for DynamoDB
  "summaries": List[str],
  "methodology": str,
  "draft": str,
  "bibtex": str,
  "s3_draft_url": str,
  "s3_bibtex_url": str,
  "metrics": {
    "total_papers": int,
    "verified_citations": int,
    "hallucinated_citations": int,
    "total_time_seconds": float
  },
  "share_token": str,          # UUID for read-only share link
  "created_at": str (ISO8601),
  "updated_at": str (ISO8601)
}
```

**Key implementation details:**
- `_to_dynamo_safe()` recursively converts `float` → `Decimal`, removes `None` values
- Auto-fallback to local JSON if DynamoDB is unavailable
- Share tokens are UUID-based, stored in session, accessible via `?share=<token>`

---

## 5. UI Design

### Layout
```
Sidebar:
  ├── Username input
  ├── My Projects (user's saved sessions)
  └── Research topic + Run button

Main area (Tabs):
  ├── 📋 Papers Found   → paper cards + influence metrics
  ├── 📊 Analysis       → themes, gaps, quality scores
  ├── ⚗️  Methodology    → proposed design + contributions
  ├── 📝 Citations      → verification table + hallucination score
  └── 📄 Full Draft     → Markdown render + AI edit bar + Share button

Bottom bar (Full Draft tab):
  └── ChatGPT-style input: "Ask AI to edit your draft"
```

### Share Link Flow
```
1. User clicks "Share"
2. App generates share_token (UUID) → saves to session
3. URL: http://44.221.85.33:8501?share=<token>
4. Shared view: read-only banner, all tabs visible, no edit controls
```

---

## 6. Deployment Architecture

```
AWS EC2 (t3.small, Ubuntu 22.04, us-east-1)
├── /home/ubuntu/ai-research-coauthor/   ← git clone
│   ├── app.py
│   ├── .env                             ← secrets (never committed)
│   └── venv/                            ← Python 3.11 virtualenv
│
└── /etc/systemd/system/streamlit_app.service
    ├── ExecStart: venv/bin/streamlit run app.py --server.port=8501
    ├── Restart: always
    └── EnvironmentFile: .env
```

**Instance:** `i-0589333063212ea96`  
**IP:** `44.221.85.33`  
**Security Group:** port 22 (SSH, my IP only) + port 8501 (0.0.0.0/0)

---

## 7. Cost Analysis

| Service | Usage per session | Cost |
|---|---|---|
| Amazon Bedrock Nova Lite | ~40K in + ~10K out tokens | ~$0.010 |
| Titan Embeddings | ~15K tokens | ~$0.002 |
| Amazon DynamoDB | 1 write + 5 reads | ~$0.001 |
| Amazon S3 | ~100 KB stored | ~$0.001 |
| Amazon EC2 t3.small | $0.02/hr shared | ~$0.002 |
| **Total** | | **~$0.016/session** |

---

## 8. Anti-Hallucination Design

```
Problem: LLMs frequently fabricate citations (fake titles, wrong authors, invalid DOIs)

Solution: 3-layer verification

Layer 1: DOI Verification
  → Check CrossRef API for every paper with a DOI
  → Match on title similarity to detect swapped-in real DOIs

Layer 2: arXiv ID Verification
  → Hit arXiv API for every arxiv_id
  → Verify the ID exists and title matches

Layer 3: Prompt Engineering
  → All generation prompts explicitly say:
    "Only cite papers from the provided context.
     Do not invent citations. Use exact titles."

Output: Confidence score per citation (0–100%)
        Hallucination rate displayed in UI
```

---

## 9. File Structure

```
ai-research-coauthor/
├── app.py                   # Streamlit UI (main entry point)
├── config.py                # AWS clients, auto-create DynamoDB/S3
├── orchestrator.py          # Pipeline coordinator
├── prompts.py               # All LLM prompt templates
├── agents/
│   ├── base_agent.py        # Abstract BaseAgent
│   ├── discovery_agent.py
│   ├── reviewer_agent.py
│   ├── methodology_agent.py
│   ├── citation_agent.py
│   └── writing_agent.py
├── tools/
│   ├── arxiv_search.py      # arXiv + Semantic Scholar + influence
│   ├── pdf_parser.py        # PDF download + PyPDF2 extraction
│   ├── doi_validator.py     # CrossRef + arXiv verification
│   ├── rag_engine.py        # FAISS + Titan Embeddings RAG
│   └── s3_uploader.py       # S3 put-object + pre-signed URL
├── memory/
│   └── session_manager.py   # DynamoDB / JSON sessions + sharing
├── streamlit_app.service    # systemd unit for EC2
├── requirements.txt
├── requirements.md          # System requirements (this project)
├── design.md                # System design (this document)
├── README.md                # Project overview
├── .env.example             # Environment variable template
└── .gitignore               # Excludes .env, venv, __pycache__
```

---

**Document Status:** Final  
**Prepared for:** AWS AI for Bharat Hackathon 2026

---

*Built with ❤️ for AWS AI for Bharat Hackathon 2026*
