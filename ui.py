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

from guardian.model.catalog import get_candidate_catalog
from guardian.model.guardian_router import get_guardian_router
from guardian.model.slots import SlotState, get_slot_registry
from guardian.model.task_router import get_task_router
from guardian.prompts import GUARDIAN_MASTER_SYSTEM_PROMPT_V1, GUARDIAN_MASTER_SYSTEM_PROMPT_V2
from guardian.security.advisory import RuleAction, generate_firewall_advisory
from guardian.security.permissions import PermissionLevel, get_permission_gateway
from guardian.web.gateway import get_digital_access_gateway


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

tab_chat, tab_kb, tab_ontology, tab_models, tab_security, tab_diag = st.tabs([
    "💬 Research & Synthesis",
    "📚 Document Library & Ingestion",
    "🧭 25 Knowledge Domains & Ontology",
    "🤖 Multi-Model Catalog & Routing",
    "🛡️ Defensive Security & Firewall",
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
# TAB 4: Multi-Model Catalog & Intelligent Routing (Sections 3, 4, 5, 6, 17)
# ---------------------------------------------------------------------------

with tab_models:
    st.markdown('<div class="main-title">Multi-Model Catalog & Task Orchestration</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Discovery, capability verification, hardware assessment, and routing across candidate specialist models.</div>',
        unsafe_allow_html=True,
    )

    catalog = get_candidate_catalog()
    all_candidates = catalog.list_all()

    # Routing Sandbox at the top
    st.subheader("⚡ Intelligent Task Routing Sandbox (Section 5 & 17)")
    col_rq, col_flags = st.columns([3, 1])
    with col_rq:
        route_query = st.text_input(
            "Enter a user prompt to simulate intelligent routing:",
            value="Examine this screenshot and write a Python script to parse the table, then check for security vulnerabilities.",
        )
    with col_flags:
        chk_img = st.checkbox("Image attached", value=True)
        chk_aud = st.checkbox("Audio attached", value=False)
        chk_pdf = st.checkbox("PDF attached", value=False)

    if st.button("🚀 Evaluate Route & Multi-Model Allocation", use_container_width=True):
        router = get_task_router()
        decision = router.route_request(
            query=route_query,
            has_images=chk_img,
            has_audio=chk_aud,
            has_pdf=chk_pdf,
        )

        r1, r2 = st.columns([1, 1])
        with r1:
            st.markdown("#### 🎯 Routing Result")
            st.markdown(decision.format_routing_report())
        with r2:
            st.markdown("#### 🤝 Multi-Model Collaboration Plan (Section 6)")
            if decision.collaborators:
                for c in decision.collaborators:
                    st.info(f"**Role: {c['role'].upper()}** ➔ `{c['model']}`")
            else:
                st.caption("Single specialist model sufficient for this task. No secondary invocation needed.")

    st.markdown("---")
    # ─── TWENTY-SLOT MODEL FOUNDATION (Architecture 2.0) ──────────────────────
    st.subheader("🧩 Twenty-Slot Model Foundation (Architecture 2.0 — Section 3)")
    st.caption("Configurable registry of 20 model slots with on-demand lazy loading (max 2 parallel models in RAM/VRAM).")

    slot_reg = get_slot_registry()
    slot_dash = slot_reg.get_status_dashboard()

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Total Model Slots", slot_dash["total_slots"])
    m_col2.metric("Loaded in Memory", f"{slot_dash['loaded_count']} / {slot_dash['policy']['max_parallel_models']} max")
    m_col3.metric("Verified Healthy", slot_dash["healthy_count"])
    m_col4.metric("Unverified Candidates", slot_dash["unverified_count"])

    btn_v_all, btn_refresh = st.columns([2, 1])
    with btn_v_all:
        if st.button("⚡ Verify All 20 Model Slots (Smoke Check & Licensing)", use_container_width=True):
            slot_reg.verify_all_slots()
            st.success("All 20 candidate slots verified according to Section 3 specifications.")
            st.rerun()

    # 20-Slot interactive table
    for s_num in range(1, 21):
        slot = slot_reg.get_slot(s_num)
        if not slot:
            continue
        
        # State badge formatting
        state_str = slot.state.value.upper()
        if slot.is_loaded:
            badge = "🔵 LOADED (ACTIVE RAM)"
        elif slot.state == SlotState.HEALTHY:
            badge = "🟢 HEALTHY (READY)"
        elif slot.state == SlotState.FAILED:
            badge = "🔴 FAILED"
        else:
            badge = "⚪ UNVERIFIED"

        with st.expander(f"Slot {slot.slot_number:02d}: `{slot.id}` — {badge} | {slot.task}"):
            col_l, col_r = st.columns([3, 2])
            with col_l:
                st.markdown(f"**Repository:** `{slot.repo}`")
                st.markdown(f"**Task Role:** `{slot.task}` | **Adapter:** `{slot.adapter_name}`")
                st.markdown(f"**Estimated Memory:** `{slot.estimated_ram_gb:.1f} GB RAM` / `{slot.estimated_vram_gb:.1f} GB VRAM`")
                if slot.validation_notes:
                    st.caption("**Validation Notes:** " + " • ".join(slot.validation_notes))
            with col_r:
                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    if st.button(f"Verify #{slot.slot_number}", key=f"v_{slot.slot_number}"):
                        res = slot_reg.verify_slot(slot.slot_number)
                        st.info(f"Verification: {res['state']}")
                        st.rerun()
                with btn_c2:
                    if slot.is_loaded:
                        if st.button(f"Unload #{slot.slot_number}", key=f"u_{slot.slot_number}"):
                            slot_reg.unload_slot(slot.slot_number)
                            st.rerun()
                    else:
                        if st.button(f"Load #{slot.slot_number}", key=f"l_{slot.slot_number}"):
                            l_res = slot_reg.load_slot(slot.slot_number)
                            if l_res.get("evicted_slot"):
                                st.warning(f"LRU: Evicted Slot {l_res['evicted_slot']} to maintain {slot_reg.policy.max_parallel_models} max models.")
                            st.rerun()

    # Model Task Execution Sandbox
    st.markdown("---")
    st.subheader("🧪 Slot Adapter Direct Execution Sandbox")
    exec_c1, exec_c2 = st.columns([1, 3])
    with exec_c1:
        chosen_slot_num = st.selectbox("Target Slot", list(range(1, 21)), index=0, format_func=lambda n: f"Slot {n:02d} ({slot_reg.get_slot(n).id if slot_reg.get_slot(n) else n})")
    with exec_c2:
        test_prompt = st.text_input("Test Prompt / Task Input", value="Analyze system telemetry and evaluate potential anomalies.")

    if st.button("▶️ Execute Task via Slot Adapter", use_container_width=True):
        res = slot_reg.run_task(chosen_slot_num, {"prompt": test_prompt, "query": test_prompt})
        st.markdown(f"**Status:** `{res.status.upper()}` | **Slot ID:** `{res.slot_id}`")
        if res.error:
            st.error(f"Error: {res.error}")
        else:
            st.json(res.output)
            st.caption(f"Metadata: {res.metadata}")

    st.markdown("---")
    st.subheader(f"📋 Candidate Model Specification Catalog ({len(all_candidates)} Proposed Models)")
    st.caption("Section 3 Rule: Treat every model ID as a CANDIDATE. Verify capabilities, hardware, and safety sandbox before activation.")

    # Filter row
    f1, f2 = st.columns(2)
    with f1:
        mod_filter = st.selectbox("Filter by Modality", ["All", "text", "image", "audio", "video", "pdf"])
    with f2:
        dep_filter = st.selectbox("Filter by Deployment", ["All", "local", "hosted", "hybrid"])

    filtered_entries = catalog.filter(
        modality=None if mod_filter == "All" else mod_filter,
        deployment=None if dep_filter == "All" else dep_filter,
    )

    for entry in filtered_entries:
        eligibility = catalog.verify_candidate_eligibility(entry.model_id)
        with st.expander(
            f"#{entry.candidate_number} | {entry.model_id} ({entry.family}) — [{entry.deployment.value.upper()}]",
            expanded=False,
        ):
            c_info, c_specs = st.columns([2, 1])
            with c_info:
                st.markdown(f"**Capability Tags:** `{'`, `'.join(entry.capability_tags)}`")
                st.markdown(f"**Modalities:** In: `{', '.join(entry.input_modalities)}` ➔ Out: `{', '.join(entry.output_modalities)}`")
                st.markdown(f"**Runtime & Dependencies:** `{entry.required_runtime}` ({', '.join(entry.required_dependencies)})")
                st.markdown(f"**License:** {entry.license}")
                if entry.known_limitations:
                    st.warning(f"**Known Limitations:** {'; '.join(entry.known_limitations)}")
                if entry.requires_custom_code:
                    st.error("⚠️ **Security Alert:** Requires `trust_remote_code=True`. Sandbox execution required.")
                if eligibility["warnings"]:
                    for w in eligibility["warnings"]:
                        st.caption(f"• {w}")

            with c_specs:
                st.markdown("**Estimated Hardware Requirements:**")
                st.write(f"- Min RAM: **{entry.estimated_hardware.min_ram_gb:.0f} GB**")
                st.write(f"- Min VRAM: **{entry.estimated_hardware.min_vram_gb:.0f} GB**")
                st.write(f"- Disk Storage: **{entry.estimated_hardware.disk_gb:.0f} GB**")
                st.write(f"- Context Window: **{entry.estimated_hardware.context_window:,} tokens**")
                st.write(f"- Recommended Host: {entry.estimated_hardware.recommended_gpu}")

            st.markdown("**Example Loading & Pipeline Snippet:**")
            st.code(entry.code_snippet, language="python")


# ---------------------------------------------------------------------------
# TAB 5: Defensive Security & Firewall Advisory (Sections 7, 8, 17)
# ---------------------------------------------------------------------------

with tab_security:
    st.markdown('<div class="main-title">Guardian Defensive Security Engine</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Advisory and read-only defensive policy, anomaly triage, and evidence-grounded firewall recommendations.</div>',
        unsafe_allow_html=True,
    )

    # ─── PERMISSION & OPERATIONAL SAFETY GATEWAY (Section 9) ─────────────────
    st.markdown("---")
    st.subheader("🛡️ Permission & Operational Safety Gateway (Section 9)")
    st.caption("Strict separation of operational authority across three permission tiers.")

    perm_gw = get_permission_gateway()
    sec_status = perm_gw.get_security_status()

    p_col1, p_col2, p_col3 = st.columns(3)
    with p_col1:
        st.info("**LEVEL 1 — READ**\n\nSearch, retrieve, inspect, summarize permitted resources without state modifications.")
    with p_col2:
        st.warning("**LEVEL 2 — PREPARE**\n\nDraft files, stage code changes, recommend security rules without committing changes.")
    with p_col3:
        st.error("**LEVEL 3 — EXECUTE**\n\nCommit changes, alter firewalls, delete files. Strictly requires explicit human authorization.")

    # Kill Switch Banner & Action Approval Queue
    st.markdown("#### 🚨 Safety Posture & Emergency Controls")
    k_col1, k_col2 = st.columns([2, 1])
    with k_col1:
        if sec_status["kill_switch_active"]:
            st.error("🔴 **EMERGENCY KILL SWITCH IS ACTIVE**: All operational actions and model executions are halted.")
        else:
            st.success("🟢 **Operational Status: Normal**: Security guardrails and permission gates active.")
    with k_col2:
        if sec_status["kill_switch_active"]:
            if st.button("Disarm Kill Switch", use_container_width=True):
                perm_gw.kill_switch.deactivate()
                st.rerun()
        else:
            if st.button("🛑 ACTIVATE EMERGENCY STOP", use_container_width=True):
                perm_gw.kill_switch.activate("User triggered emergency stop from UI")
                st.rerun()

    # Action Approval Queue
    st.markdown("#### 📋 Consequential Action Approval Queue (Level 3)")
    pending = sec_status["pending_proposals"]
    if pending:
        for p in pending:
            with st.container():
                st.write(f"**Action:** `{p['action_type']}` | **Target:** `{p['target']}` | **ID:** `{p['action_id']}`")
                st.caption(f"Description: {p['description']}")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button(f"✅ Authorize & Commit #{p['action_id']}", key=f"app_{p['action_id']}"):
                        perm_gw.approve_proposal(p['action_id'], approver="human_ui_admin")
                        perm_gw.execute_proposal(p['action_id'])
                        st.success(f"Action {p['action_id']} executed.")
                        st.rerun()
                with b2:
                    if st.button(f"❌ Reject #{p['action_id']}", key=f"rej_{p['action_id']}"):
                        perm_gw.reject_proposal(p['action_id'])
                        st.info(f"Action {p['action_id']} rejected.")
                        st.rerun()
    else:
        st.caption("No pending consequential actions requiring human authorization.")

    # Live Audit Log Viewer
    st.markdown("---")
    st.subheader("📜 Operational Audit Log (`data/audit/guardian.jsonl`)")
    audit_events = perm_gw.audit_logger.read_recent_events(limit=15)
    if audit_events:
        st.dataframe(audit_events, use_container_width=True)
    else:
        st.caption("Audit log is currently empty.")


# ---------------------------------------------------------------------------
# TAB 6: System Diagnostics
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
