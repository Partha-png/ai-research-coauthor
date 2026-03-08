# 🔬 AI Research Co-Author

> **Multi-agent AI platform that turns a research topic into a citation-verified paper draft in minutes.**

Built for the **AWS AI for Bharat Hackathon 2026**. Powered by **AWS Bedrock** (Amazon Nova Lite LLM + Titan Embeddings) with a 5-agent pipeline, persistent sessions via **DynamoDB**, and file storage on **S3** — all deployed live on **AWS EC2**.

🌐 **Live Demo**: [http://44.221.85.33:8501](http://44.221.85.33:8501)  
💻 **GitHub**: [github.com/Partha-png/ai-research-coauthor](https://github.com/Partha-png/ai-research-coauthor)

---

## ✨ What It Does

1. **Discovers** 10–20 relevant papers from arXiv + Semantic Scholar
2. **Reviews** the literature with RAG-powered summaries and research gap analysis
3. **Proposes** a novel methodology grounded in existing research
4. **Verifies** every citation via DOI.org + arXiv APIs (detects hallucinated refs)
5. **Assembles** a full Markdown paper draft + BibTeX bibliography, uploaded to S3

---

## 🌟 Key Features

| Feature | Description |
|---|---|
| **5-Agent Pipeline** | Discovery → Review → Methodology → Citation → Writing |
| **RAG Engine** | FAISS + Titan Embeddings for context-aware generation |
| **Anti-Hallucination** | Every citation verified via CrossRef + arXiv APIs |
| **📈 Influence Tracking** | Semantic Scholar "Cited by" + References per paper |
| **✏️ Inline AI Editing** | Chat-style bar to edit any part of your draft via AI |
| **👤 User Accounts** | Username-based sessions, "My Projects" panel |
| **🔗 Share Links** | Read-only shareable URL for any completed session |
| **☁️ Cloud Storage** | Drafts + BibTeX auto-uploaded to S3, DynamoDB for sessions |
| **📄 PDF Upload** | Upload your own papers to include in the RAG pipeline |

---

## 🚀 Quick Start (Local)

```bash
# 1. Clone the repo
git clone https://github.com/Partha-png/ai-research-coauthor.git
cd ai-research-coauthor

# 2. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your AWS credentials

# 5. Launch
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Streamlit UI (app.py)                │
│  User Accounts • Live Progress • Share Links • Edit   │
└──────────────────────┬───────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────┐
│          Orchestrator (orchestrator.py)               │
│     Sequential 5-agent pipeline + session tracking    │
└──┬───────────────────────────────────────────────────┘
   │
   ├─ 🔍 DiscoveryAgent    → arXiv + Semantic Scholar APIs
   ├─ 📚 ReviewerAgent     → RAG Engine (FAISS + Titan Embeddings)
   ├─ ⚗️  MethodologyAgent  → Bedrock LLM (reasoning)
   ├─ 🔬 CitationAgent     → DOI validator (CrossRef + arXiv)
   └─ ✍️  WritingAgent      → Bedrock LLM (full draft) → S3 upload

         AWS Services
         ├── Amazon Bedrock    (LLM + Embeddings)
         ├── Amazon DynamoDB   (Session persistence)
         ├── Amazon S3         (Draft + BibTeX storage)
         └── Amazon EC2        (App hosting, 24/7)
```

---

## 📁 Project Structure

```
ai-research-coauthor/
├── app.py                   # Streamlit UI
├── config.py                # AWS clients, Bedrock helpers, auto-create resources
├── orchestrator.py          # 5-agent pipeline coordinator
├── prompts.py               # All LLM prompt templates
├── agents/
│   ├── base_agent.py        # Abstract BaseAgent (timing, error handling)
│   ├── discovery_agent.py   # Paper search + PDF parsing
│   ├── reviewer_agent.py    # Summarisation + gap analysis (RAG)
│   ├── methodology_agent.py # Experimental design proposal
│   ├── citation_agent.py    # DOI verification + BibTeX generation
│   └── writing_agent.py     # Full paper assembly + S3 upload
├── tools/
│   ├── arxiv_search.py      # arXiv + Semantic Scholar + influence tracking
│   ├── pdf_parser.py        # PDF download + text extraction
│   ├── doi_validator.py     # Hallucination detection
│   ├── rag_engine.py        # FAISS vector store + Titan Embeddings
│   └── s3_uploader.py       # S3 upload + pre-signed URL generation
├── memory/
│   └── session_manager.py   # DynamoDB / local JSON sessions + sharing
├── streamlit_app.service    # systemd service for EC2 auto-start
├── requirements.txt
└── .env.example
```

---

## 🔑 Environment Variables

| Variable | Description | Default |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | AWS credentials | — |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials | — |
| `AWS_DEFAULT_REGION` | Bedrock region | `us-east-1` |
| `BEDROCK_LLM_MODEL` | Bedrock LLM model ID | `us.amazon.nova-lite-v1:0` |
| `BEDROCK_EMBED_MODEL` | Titan embed model | `amazon.titan-embed-text-v1` |
| `S3_BUCKET_NAME` | S3 bucket for drafts | `ai-research-coauthor-mvp` |
| `DYNAMODB_TABLE_NAME` | Session table name | `research_sessions` |
| `MAX_PAPERS` | Papers to retrieve per run | `10` |
| `USE_MOCK_LLM` | Demo without AWS | `false` |

> DynamoDB table and S3 bucket are **auto-created on startup** if they don't exist.

---

## 🛡️ Anti-Hallucination Measures

1. **DOI Verification** — every citation checked against CrossRef API
2. **arXiv ID Validation** — papers with arXiv IDs verified against arXiv API
3. **Confidence Scoring** — each citation gets a 0–100% confidence score
4. **Hallucination Rate Dashboard** — real-time metric in the UI
5. **No Fabrication Prompts** — LLM prompts explicitly forbid inventing citations

---

## 📊 Performance & Cost

| Metric | Value |
|---|---|
| End-to-end pipeline time | ~3–5 minutes |
| Papers searched per run | 10 papers |
| RAG chunks indexed | ~50 chunks |
| Draft length | ~2,000–4,000 words |
| Cost per run (Nova Lite) | ~$0.01–0.03 |
| DynamoDB session save | <1 second |

| AWS Service | Usage | Est. Cost/Session |
|---|---|---|
| Amazon Bedrock (Nova Lite) | ~40K tokens in + ~10K out | ~$0.01 |
| Titan Embeddings | ~15K tokens | ~$0.002 |
| DynamoDB | 1 write + reads | ~$0.001 |
| S3 | ~100KB/session | ~$0.001 |
| **Total** | | **~$0.015/session** |

---

## 💡 Demo Topics

- `"Large language models for automated code generation"`
- `"Federated learning for privacy-preserving healthcare AI"`
- `"Graph neural networks for drug discovery"`
- `"Transformer architectures for time series forecasting"`
- `"Multimodal AI for medical image analysis"`

---

## 🚢 EC2 Deployment

```bash
# SSH into server
ssh -i "your-key.pem" ubuntu@44.221.85.33

# Update code after GitHub push
cd ai-research-coauthor && git pull && sudo systemctl restart streamlit_app

# View logs
sudo journalctl -u streamlit_app -f
```

The app runs as a **systemd service** — auto-starts on boot, auto-restarts on crash.

---

*Built with ❤️ for AWS AI for Bharat Hackathon 2026*
