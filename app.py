"""
app.py – Streamlit UI for the AI Research Co-Author platform.

Features:
  - Clear "How it works" onboarding in the sidebar
  - Live multi-agent progress tracking
  - Interactive paper list with verification badges
  - Full draft viewer with copy/download
  - Research gap explorer
  - BibTeX export
  - Session history sidebar
  - Hallucination rate metric dashboard
  - Detailed error display (no more silent "Draft not available")
"""

import sys
import time
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Page configuration (MUST be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Research Co-Author",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Share-link detection – load a shared session in read-only mode
# ─────────────────────────────────────────────────────────────────────────────
_share_id = st.query_params.get("share", "")
if _share_id and not st.session_state.get("result"):
    try:
        from memory.session_manager import SessionManager as _SM
        _shared_result = _SM().load_for_sharing(_share_id)
        if _shared_result:
            st.session_state.result = _shared_result
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS – premium dark theme
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --primary:   #6C63FF;
    --secondary: #00D4AA;
    --accent:    #FF6B6B;
    --bg:        #0F1117;
    --surface:   #1A1D2E;
    --surface2:  #252840;
    --text:      #E8EAF6;
    --muted:     #8B8FA8;
    --verified:  #00D4AA;
    --warn:      #FFB347;
    --danger:    #FF6B6B;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Main background ── */
.stApp { background: var(--bg); color: var(--text); }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid #2A2D45;
}

/* ── How it works steps ── */
.how-step {
    display: flex; align-items: flex-start; gap: 12px;
    background: #1A1D2E;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    border: 1px solid #2A2D45;
}
.how-step .num {
    background: var(--primary);
    color: white;
    border-radius: 50%;
    width: 24px; height: 24px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem; font-weight: 700;
    flex-shrink: 0;
}
.how-step .body { font-size: 0.82rem; color: var(--text); line-height: 1.4; }
.how-step .body b { color: var(--secondary); }
.how-step .body span { color: var(--muted); font-size: 0.78rem; }

/* ── Metric cards ── */
.metric-card {
    background: var(--surface2);
    border-radius: 12px;
    padding: 16px 20px;
    border: 1px solid #3A3D5C;
    text-align: center;
    margin-bottom: 8px;
}
.metric-card .value { font-size: 2rem; font-weight: 700; color: var(--primary); }
.metric-card .label { font-size: 0.75rem; color: var(--muted); margin-top: 4px; }

/* ── Paper card ── */
.paper-card {
    background: var(--surface);
    border-radius: 10px;
    padding: 14px 18px;
    border-left: 3px solid var(--primary);
    margin-bottom: 12px;
    transition: border-color 0.2s;
}
.paper-card.verified { border-left-color: var(--verified); }
.paper-card.unverified { border-left-color: var(--warn); }
.paper-card.hallucinated { border-left-color: var(--danger); }
.paper-card h4 { margin: 0 0 4px 0; font-size: 0.9rem; color: var(--text); }
.paper-card .meta { font-size: 0.75rem; color: var(--muted); }

/* ── Progress step ── */
.step-item {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 0; border-bottom: 1px solid #2A2D45;
    font-size: 0.85rem;
}
.step-item .icon { font-size: 1.1rem; min-width: 24px; }
.step-detail { color: var(--muted); font-size: 0.78rem; }

