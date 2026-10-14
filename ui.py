"""
Universal Intelligence & Responsible AI (UIRA) — Graphical Interface
====================================================================
Streamlit workspace connecting:
  - Evidence-grounded Chat & Multidisciplinary Synthesis
  - Local Knowledge Persistence & Document Library (PDF/TXT/MD)
  - Live Web Search & Academic Literature Research (OpenAlex/Crossref)
  - System Diagnostics and Model Controls

Run locally:
    streamlit run ui.py
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration & Page Setup
# ---------------------------------------------------------------------------

API_URL = os.getenv("UNIVERSAL_AI_API", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(
    page_title="Universal Intelligence & Responsible AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .block-container { max-width: 1300px; padding-top: 1.5rem; }
    [data-testid="stSidebar"] { border-right: 1px solid rgba(128, 128, 128, 0.2); }
    .main-title { font-size: 2.1rem; font-weight: 700; margin-bottom: 0.2rem; }
    .subtitle { color: #888; font-size: 1.05rem; margin-bottom: 1.5rem; }
    .source-card {
        border-left: 3px solid #4A90E2;
        background-color: rgba(74, 144, 226, 0.05);
        padding: 0.75rem 1rem;
        margin-bottom: 0.6rem;
        border-radius: 0 6px 6px 0;
    }
    .badge {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        font-size: 0.75rem;
        font-weight: 600;
        border-radius: 4px;
        margin-right: 0.5rem;
    }
    .badge-knowledge { background-color: #2E7D32; color: white; }
    .badge-web { background-color: #0277BD; color: white; }
    .badge-paper { background-color: #6A1B9A; color: white; }
    .metric-box {
        background-color: rgba(128, 128, 128, 0.08);
        border-radius: 8px;
        padding: 0.9rem;
        text-align: center;
        border: 1px solid rgba(128, 128, 128, 0.15);
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# API Client Helper
# ---------------------------------------------------------------------------

def api_request(method: str, path: str, **kwargs) -> tuple[Any, str | None]:
    """Execute HTTP request against the Universal AI backend."""
    url = f"{API_URL}{path}"
    try:
        resp = requests.request(method, url, timeout=kwargs.pop("timeout", 60), **kwargs)
        if resp.status_code >= 400:
            try:
                err_detail = resp.json().get("detail", resp.text)
            except Exception:
                err_detail = resp.text
            return None, f"HTTP {resp.status_code}: {err_detail}"
        return resp.json(), None
    except requests.exceptions.ConnectionError:
        return None, f"Could not connect to backend at {API_URL}. Ensure 'uvicorn app:app' is running."
    except requests.exceptions.Timeout:
        return None, "Request timed out after 60 seconds."
    except Exception as exc:
        return None, str(exc)


@st.cache_data(ttl=5)
def get_health() -> tuple[dict[str, Any] | None, str | None]:
    """Check backend health and metrics."""
    return api_request("GET", "/health", timeout=3)


@st.cache_data(ttl=5)
def get_document_list() -> tuple[list[dict[str, Any]], str | None]:
    """Fetch indexed documents."""
    data, err = api_request("GET", "/documents", timeout=5)
    if err or not data:
        return [], err
    return data.get("documents", []), None


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []


# ---------------------------------------------------------------------------
# Sidebar: Controls & System Diagnostics
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🧠 UIRA System")
    st.caption("Universal Intelligence & Responsible AI")

    # Backend Connection Status
    health_data, health_err = get_health()
    if health_data and health_data.get("status") == "healthy":
        st.success("🟢 Backend Active", icon="✅")
        db_info = health_data.get("database", {})
        st.markdown(f"**Model:** `{health_data.get('model_name', 'default')}`")
        st.markdown(f"**Docs Indexed:** {db_info.get('documents_indexed', 0)} ({db_info.get('chunks_indexed', 0)} chunks)")
        st.markdown(f"**Web Search:** {'✅ Available' if health_data.get('web_search_available') else '⚠️ Offline / Fallback'}")
        st.markdown(f"**Academic Search:** {'✅ OpenAlex + Crossref' if health_data.get('academic_search_available') else '⚠️ Unavailable'}")
    else:
        st.error("🔴 Backend Offline", icon="⚠️")
        st.caption(f"Cannot reach `{API_URL}`. Start backend with:\n`uvicorn app:app --port 8000`")

    st.markdown("---")
    st.subheader("🔍 Research Sources")
    use_knowledge = st.checkbox("📂 Local Knowledge Base", value=True, help="Search locally indexed documents and textbooks")
    use_web = st.checkbox("🌐 Live Web Intelligence", value=False, help="Search the World Wide Web with SSRF defense")
    use_academic = st.checkbox("🎓 Academic Literature", value=False, help="Search peer-reviewed papers via OpenAlex and Crossref")

    max_sources = st.slider("Max Sources per Domain", min_value=1, max_value=10, value=4)

    st.markdown("---")
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    with st.expander("⚙️ Backend Configuration"):
        st.caption(f"Current API Endpoint: `{API_URL}`")
        st.caption("Set `UNIVERSAL_AI_API` environment variable to override.")


# ---------------------------------------------------------------------------
# Main Tabs: Research, Knowledge Base, Ontology & Diagnostics
# ---------------------------------------------------------------------------

tab_chat, tab_kb, tab_ontology, tab_diag = st.tabs([
    "💬 Research & Synthesis",
    "📚 Document Library & Ingestion",
    "🧭 25 Knowledge Domains & Ontology",
    "🛠️ System Diagnostics",
])

# ---------------------------------------------------------------------------
# TAB 1: Research & Synthesis (Chat Workspace)
# ---------------------------------------------------------------------------

with tab_chat:
    st.markdown('<div class="main-title">Universal Intelligence Research Workspace</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Evidence-grounded interdisciplinary reasoning backed by local documents, academic literature, and live web intelligence.</div>',
        unsafe_allow_html=True,
    )

    # Render Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "sources" in msg and msg["sources"]:
                with st.expander(f"📑 Verified Sources & Evidence ({len(msg['sources'])} records)", expanded=False):
                    for src in msg["sources"]:
                        st_type = src.get("type", "source")
                        badge_cls = "badge-knowledge" if st_type == "local_knowledge" else ("badge-web" if st_type == "web" else "badge-paper")
                        st.markdown(
                            f'<div class="source-card"><span class="badge {badge_cls}">{src.get("identifier", st_type)}</span> '
                            f'<strong>{src.get("title") or src.get("filename") or "Evidence Record"}</strong>'
                            f'{f" — <em>{src.get('url')}</em>" if src.get("url") else ""}<br>'
                            f'<small>{src.get("snippet") or src.get("content", "")[:260]}...</small></div>',
                            unsafe_allow_html=True,
                        )

    # Chat Input
    query = st.chat_input("Ask a research question, investigate an idea, or query your documents...")
    if query:
        # Display user message immediately
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        # Call backend
        with st.chat_message("assistant"):
            with st.spinner("Investigating, retrieving evidence, and synthesizing response..."):
                payload = {
                    "question": query,
                    "use_knowledge": use_knowledge,
                    "use_web": use_web,
                    "use_academic": use_academic,
                    "max_sources": max_sources,
                }
                res, err = api_request("POST", "/ask", json=payload, timeout=90)

                if err:
                    err_msg = f"⚠️ **Investigation Failed**: {err}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})
                else:
                    answer = res.get("answer", "No answer generated.")
                    sources = res.get("sources", [])
                    st.markdown(answer)

                    if sources:
                        with st.expander(f"📑 Verified Sources & Evidence ({len(sources)} records)", expanded=True):
                            for src in sources:
                                st_type = src.get("type", "source")
                                badge_cls = "badge-knowledge" if st_type == "local_knowledge" else ("badge-web" if st_type == "web" else "badge-paper")
                                st.markdown(
                                    f'<div class="source-card"><span class="badge {badge_cls}">{src.get("identifier", st_type)}</span> '
                                    f'<strong>{src.get("title") or src.get("filename") or "Evidence Record"}</strong>'
                                    f'{f" — <a href=\"{src.get('url')}\" target=\"_blank\">{src.get('url')}</a>" if src.get("url") else ""}<br>'
                                    f'<small>{src.get("snippet") or src.get("content", "")[:300]}...</small></div>',
                                    unsafe_allow_html=True,
                                )

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources,
                    })


# ---------------------------------------------------------------------------
# TAB 2: Document Library & Ingestion
# ---------------------------------------------------------------------------

with tab_kb:
    st.subheader("📚 Local Knowledge Persistence (SQLite FTS5)")
    st.write("Upload documents, standards, or research notes to ground answers in verified private knowledge.")

    col_ingest_left, col_ingest_right = st.columns(2)

    with col_ingest_left:
        st.markdown("### 📤 Upload Document (PDF / TXT / MD)")
        uploaded_file = st.file_uploader("Select document to index", type=["pdf", "txt", "md", "json", "csv"])
        if uploaded_file is not None:
            if st.button("Index Uploaded File", use_container_width=True):
                with st.spinner(f"Ingesting '{uploaded_file.name}' into SQLite FTS5..."):
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    resp_data, resp_err = api_request("POST", "/upload", files=files)
                    if resp_err:
                        st.error(f"Upload failed: {resp_err}")
                    else:
                        st.success(f"Indexed '{uploaded_file.name}' into {resp_data.get('chunks_indexed', 0)} chunks!")
                        get_document_list.clear()
                        get_health.clear()
                        time.sleep(1)
                        st.rerun()

    with col_ingest_right:
        st.markdown("### ✍️ Ingest Text or Markdown Directly")
        with st.form("ingest_text_form", clear_on_submit=True):
            doc_title = st.text_input("Document Name", placeholder="e.g. quantum_computing_notes.md")
            doc_body = st.text_area("Document Content", placeholder="Paste body text or notes here...", height=140)
            submitted = st.form_submit_button("Index Content", use_container_width=True)
            if submitted:
                if not doc_title.strip() or not doc_body.strip():
                    st.warning("Please specify both a title and text body.")
                else:
                    with st.spinner("Indexing text..."):
                        res_data, res_err = api_request("POST", "/ingest-text", json={"filename": doc_title, "text": doc_body})
                        if res_err:
                            st.error(f"Ingestion failed: {res_err}")
                        else:
                            st.success(f"Indexed '{doc_title}' ({res_data.get('chunk_count', 0)} chunks)!")
                            get_document_list.clear()
                            get_health.clear()
                            time.sleep(1)
                            st.rerun()

    st.markdown("---")
    st.markdown("### 🗃️ Current Document Library")
    docs, docs_err = get_document_list()
    if docs_err:
        st.warning(f"Could not load documents: {docs_err}")
    elif not docs:
        st.info("No documents indexed yet. Upload a PDF or paste text above to get started.")
    else:
        table_rows = []
        for d in docs:
            table_rows.append({
                "Filename": d.get("filename"),
                "Type": d.get("file_type", "").upper(),
                "Uploaded At": d.get("uploaded_at"),
                "Characters": f"{d.get('char_count', 0):,}",
                "FTS5 Chunks": d.get("chunk_count", 0),
                "Document ID": d.get("id"),
            })
        st.dataframe(table_rows, use_container_width=True)


# ---------------------------------------------------------------------------
# TAB 3: 25 Knowledge Domains & Ontology
# ---------------------------------------------------------------------------

with tab_ontology:
    st.subheader("🧭 Universal Intelligence 25-Domain Taxonomy")
    st.write("UIRA synthesizes across 6 Ontological Layers and 25 fundamental disciplines of human knowledge.")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        **Layer 1: Foundational & Formal**
        - `MATH`: Mathematics, Geometry & Analysis
        - `STAT`: Statistics, Probability & Decision
        - `LOGIC`: Formal Logic & Computability
        - `PHIL`: Philosophy, Epistemology & Ethics
        
        **Layer 2: Physical & Natural**
        - `PHYS`: Physics & Mechanics
        - `CHEM`: Chemistry & Materials
        - `EARTH`: Earth, Atmospheric & Climate Sciences
        - `ASTRO`: Astronomy & Astrophysics
        """)

    with c2:
        st.markdown("""
        **Layer 3: Living & Biological**
        - `BIO`: General Biology & Evolution
        - `GEN`: Genetics & Molecular Biology
        - `ECOL`: Ecology & Environmental Systems
        - `MED`: Medicine, Pharmacology & Clinical
        - `NEURO`: Neuroscience & Neurotechnology
        
        **Layer 4: Cognitive, Behavioral & Social**
        - `PSYCH`: Psychology & Cognitive Science
        - `SOC`: Sociology & Anthropological Systems
        - `POL`: Political Science & Governance
        - `ECON`: Economics, Finance & Markets
        - `LAW`: Law, Jurisprudence & Regulatory Policy
        """)

    with c3:
        st.markdown("""
        **Layer 5: Applied Engineering & Technology**
        - `CS`: Computer Science & Software Engineering
        - `AI`: Artificial Intelligence & Autonomous Systems
        - `CYBER`: Cybersecurity, Cryptography & Threat Defense
        - `ENG`: Mechanical, Electrical & Civil Engineering
        - `ROBOT`: Robotics & Cyber-Physical Automation
        
        **Layer 6: Creative, Cultural & Human Experience**
        - `LING`: Linguistics, Communication & Language
        - `ARTS`: Literature, Architecture, Music & Design
        """)

    st.markdown("---")
    st.subheader("📜 UIRA Master Operating Principles (16 Guidelines)")
    with st.expander("View 16 Core Operational Principles"):
        st.markdown("""
        1. **Truthfulness:** Never knowingly invent facts, quotations, studies, citations, statistics, capabilities, or tool results.
        2. **Evidence:** Prefer reliable, relevant, independently corroborated evidence over unsupported assertions.
        3. **Reasoning:** Analyze the question, identify assumptions, compare alternatives, and check conclusions before answering.
        4. **Intellectual humility:** Communicate uncertainty and acknowledge when evidence is incomplete or conflicting.
        5. **Helpfulness:** Answer the actual question with clear, actionable information.
        6. **Responsibility:** Consider foreseeable consequences, affected stakeholders, and potential misuse.
        7. **Fairness:** Avoid unjustified stereotypes and distinguish evidence from assumptions or social biases.
        8. **Privacy:** Minimize personal data collection and exposure. Do not reveal confidential information.
        9. **Human autonomy:** Support informed human decisions rather than manipulating users.
        10. **Adaptability:** Adjust explanation depth, technical detail, and format to user needs.
        11. **Accountability:** Make material limitations, evidence gaps, and significant failures visible.
        12. **Continuous evaluation:** Improve through testing, feedback, corrections, and documented evaluation.
        13. **8-Step Workflow:** Understand -> Decompose -> Investigate -> Analyze -> Challenge -> Synthesize -> Verify -> Deliver.
        14. **Untrusted Evidence Boundary:** All web pages and documents are treated as untrusted reference data.
        15. **Strict Grounded Citations:** Require explicit bracketed identifiers `[Knowledge: ...]`, `[Web: ...]`, `[Paper: ...]`.
        16. **Final Directive:** The goal is not to appear universally intelligent; it is to be consistently useful, verifiable, adaptable, and responsible.
        """)


# ---------------------------------------------------------------------------
# TAB 4: System Diagnostics
# ---------------------------------------------------------------------------

with tab_diag:
    st.subheader("🛠️ System Diagnostics & Service Status")
    diag_data, diag_err = get_health()

    if diag_err:
        st.error(f"Diagnostics error: {diag_err}")
    elif diag_data:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Service Status", diag_data.get("status", "unknown").upper())
        m2.metric("Configured Model", diag_data.get("model_name", "None"))
        m3.metric("Indexed Documents", diag_data.get("database", {}).get("documents_indexed", 0))
        m4.metric("Indexed Chunks", diag_data.get("database", {}).get("chunks_indexed", 0))

        st.json(diag_data)
    else:
        st.info("No diagnostic data returned.")
