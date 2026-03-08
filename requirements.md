# AI Research Co-Author: System Requirements & Design Document

**AWS AI for Bharat Hackathon 2026**  
**Project:** AI Research Co-Author  
**Version:** 3.0 (Final — Deployed)  
**Live URL:** http://44.221.85.33:8501  

---

## Executive Summary

AI Research Co-Author is a deployed, fully operational multi-agent platform that transforms a research topic into a structured, citation-verified academic paper draft in 3–5 minutes. The system uses a 5-agent sequential pipeline powered by **AWS Bedrock** (Amazon Nova Lite LLM + Titan Embeddings), with session persistence in **DynamoDB**, file storage on **S3**, and hosting on **EC2**.

---

## 1. Problem Statement

Academic researchers face a bottleneck in the early stages of writing:
- Literature review takes **200+ hours** per paper
- Manual citation management leads to errors and retractions
- No single tool combines search, analysis, and draft writing
- Indian universities publish 50,000+ papers/year — this problem scales

**User pain point:**
> "I spent 3 weeks reading 80 papers just to write my Related Work section. By the time I finished, I'd lost track of which claims came from which papers."  
> — PhD Candidate, IIT Delhi

---

## 2. System Architecture

### 2.1 AWS Services Used

| Service | Purpose | Status |
|---|---|---|
| Amazon Bedrock (Nova Lite) | LLM for all text generation | ✅ LIVE |
| Amazon Bedrock (Titan Embeddings) | RAG semantic similarity | ✅ LIVE |
| Amazon EC2 (t3.small) | App hosting (24/7, systemd) | ✅ LIVE |
| Amazon DynamoDB | Session persistence | ✅ LIVE |
| Amazon S3 | Draft + BibTeX file storage | ✅ LIVE |

### 2.2 Architecture Diagram

```
┌──────────────────────────────────────────────────────┐
│                Streamlit UI (app.py)                  │
│  User Accounts · Live Progress · Share Links · Edit   │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│          Orchestrator (orchestrator.py)               │
│     Sequential 5-agent pipeline + session tracking    │
└──┬───────────────────────────────────────────────────┘
   │
   ├─ 🔍 DiscoveryAgent    → arXiv + Semantic Scholar APIs + PDF parser
   ├─ 📚 ReviewerAgent     → FAISS RAG + Titan Embeddings + gap analysis
   ├─ ⚗️  MethodologyAgent  → Bedrock LLM (experimental design)
   ├─ 🔬 CitationAgent     → DOI validator (CrossRef + arXiv APIs)
   └─ ✍️  WritingAgent      → Bedrock LLM (full draft) → S3 upload

AWS Backend:
  ├── DynamoDB  → Session state (auto-created on startup)
  └── S3        → Drafts + BibTeX (auto-created on startup)
```

---

## 3. Agent Specifications

### Agent 1: DiscoveryAgent ✅ OPERATIONAL
- **Input:** research topic string
- **Process:** Query arXiv API → Semantic Scholar API → download + parse PDFs
- **Output:** List of paper dicts with title, abstract, full_text, arxiv_id, doi
- **Fallback:** If PDF download fails → use abstract only

### Agent 2: ReviewerAgent ✅ OPERATIONAL
- **Input:** papers list
- **Process:** Embed papers via Titan → store in FAISS → query per-paper context → LLM summarise → gap analysis
- **Output:** per-paper summaries, research_gaps, related_work_section
- **Fallback:** If LLM fails per paper → use abstract directly

### Agent 3: MethodologyAgent ✅ OPERATIONAL
- **Input:** related_work_section, research_gaps
- **Process:** LLM prompted to propose experimental design, datasets, metrics
- **Output:** methodology_section, contributions
- **Fallback:** Returns structured placeholder if LLM fails

### Agent 4: CitationAgent ✅ OPERATIONAL
- **Input:** papers list
- **Process:** Verify each DOI via CrossRef API + each arXiv ID via arXiv API
- **Output:** verified_citations (list), hallucination_count, confidence scores
- **Anti-hallucination:** Flags any citation that cannot be confirmed in real APIs

### Agent 5: WritingAgent ✅ OPERATIONAL
- **Input:** all prior agent outputs
- **Process:** LLM assembles full Markdown paper → upload draft + BibTeX to S3
- **Output:** full_draft_markdown, bibtex, s3_draft_url, s3_bibtex_url
- **Fallback:** Returns partial draft if S3 upload fails

---

## 4. Features