/* ── Badges ── */
.badge {
    display: inline-block; padding: 2px 8px; border-radius: 20px;
    font-size: 0.7rem; font-weight: 600; margin-left: 6px;
}
.badge-verified  { background: #00D4AA22; color: var(--verified); border: 1px solid var(--verified); }
.badge-unverified { background: #FFB34722; color: var(--warn); border: 1px solid var(--warn); }
.badge-hallucinated { background: #FF6B6B22; color: var(--danger); border: 1px solid var(--danger); }

/* ── Section headings ── */
h1 { color: var(--primary) !important; }
h2 { color: #C3C6E8 !important; border-bottom: 1px solid #2A2D45; padding-bottom: 6px; }
h3 { color: var(--secondary) !important; }

/* ── Code / draft area ── */
.draft-box {
    background: var(--surface2);
    border-radius: 10px;
    padding: 24px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    line-height: 1.7;
    white-space: pre-wrap;
    border: 1px solid #3A3D5C;
    max-height: 600px;
    overflow-y: auto;
}

/* ── Error card ── */
.error-card {
    background: #2A1A1A;
    border: 1px solid var(--danger);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
}
.error-card .err-title { color: var(--danger); font-weight: 600; font-size: 0.9rem; }
.error-card .err-detail { color: #C8A0A0; font-size: 0.8rem; margin-top: 4px; font-family: 'JetBrains Mono', monospace; }

/* ── Output preview box ── */
.output-preview {
    background: var(--surface);
    border-radius: 10px;
    padding: 14px 18px;
    border: 1px solid #2A2D45;
    margin-bottom: 10px;
    font-size: 0.82rem;
    color: var(--muted);
}
.output-preview .title { color: var(--secondary); font-weight: 600; margin-bottom: 4px; font-size: 0.85rem; }

/* ── Hero cards ── */
.hero-card {
    background: var(--surface);
    border-radius: 12px;
    padding: 20px 24px;
    border: 1px solid #2A2D45;
    text-align: center;
    min-width: 150px;
    flex: 1;
}
.hero-card .icon { font-size: 2rem; margin-bottom: 8px; }
.hero-card .label { color: var(--primary); font-weight: 600; font-size: 0.9rem; }
.hero-card .sub { color: var(--muted); font-size: 0.75rem; margin-top: 4px; }

/* ── Primary button ── */
.stButton > button {
    background: linear-gradient(135deg, var(--primary), #8B5CF6) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 10px 28px !important;
    font-size: 1rem !important;
    transition: transform 0.15s, box-shadow 0.15s !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 24px #6C63FF55 !important;
}

/* ── Progress bar ── */
.stProgress > div > div { background: var(--primary) !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab"] { color: var(--muted); }
.stTabs [data-baseweb="tab"][aria-selected="true"] { color: var(--primary); border-bottom-color: var(--primary); }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Session state defaults
# ─────────────────────────────────────────────────────────────────────────────
DEFAULTS = {
    "running": False,
    "result": None,
    "progress_steps": [],
    "error": None,
    "session_id": None,
    "uploaded_papers": [],      # parsed paper dicts from user uploads
    "upload_summary": [],       # brief metadata for UI display
    "username": "anonymous",    # current user account name
    "edit_result": None,        # AI-edited section text
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown("# 🔬")
with col_title:
    st.markdown("# AI Research Co-Author")
    st.markdown(
        "<p style='color:#8B8FA8;margin-top:-14px;'>Multi-Agent Platform · Citation-Grounded · Hallucination-Aware</p>",
        unsafe_allow_html=True,
    )

st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar – How it works + Configuration + Upload + History
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:

    # ── USER ACCOUNT ────────────────────────────────────────────────
    st.markdown("### 👤 Your Account")
    _uname_input = st.text_input(
        "Username",
        value=st.session_state.username,
        placeholder="Enter your name",
        label_visibility="collapsed",
        key="username_input",
        help="Set your name to track and share your research sessions.",
    )
    if _uname_input.strip():
        st.session_state.username = _uname_input.strip()
    st.caption(f"👋 Welcome, **{st.session_state.username}**!")
    st.markdown("---")

    # ── HOW IT WORKS ────────────────────────────────────────────────
    st.markdown("### 💡 How It Works")
    st.markdown("""
<div class="how-step">
  <div class="num">1</div>
  <div class="body">
    <b>Type a research topic</b><br>
    <span>e.g. "Medical chatbot using RAG" or "Transformer models for drug discovery"</span>
  </div>
</div>
<div class="how-step">
  <div class="num">2</div>
  <div class="body">
    <b>Click Generate Research Paper</b><br>
    <span>5 AI agents will discover papers, review literature, design a methodology, verify citations, and write a full draft</span>
  </div>
</div>
<div class="how-step">
  <div class="num">3</div>
  <div class="body">
    <b>Download your paper</b><br>
    <span>You get a complete Markdown draft with Abstract, Introduction, Related Work, Methodology, Conclusion + BibTeX references</span>
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    # ── CONFIGURATION ───────────────────────────────────────────────
    st.markdown("### ⚙️ Configuration")

    topic = st.text_area(
        "Research Topic",
        placeholder="e.g. Large language models for code generation",
        height=90,
        key="topic_input",
        help="Enter the research topic you want a paper written about. Be specific — good topics include the problem domain and technique.",
    )

    col1, col2 = st.columns(2)
    with col1:
        max_papers = st.slider(
            "Max Papers", 5, 20, 10,
            help="Number of academic papers the AI will discover and analyse. More papers = better coverage but slower run."
        )
    with col2:
        output_format = st.selectbox(
            "Citation Format",
            ["IEEE", "ACM", "APA", "MLA"],
            help="Citation style for the References section and BibTeX output."
        )

    # ── UPLOAD YOUR OWN PAPERS ──────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📎 Add Your Own Papers *(Optional)*")
    st.caption(
        "Upload any PDF or TXT papers you already have. "
        "They'll be added to the AI's knowledge base alongside papers it discovers automatically from arXiv and Semantic Scholar."
    )

    uploaded_files = st.file_uploader(
        "Drop your research papers here",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        key="paper_uploader",
        label_visibility="collapsed",
    )

    if uploaded_files:
        from tools.pdf_parser import parse_uploaded_pdf
        parsed_papers = []
        summary_lines = []
        with st.spinner("Parsing uploaded files…"):
            for uf in uploaded_files:
                try:
                    paper = parse_uploaded_pdf(uf.read(), uf.name)
                    parsed_papers.append(paper)
                    summary_lines.append({
                        "filename": uf.name,
                        "title": paper["title"],
                        "chars": len(paper.get("full_text", "")),
                    })
                except Exception as exc:
                    st.warning(f"Could not parse {uf.name}: {exc}")
        st.session_state.uploaded_papers = parsed_papers
        st.session_state.upload_summary = summary_lines

    # Show parsed file list
    if st.session_state.upload_summary:
        st.markdown("**Queued for analysis:**")
        for s in st.session_state.upload_summary:
            st.markdown(
                f"<div style='background:#1A1D2E;border-radius:8px;padding:8px 12px;"
                f"border-left:3px solid #00D4AA;margin-bottom:6px;font-size:0.8rem'>"
                f"📄 <b>{s['filename']}</b><br>"
                f"<span style='color:#8B8FA8'>{s['title'][:60]}{'…' if len(s['title']) > 60 else ''} · {s['chars']:,} chars</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        if st.button("🗑️ Clear uploads", key="clear_uploads"):
            st.session_state.uploaded_papers = []
            st.session_state.upload_summary = []
            st.rerun()

    elif not uploaded_files:
        st.markdown(
            "<div style='color:#8B8FA8;font-size:0.8rem;text-align:center;padding:8px;border:1px dashed #2A2D45;border-radius:8px'>"
            "No files uploaded — pipeline will search arXiv + Semantic Scholar automatically"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### 🧠 Agent Pipeline")
    agents_info = [
        ("🔍", "Discovery",    "arXiv + Semantic Scholar search"),
        ("📚", "Reviewer",     "Summarise papers + find gaps"),
        ("⚗️",  "Methodology", "Design experimental approach"),
        ("🔬", "Citation",     "Verify DOIs + arXiv IDs"),
        ("✍️", "Writing",      "Assemble full paper draft"),
    ]
    for icon, name, desc in agents_info:
        st.markdown(f"{icon} **{name}** – <span style='color:#8B8FA8;font-size:0.8rem'>{desc}</span>", unsafe_allow_html=True)

    st.markdown("---")

    # ── MY PROJECTS ────────────────────────────────────────────────
    st.markdown("### 📂 My Projects")
    try:
        from memory.session_manager import SessionManager
        _sm = SessionManager()
        _my_sessions = _sm.list_sessions_for_user(st.session_state.username, limit=8)
        if _my_sessions:
            for _s in _my_sessions:
                _col1, _col2 = st.columns([4, 1])
                _status_e = "✅" if _s.get("status") == "completed" else "🔄"
                with _col1:
                    st.caption(f"{_status_e} {_s.get('topic','')[:35]}…")
                with _col2:
                    if st.button("Load", key=f"load_{_s['session_id']}", use_container_width=True):
                        _shared = _sm.load_for_sharing(_s["session_id"])
                        if _shared:
                            st.session_state.result = _shared
                            st.rerun()
        else:
            st.caption(f"No projects yet for **{st.session_state.username}**")
    except Exception:
        st.caption("Project history unavailable")


# ─────────────────────────────────────────────────────────────────────────────
# Run pipeline button
# ─────────────────────────────────────────────────────────────────────────────
run_col, _ = st.columns([2, 5])
with run_col:
    run_clicked = st.button(
        "🚀 Generate Research Paper",
        disabled=st.session_state.running,
        use_container_width=True,
    )

if run_clicked:
    if not topic or len(topic.strip()) < 10:
        st.warning("⚠️ Please enter a research topic (at least 10 characters).")
    else:
        st.session_state.running = True
        st.session_state.result = None
        st.session_state.progress_steps = []
        st.session_state.error = None

        TOTAL_STEPS = 25
        step_count = [0]

        with st.status("🔬 Running research pipeline…", expanded=True) as status_box:
            progress_bar = st.progress(0)

            def progress_cb(step: str, detail: str = ""):
                step_count[0] += 1
                st.session_state.progress_steps.append((step, detail))
                progress_bar.progress(min(step_count[0] / TOTAL_STEPS, 0.97))
                if detail:
                    status_box.write(f"{step} — {detail}")
                else:
                    status_box.write(step)

            try:
                from orchestrator import ResearchPipeline
                pipeline = ResearchPipeline(progress_callback=progress_cb)
                result = pipeline.run(
                    topic=topic.strip(),
                    max_papers=max_papers,
                    output_format=output_format,
                    uploaded_papers=st.session_state.uploaded_papers or None,
                    username=st.session_state.username,
                )
                st.session_state.result = result
                progress_bar.progress(1.0)
                status_box.update(label="✅ Pipeline complete!", state="complete", expanded=False)
            except Exception as exc:
                import traceback
                st.session_state.error = traceback.format_exc()
                status_box.update(label=f"❌ Pipeline failed: {exc}", state="error", expanded=True)

        st.session_state.running = False
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Results Panel
# ─────────────────────────────────────────────────────────────────────────────
result = st.session_state.result

if result:
    metrics = result.get("metrics", {})
    agent_errors = result.get("agent_errors", [])

    st.markdown("---")
    st.markdown("## 📊 Pipeline Results")

    # ── Agent error banner ───────────────────────────────────────────
    if agent_errors:
        st.markdown(
            "<div style='background:#2A1A1A;border:1px solid #FF6B6B;border-radius:10px;padding:14px 18px;margin-bottom:16px'>"
            "<div style='color:#FF6B6B;font-weight:700;font-size:0.9rem;margin-bottom:8px'>⚠️ Some agents encountered errors (pipeline continued with fallbacks)</div>"
            + "".join(
                f"<div style='color:#C8A0A0;font-size:0.8rem;font-family:monospace;padding:3px 0'>"
                f"❌ <b>{e['agent'].capitalize()}</b>: {e['error'][:150]}</div>"
                for e in agent_errors
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    # ── Metric cards row ─────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    uploaded_count = metrics.get("uploaded_papers_count", 0)
    papers_label = f"Papers Found" + (f" (+{uploaded_count} 📎)" if uploaded_count else "")
    metric_data = [
        (m1, metrics.get("papers_retrieved", 0), papers_label),
        (m2, metrics.get("papers_summarised", 0), "Papers Summarised"),
        (m3, metrics.get("citations_verified", 0), "Citations Verified"),
        (m4, f"{metrics.get('hallucination_rate_pct', 0):.1f}%", "Hallucination Rate"),
        (m5, f"~{metrics.get('word_count', 0):,}", "Draft Word Count"),
    ]
    for col, value, label in metric_data:
        with col:
            st.markdown(
                f"<div class='metric-card'>"
                f"<div class='value'>{value}</div>"
                f"<div class='label'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    timing = metrics.get("total_time_seconds", 0)

    # Shared session read-only banner
    if result.get("_shared"):
        st.markdown(
            f"<div style='background:#1A1D2E;border:1px solid #00D4AA;border-radius:10px;"
            f"padding:10px 18px;margin-bottom:12px;color:#00D4AA;font-size:0.88rem'>"
            f"👁️ <b>Read-only view</b> — shared session by <b>@{result.get('_shared_by','?')}</b>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.caption(f"⏱️ Total pipeline time: **{timing}s** | Session: `{metrics.get('session_id', '')[:8]}…`")

    # Share button
    _sid = metrics.get("session_id", "")
    if _sid and not result.get("_shared"):
        _share_url = f"?share={_sid}"
        st.markdown(
            f"<a href='{_share_url}' target='_blank' style='"
            f"display:inline-block;background:#252840;border:1px solid #3A3D5C;color:#8B8FA8;"
            f"padding:4px 14px;border-radius:8px;text-decoration:none;"
            f"font-size:0.8rem;margin-bottom:8px'>🔗 Share this paper (read-only link)</a>",
            unsafe_allow_html=True,
        )

    # ── Tabs ─────────────────────────────────────────────────────────
    # ── S3 links banner ────────────────────────────────
    s3_draft_url  = metrics.get('s3_draft_url')
    s3_bibtex_url = metrics.get('s3_bibtex_url')
    if s3_draft_url or s3_bibtex_url:
        links_html = ''
        if s3_draft_url:
            links_html += (
                f"<a href='{s3_draft_url}' target='_blank' style='"
                f"background:#6C63FF22;border:1px solid #6C63FF;color:#6C63FF;"
                f"padding:6px 16px;border-radius:8px;text-decoration:none;"
                f"font-weight:600;font-size:0.85rem;margin-right:12px'>"
                f"☁️ Download Draft from S3 ↗️</a>"
            )
        if s3_bibtex_url:
            links_html += (
                f"<a href='{s3_bibtex_url}' target='_blank' style='"
                f"background:#00D4AA22;border:1px solid #00D4AA;color:#00D4AA;"
                f"padding:6px 16px;border-radius:8px;text-decoration:none;"
                f"font-weight:600;font-size:0.85rem'>"
                f"☁️ Download BibTeX from S3 ↗️</a>"
            )
        st.markdown(
            f"<div style='margin:12px 0 4px;'>{links_html}</div>",
            unsafe_allow_html=True,
        )

    tabs = st.tabs([
        "📄 Full Draft",
        "📚 Papers Found",
        "🔭 Research Gaps",
        "🔬 Citation Audit",
        "📝 BibTeX",
    ])

    # ── Tab 1: Full Draft ─────────────────────────────────────────────
    with tabs[0]:
        draft = result.get("full_draft_markdown", "")
        if draft and len(draft.strip()) > 50:
            col_view, col_btn, col_s3 = st.columns([4, 1, 1])
            with col_btn:
                st.download_button(
                    "⬇️ Download .md",
                    data=draft,
                    file_name=f"research_paper_{result['metrics']['session_id'][:8]}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with col_s3:
                _s3u = metrics.get('s3_draft_url')
                if _s3u:
                    st.markdown(
                        f"<a href='{_s3u}' target='_blank' style='display:block;text-align:center;"
                        f"background:#6C63FF22;border:1px solid #6C63FF;color:#6C63FF;"
                        f"padding:6px 8px;border-radius:8px;text-decoration:none;"
                        f"font-size:0.8rem;font-weight:600;margin-top:4px'>☁️ S3 Link</a>",
                        unsafe_allow_html=True,
                    )
            st.markdown("---")
            # Render nicely
            st.markdown(draft)
        else:
            # Explain why the draft is unavailable with actionable detail
            st.markdown(
                "<div style='background:#1A1D2E;border:1px solid #FFB347;border-radius:10px;padding:20px;'>"
                "<div style='color:#FFB347;font-weight:700;font-size:1rem;margin-bottom:10px'>⚠️ Draft could not be generated</div>"
                "<div style='color:#C3C6E8;font-size:0.86rem;line-height:1.6'>"
                "<b>Most common causes:</b><ul style='margin-top:8px'>"
                "<li>The writing agent failed (check the error banner above)</li>"
                "<li>No papers were successfully summarised (Papers Summarised = 0)</li>"
                "<li>The research topic returned no results from arXiv / Semantic Scholar</li>"
                "</ul>"
                "<b>Quick fixes:</b><ul style='margin-top:8px'>"
                "<li>Try a different or broader research topic</li>"
                "<li>Upload a PDF of a related paper to give the AI a head start</li>"
                "<li>Check the Papers Found and Research Gaps tabs for partial results</li>"
                "</ul></div></div>",
                unsafe_allow_html=True,
            )

            # Show partial sections if writing agent produced anything
            abstract = result.get("abstract", "")
            introduction = result.get("introduction", "")
            if abstract or introduction:
                st.markdown("### Partial output recovered:")
                if abstract:
                    with st.expander("Abstract"):
                        st.markdown(abstract)
                if introduction:
                    with st.expander("Introduction"):
                        st.markdown(introduction)

        # ── AI Chat-Edit bar (ChatGPT-style, bottom of Full Draft tab) ──
        _has_draft = draft and len(draft.strip()) > 50
        if _has_draft and not result.get('_shared'):
            st.markdown("---")
            st.markdown(
                "<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px'>"
                "<span style='font-size:1.1rem'>✨</span>"
                "<span style='color:#8B8FA8;font-size:0.82rem;font-weight:600'>AI Draft Editor</span>"
                "<span style='color:#3A3D5C;font-size:0.78rem'> — type an instruction and press Enter or click Send</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            # Use st.form so the text_input value is captured correctly at submit time
            with st.form(key='draft_edit_form', clear_on_submit=True):
                _form_col, _btn_col = st.columns([8, 1])
                with _form_col:
                    _edit_prompt = st.text_input(
                        'edit_instruction',
                        placeholder='✍️ e.g. “Make the introduction more concise”  ·  “Expand methodology with more detail”  ·  “Make the tone more formal”',
                        label_visibility='collapsed',
                    )
                with _btn_col:
                    _send = st.form_submit_button('↑ Send', use_container_width=True)
            # Process AFTER the form closes — _edit_prompt still holds the value
            if _send and _edit_prompt and _edit_prompt.strip():
                _instr = _edit_prompt.strip()
                with st.spinner(f'Applying: "{_instr[:60]}"...'):
                    try:
                        from config import invoke_claude
                        import re as _re

                        # ── Step 1: detect which section the instruction targets ──────
                        _headings = _re.findall(r'^#{1,3} .+', draft, flags=_re.MULTILINE)
                        _headings_list = '\n'.join(f'- {h}' for h in _headings[:20])
                        _section_prompt = (
                            f'The user wants to edit a research paper with this instruction:\n'
                            f'"{_instr}"\n\n'
                            f'The paper has these sections:\n{_headings_list}\n\n'
                            f'Which ONE section heading does the instruction target? '
                            f'Reply with ONLY the exact heading text (e.g. "## Abstract"). '
                            f'If it applies to the whole paper, reply with WHOLE.'
                        )
                        _target = invoke_claude(_section_prompt, max_tokens=60, temperature=0.0).strip()

                        if _target == 'WHOLE' or not _headings:
                            # ── whole-draft edit (global instruction) ──────────────
                            _new_draft = invoke_claude(
                                f'Instruction: {_instr}\n\n--- FULL DRAFT ---\n{draft}',
                                system=(
                                    'You are an academic writing assistant. '
                                    'Apply the instruction to the ENTIRE paper. '
                                    'Return the COMPLETE updated draft — do NOT omit or truncate any section.'
                                ),
                                max_tokens=8000,
                                temperature=0.3,
                            )
                        else:
                            # ── section-targeted edit ──────────────────────────────
                            _h_clean = _target.lstrip('#').strip()
                            _pat = _re.compile(
                                r'(#{1,3}\s+' + _re.escape(_h_clean) + r'.*?)(?=\n#{1,3} |\Z)',
                                _re.DOTALL | _re.IGNORECASE,
                            )
                            _match = _pat.search(draft)
                            if _match:
                                _section_text = _match.group(1)
                                _section_edited = invoke_claude(
                                    f'Instruction: {_instr}\n\nEdit ONLY this section:\n\n{_section_text}',
                                    system=(
                                        'You are an academic writing assistant. '
                                        'Edit the given section per the instruction. '
                                        'Preserve the Markdown heading. '
                                        'Return ONLY the updated section — nothing else.'
                                    ),
                                    max_tokens=2000,
                                    temperature=0.3,
                                )
                                # Splice edited section back into the full draft
                                _new_draft = draft[:_match.start()] + _section_edited.strip() + '\n' + draft[_match.end():]
                            else:
                                # heading not matched — fall back to whole-draft edit
                                _new_draft = invoke_claude(
                                    f'Instruction: {_instr}\n\n--- FULL DRAFT ---\n{draft}',
                                    system='Apply the instruction and return the COMPLETE updated draft.',
                                    max_tokens=8000,
                                    temperature=0.3,
                                )

                        # Safety: if output is <40% of original, something went wrong
                        if len(_new_draft.strip()) < len(draft.strip()) * 0.4:
                            st.warning(
                                '⚠️ The AI returned a much shorter response than expected — '
                                'the original draft has been preserved. Try rephrasing your instruction.'
                            )
                        else:
                            st.session_state.result['full_draft_markdown'] = _new_draft
                            st.session_state.setdefault('draft_chat_history', []).append(_instr)
                            st.success(f'✅ Applied: "{_instr[:80]}"')
                            st.rerun()
                    except Exception as _exc:
                        st.error(f'Edit failed: {_exc}')
            # Chat history
            _hist = st.session_state.get('draft_chat_history', [])
            if _hist:
                with st.expander(f"💬 Edit history ({len(_hist)} edits)", expanded=False):
                    for _i, _h in enumerate(reversed(_hist), 1):
                        st.markdown(
                            f"<div style='background:#1A1D2E;border-left:3px solid #6C63FF;"
                            f"border-radius:6px;padding:8px 12px;margin-bottom:6px;font-size:0.82rem'>"
                            f"✏️ <b>Edit {_i}:</b> {_h}</div>",
                            unsafe_allow_html=True,
                        )
                    if st.button('🗑️ Clear edit history', key='clear_edit_hist'):
                        st.session_state.draft_chat_history = []
                        st.rerun()

    # ── Tab 2: Papers Found ───────────────────────────────────────────
    with tabs[1]:
        papers = result.get("papers", [])
        summaries = result.get("summaries", [])
        summary_map = {s.get("paper_id", ""): s for s in summaries}

        if papers:
            uploaded_cnt = sum(1 for p in papers if p.get("is_uploaded"))
            disc_cnt = len(papers) - uploaded_cnt
            label_parts = []
            if disc_cnt:  label_parts.append(f"{disc_cnt} discovered from arXiv / Semantic Scholar")
            if uploaded_cnt: label_parts.append(f"{uploaded_cnt} uploaded by you 📎")
            st.markdown(f"**{len(papers)} papers total** · {' + '.join(label_parts)}")
            st.caption("Papers are used by the AI to write the literature review, propose the methodology, and generate citations.")
            st.markdown("---")
            for paper in papers:
                is_uploaded = paper.get("is_uploaded", False)
                verified = paper.get("verified")
                conf = paper.get("confidence", 0.5)

                if is_uploaded:
                    badge_cls, badge_txt = "verified", "📎 Your Upload"
                elif verified is True:
                    badge_cls, badge_txt = "verified", "✓ Verified"
                elif verified is False:
                    badge_cls, badge_txt = "hallucinated", "✗ Flagged"
                else:
                    badge_cls, badge_txt = "unverified", "? Unconfirmed"

                summary_obj = summary_map.get(paper.get("id", ""), {})
                summary_txt = summary_obj.get("summary", paper.get("abstract", ""))[:200]

                authors_str = ", ".join(paper.get("authors", [])[:3])
                if len(paper.get("authors", [])) > 3:
                    authors_str += " et al."

                arxiv_link = ""
                if paper.get("arxiv_id"):
                    arxiv_link = f'<a href="https://arxiv.org/abs/{paper["arxiv_id"]}" target="_blank" style="color:#6C63FF">📎 arXiv</a>'

                with st.expander("📈 Influence — Cited by & References"):
                    with st.spinner("Loading influence data..."):
                        from tools.arxiv_search import get_paper_influence
                        _inf = get_paper_influence(paper)
                    _c1, _c2 = st.columns(2)
                    with _c1:
                        st.markdown("**Cited by:**")
                        if _inf['cited_by']:
                            for _cp in _inf['cited_by']:
                                st.markdown(f"- {_cp['title'][:70]} *({_cp['year']})* — {_cp['citation_count']:,} citations")
                        else:
                            st.caption("No citing papers found")
                    with _c2:
                        st.markdown("**References:**")
                        if _inf['references']:
                            for _rp in _inf['references']:
                                st.markdown(f"- {_rp['title'][:70]} *({_rp['year']})*")
                        else:
                            st.caption("No references found")

                st.markdown(
                    f"<div class='paper-card {badge_cls}'>"
                    f"<h4>{paper.get('title', 'Unknown')} <span class='badge badge-{badge_cls}'>{badge_txt}</span></h4>"
                    f"<div class='meta'>{authors_str} · {paper.get('year', '?')} · "
                    f"📖 {paper.get('citation_count', 0)} citations · {arxiv_link}</div>"
                    f"<p style='font-size:0.82rem;color:#C3C6E8;margin-top:8px'>{summary_txt}{'…' if summary_txt else ''}</p>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No papers found. Try a different or broader research topic.")

    # ── Tab 3: Research Gaps ──────────────────────────────────────────
    with tabs[2]:
        gaps = result.get("gaps", "")
        if gaps and gaps != "No papers available for analysis.":
            st.markdown("### 🔭 Identified Research Gaps")
            st.caption("These are areas the AI identified as under-explored based on the papers it read. They form the basis for the proposed methodology.")
            st.markdown("---")
            st.markdown(gaps)
        else:
            st.info("Gap analysis is not available. This usually means no papers were summarised — check the error banner.")

    # ── Tab 4: Citation Audit ─────────────────────────────────────────
    with tabs[3]:
        st.caption("The Citation Agent verifies each paper against live arXiv and DOI databases to detect hallucinated references.")
        citation_stats = result.get("citation_stats", {})
        if citation_stats:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total", citation_stats.get("total_papers", 0))
            c2.metric("✅ Verified", citation_stats.get("verified", 0))
            c3.metric("⚠️ Unconfirmed", citation_stats.get("unverified", 0))
            c4.metric("❌ Hallucinated", citation_stats.get("hallucinated", 0))

            rate = citation_stats.get("hallucination_rate_pct", 0)
            color = "#00D4AA" if rate < 5 else ("#FFB347" if rate < 15 else "#FF6B6B")
            st.markdown(
                f"<p style='color:{color};font-weight:700;font-size:1.1rem'>"
                f"Hallucination Rate: {rate:.1f}%</p>",
                unsafe_allow_html=True,
            )
            if rate < 5:
                st.success("✅ Excellent citation accuracy!")
            elif rate < 15:
                st.warning("⚠️ Some citations could not be verified.")
            else:
                st.error("❌ High hallucination rate – review citations manually.")

        validated_papers = result.get("validated_papers", [])
        if validated_papers:
            st.markdown("### Per-Paper Verification")
            for p in validated_papers:
                v = p.get("verified")
                icon = "✅" if v is True else ("❌" if v is False else "⚠️")
                reason = p.get("verify_reason", "")
                conf_pct = int(p.get("confidence", 0.5) * 100)
                st.markdown(
                    f"{icon} **{p.get('title', 'Unknown')[:70]}** — "
                    f"Confidence: `{conf_pct}%` – {reason}"
                )
        elif not citation_stats:
            st.info("Citation audit data not available.")

    # ── Tab 5: BibTeX ─────────────────────────────────────────────────
    with tabs[4]:
        bibtex = result.get("bibtex", "")
        if bibtex:
            st.caption("Copy this BibTeX into your LaTeX editor or reference manager (Zotero, Mendeley, Overleaf, etc.)")
            _s3_bib = metrics.get('s3_bibtex_url')
            if _s3_bib:
                st.markdown(
                    f"<a href='{_s3_bib}' target='_blank' style='"
                    f"display:inline-block;background:#00D4AA22;border:1px solid #00D4AA;"
                    f"color:#00D4AA;padding:5px 14px;border-radius:8px;"
                    f"text-decoration:none;font-size:0.82rem;font-weight:600;margin-bottom:10px'>"
                    f"☁️ Download BibTeX from S3 ↗️</a>",
                    unsafe_allow_html=True,
                )
            st.code(bibtex, language="bibtex")
            st.download_button(
                "⬇️ Download .bib",
                data=bibtex,
                file_name=f"references_{result['metrics']['session_id'][:8]}.bib",
                mime="text/plain",
            )
        else:
            st.info("No BibTeX available — the citation agent may not have run.")


elif st.session_state.error:
    st.error("Pipeline failed. See details below:")
    with st.expander("Error traceback"):
        st.code(st.session_state.error)

else:
    # ── Landing / empty state ─────────────────────────────────────────
    st.markdown("""
<div style='text-align:center;padding:40px 20px 20px;'>
  <div style='font-size:4rem;margin-bottom:16px'>🔬</div>
  <h2 style='color:#C3C6E8;border:none'>Your AI-Powered Research Co-Author</h2>
  <p style='color:#8B8FA8;max-width:600px;margin:auto;font-size:1.05rem;line-height:1.7'>
    Type a research topic in the sidebar → click <b style='color:#6C63FF'>Generate Research Paper</b>.<br>
    Five AI agents will search academic databases, review the literature, design a methodology,
    verify every citation, and write a complete paper draft — all in a few minutes.
  </p>
</div>
""", unsafe_allow_html=True)

    # IO explanation cards
    col_in, col_arrow, col_out = st.columns([5, 1, 5])
    with col_in:
        st.markdown("""
<div style='background:#1A1D2E;border-radius:12px;padding:20px 24px;border:1px solid #2A2D45;'>
  <div style='color:#00D4AA;font-weight:700;font-size:1rem;margin-bottom:12px'>📥 What You Give</div>
  <div style='color:#C3C6E8;font-size:0.88rem;line-height:1.8'>
    ✏️ <b>Research topic</b> — a short description of what you want the paper to be about<br><br>
    📄 <b>Your own papers</b> <span style='color:#8B8FA8'>(optional)</span> — upload PDFs you've already collected; they'll be included in the analysis<br><br>
    🔢 <b>Max papers</b> — how many papers to search (5–20)<br><br>
    📑 <b>Citation format</b> — IEEE, ACM, APA, or MLA
  </div>
</div>
""", unsafe_allow_html=True)

    with col_arrow:
        st.markdown("<div style='text-align:center;padding-top:80px;font-size:2rem;color:#6C63FF'>→</div>", unsafe_allow_html=True)

    with col_out:
        st.markdown("""
<div style='background:#1A1D2E;border-radius:12px;padding:20px 24px;border:1px solid #2A2D45;'>
  <div style='color:#6C63FF;font-weight:700;font-size:1rem;margin-bottom:12px'>📤 What You Get</div>
  <div style='color:#C3C6E8;font-size:0.88rem;line-height:1.8'>
    📄 <b>Full paper draft</b> — Abstract, Introduction, Related Work, Methodology, Limitations, Future Work, Conclusion<br><br>
    📚 <b>Papers found</b> — list of academic papers discovered and analysed, with summaries<br><br>
    🔭 <b>Research gaps</b> — what the AI identified as under-explored in the field<br><br>
    📎 <b>BibTeX file</b> — verified references ready to import into LaTeX / Zotero
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Agent pipeline visual
    st.markdown("<p style='text-align:center;color:#8B8FA8;font-size:0.85rem;margin-bottom:16px'>The 5 agents that run when you click Generate:</p>", unsafe_allow_html=True)
    a1, a2, a3, a4, a5 = st.columns(5)
    for col, icon, name, desc in [
        (a1, "🔍", "Discovery",    "arXiv + Semantic Scholar"),
        (a2, "📚", "Review",       "Summarise + find gaps"),
        (a3, "⚗️",  "Methodology", "Experimental design"),
        (a4, "🔬", "Citation",     "DOI/arXiv validation"),
        (a5, "✍️", "Writing",      "Full draft assembly"),
    ]:
        with col:
            st.markdown(
                f"<div class='hero-card'>"
                f"<div class='icon'>{icon}</div>"
                f"<div class='label'>{name}</div>"
                f"<div class='sub'>{desc}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
