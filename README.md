# 🔬 AI Research Co-Author

> **Multi-agent platform that turns a research topic into a citation-verified paper draft in minutes.**

Built for the **AWS AI for Bharat Hackathon**. Uses AWS Bedrock (Claude 3.5 Sonnet + Titan Embeddings) with a 5-agent pipeline orchestrated locally.

---

## ✨ What It Does

1. **Discovers** 10–20 relevant papers from arXiv + Semantic Scholar
2. **Reviews** the literature with RAG-powered summaries and gap analysis
3. **Proposes** a novel methodology grounded in the existing research
4. **Verifies** every citation via DOI.org + arXiv APIs (detects hallucinated refs)
5. **Assembles** a full Markdown paper draft with BibTeX bibliography

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your AWS credentials
# Or set USE_MOCK_LLM=true to test without AWS

# 3. Launch the app
streamlit run app.py
```

Then open http://localhost:8501 in your browser.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│              Streamlit UI (app.py)               │
│     Live progress • Results dashboard • Export   │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│            Orchestrator (orchestrator.py)         │
│       Sequential 5-agent pipeline + sessions      │
└──┬──────────────────────────────────────────────┘
   │
   ├─ 🔍 DiscoveryAgent   → arxiv_search + pdf_parser
   ├─ 📚 ReviewerAgent    → RAGEngine + Claude 3.5
   ├─ ⚗️  MethodologyAgent → Claude 3.5 (reasoning)
   ├─ 🔬 CitationAgent    → doi_validator (CrossRef + arXiv)
   └─ ✍️  WritingAgent     → Claude 3.5 (full draft)
```

### Key Design Principles
- **Hallucination-Aware**: Every citation is verified against real APIs
- **Fallback-Ready**: If AWS is down, `USE_MOCK_LLM=true` lets you demo locally
- **Session Persistence**: DynamoDB (AWS) → local JSON fallback automatically
- **No Hardcoded Values**: All knobs in `.env` / `config.py`

---

## 📁 Project Structure

```
ai-research-coauthor/
├── app.py                  # Streamlit UI (hackathon demo)
├── config.py               # Config, AWS clients, Bedrock helpers
├── orchestrator.py         # 5-agent pipeline coordinator
├── prompts.py              # All LLM prompt templates
├── agents/
│   ├── base_agent.py       # Abstract BaseAgent (timing, error handling)
│   ├── discovery_agent.py  # Paper search + PDF parsing
│   ├── reviewer_agent.py   # Summarisation + gap analysis
│   ├── methodology_agent.py# Experimental design proposal
│   ├── citation_agent.py   # DOI verification + BibTeX
│   └── writing_agent.py    # Full paper assembly
├── tools/
│   ├── arxiv_search.py     # arXiv + Semantic Scholar APIs
│   ├── pdf_parser.py       # PDF download + text extraction
│   ├── doi_validator.py    # DOI/arXiv hallucination detection
│   └── rag_engine.py       # FAISS + Bedrock Titan RAG
├── memory/
│   └── session_manager.py  # DynamoDB / local JSON sessions
├── requirements.txt
└── .env.example
```

---

## 🔑 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | AWS credentials | — |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials | — |
| `AWS_DEFAULT_REGION` | Bedrock region | `us-east-1` |
| `BEDROCK_LLM_MODEL` | Claude model ID | `claude-3-5-sonnet-20241022-v2:0` |
| `BEDROCK_EMBED_MODEL` | Titan embed model | `amazon.titan-embed-text-v1` |
| `S3_BUCKET_NAME` | S3 bucket for drafts | `ai-research-coauthor-mvp` |
| `DYNAMODB_TABLE_NAME` | Session table | `research_sessions` |
| `MAX_PAPERS` | Papers to retrieve | `10` |
| `USE_MOCK_LLM` | Demo without AWS | `false` |

---

## 💡 Demo Topics (Try These)

- `"Large language models for automated code generation"`
- `"Federated learning for privacy-preserving healthcare AI"`
- `"Graph neural networks for drug discovery"`
- `"Transformer architectures for time series forecasting"`

---

## 🛡️ Anti-Hallucination Measures

1. **DOI Verification** – every citation checked against CrossRef API
2. **arXiv ID Validation** – papers with arXiv IDs verified against arXiv API
3. **Confidence Scoring** – each citation gets a 0–100% confidence score
4. **Hallucination Rate Dashboard** – real-time metric in the UI
5. **No Fabrication Prompts** – all LLM prompts explicitly forbid inventing citations

---

## 📊 Cost Estimate (AWS Bedrock)

| Per Session | Usage | Cost |
|-------------|-------|------|
| Claude 3.5 Sonnet | ~50K input + ~10K output tokens | ~$0.30 |
| Titan Embeddings | ~15K tokens | ~$0.002 |
| **Total** | | **~$0.30/session** |

---

*Built with ❤️ for AWS AI for Bharat Hackathon 2026*