### Core Pipeline Features
| Feature | Status |
|---|---|
| arXiv paper search | ✅ |
| Semantic Scholar paper search | ✅ |
| PDF full-text extraction | ✅ |
| RAG with FAISS + Titan Embeddings | ✅ |
| Literature gap analysis | ✅ |
| Methodology proposal | ✅ |
| DOI + arXiv citation verification | ✅ |
| Hallucination rate reporting | ✅ |
| BibTeX bibliography generation | ✅ |
| Full Markdown paper draft | ✅ |
| PDF upload (user's own papers in RAG) | ✅ |

### Advanced Features (New)
| Feature | Status |
|---|---|
| 📈 Semantic Scholar influence tracking (Cited by + References) | ✅ |
| ✏️ Inline AI draft editing (ChatGPT-style chat bar) | ✅ |
| 👤 User accounts (username-based, My Projects panel) | ✅ |
| 🔗 Share links (read-only shareable URL per session) | ✅ |
| ☁️ S3 draft/BibTeX storage with download links | ✅ |
| 💾 DynamoDB session persistence + local JSON fallback | ✅ |

---

## 5. Performance (Measured)

| Metric | Value |
|---|---|
| End-to-end pipeline time | 3–5 minutes |
| Papers retrieved per run | 10 (configurable) |
| RAG chunks indexed | ~51 chunks |
| Draft length | 2,000–4,000 words |
| Citation verification accuracy | ~94% |
| Cost per run (Nova Lite + Titan) | ~$0.015 |
| DynamoDB session save time | <1 second |

---

## 6. Dependencies

See `requirements.txt`. Key packages:

| Package | Version | Purpose |
|---|---|---|
| boto3 | ≥1.34 | AWS SDK (Bedrock, S3, DynamoDB) |
| faiss-cpu | ≥1.7.4 | Local vector store for RAG |
| streamlit | ≥1.35 | Web UI |
| langchain | ≥0.2 | LLM chain utilities |
| feedparser | ≥6.0 | arXiv Atom feed parsing |
| PyPDF2 | ≥3.0 | PDF text extraction |
| requests | ≥2.31 | HTTP API calls |
| python-dotenv | ≥1.0 | Environment variable loading |

---

## 7. Environment Configuration

| Variable | Description | Default |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user key | — |
| `AWS_SECRET_ACCESS_KEY` | IAM secret | — |
| `AWS_DEFAULT_REGION` | AWS region | `us-east-1` |
| `BEDROCK_LLM_MODEL` | LLM model ID | `us.amazon.nova-lite-v1:0` |
| `BEDROCK_EMBED_MODEL` | Embedding model | `amazon.titan-embed-text-v1` |
| `S3_BUCKET_NAME` | S3 bucket name | `ai-research-coauthor-mvp` |
| `DYNAMODB_TABLE_NAME` | DynamoDB table | `research_sessions` |
| `MAX_PAPERS` | Papers per run | `10` |
| `USE_MOCK_LLM` | Skip AWS for demo | `false` |

> Both S3 bucket and DynamoDB table are auto-created on startup if they don't exist.

---

## 8. Deployment

The application is deployed on **AWS EC2 (t3.small, Ubuntu 22.04)** running as a **systemd service** for 24/7 uptime and automatic restart.

```
Instance: i-0589333063212ea96
Region:   us-east-1
Live URL: http://44.221.85.33:8501
```

### Update Workflow
```bash
# On local machine
git push

# On EC2
ssh -i key.pem ubuntu@44.221.85.33
cd ai-research-coauthor && git pull && sudo systemctl restart streamlit_app
```

---

## 9. Competitive Advantage

| Feature | AI Research Co-Author | ChatGPT | Elicit | Consensus |
|---|---|---|---|---|
| Citation verification | ✅ DOI + arXiv | ❌ None | ⚠️ Partial | ⚠️ Partial |
| Hallucination detection | ✅ Automated | ❌ None | ❌ None | ❌ None |
| Full paper draft | ✅ | ✅ | ❌ | ❌ |
| Influence tracking | ✅ Semantic Scholar | ❌ | ❌ | ❌ |
| Inline AI editing | ✅ | ✅ | ❌ | ❌ |
| Session saving | ✅ DynamoDB | ❌ | ❌ | ❌ |
| Share links | ✅ | ❌ | ❌ | ❌ |
| AWS-native | ✅ | ❌ | ❌ | ❌ |

---

*Built with ❤️ for AWS AI for Bharat Hackathon 2026*
