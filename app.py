import streamlit as st
import tempfile
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Intelli-Credit | DOMINIX",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .main-header {
        background: linear-gradient(135deg, #0a1628 0%, #0d2137 50%, #0a1628 100%);
        border: 1px solid #1e3a5f;
        padding: 2.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .main-header::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, #00d4ff, #0066cc, #00d4ff);
    }
    .main-header h1 {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 2rem;
        color: #e8f4fd;
        margin: 0 0 0.5rem 0;
        letter-spacing: 2px;
    }
    .main-header p {
        color: #7aadcc;
        font-size: 0.9rem;
        margin: 0.2rem 0;
    }
    .tag-row {
        display: flex;
        gap: 8px;
        justify-content: center;
        margin-top: 0.8rem;
        flex-wrap: wrap;
    }
    .tag {
        background: rgba(0, 212, 255, 0.1);
        border: 1px solid rgba(0, 212, 255, 0.3);
        color: #00d4ff;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-family: 'IBM Plex Mono', monospace;
    }
    .section-header {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1rem;
        color: #e8f4fd;
        border-left: 3px solid #0066cc;
        padding-left: 12px;
        margin: 1.5rem 0 1rem 0;
        letter-spacing: 1px;
    }
    .agent-card {
        background: #0d1f33;
        border: 1px solid #1e3a5f;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        margin: 0.3rem 0;
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.85rem;
    }
    .status-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
    }
    .dot-pending  { background: #555; }
    .dot-running  { background: #f59e0b; box-shadow: 0 0 6px #f59e0b; }
    .dot-done     { background: #10b981; box-shadow: 0 0 6px #10b981; }
    .dot-error    { background: #ef4444; }
    .decision-approve {
        background: linear-gradient(135deg, #064e3b, #065f46);
        border: 1px solid #10b981;
        color: #6ee7b7;
        padding: 1rem 2rem;
        border-radius: 8px;
        text-align: center;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.1rem;
        font-weight: 600;
        letter-spacing: 2px;
    }
    .decision-conditional {
        background: linear-gradient(135deg, #451a03, #78350f);
        border: 1px solid #f59e0b;
        color: #fcd34d;
        padding: 1rem 2rem;
        border-radius: 8px;
        text-align: center;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.1rem;
        font-weight: 600;
        letter-spacing: 2px;
    }
    .decision-reject {
        background: linear-gradient(135deg, #450a0a, #7f1d1d);
        border: 1px solid #ef4444;
        color: #fca5a5;
        padding: 1rem 2rem;
        border-radius: 8px;
        text-align: center;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.1rem;
        font-weight: 600;
        letter-spacing: 2px;
    }
    .metric-box {
        background: #0d1f33;
        border: 1px solid #1e3a5f;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .metric-label {
        color: #7aadcc;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.4rem;
        font-family: 'IBM Plex Mono', monospace;
    }
    .metric-value {
        color: #e8f4fd;
        font-size: 1.4rem;
        font-weight: 700;
        font-family: 'IBM Plex Mono', monospace;
    }
    .five-c-card {
        background: #0d1f33;
        border: 1px solid #1e3a5f;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .five-c-label {
        color: #7aadcc;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-family: 'IBM Plex Mono', monospace;
    }
    .five-c-score-high   { color: #10b981; font-size: 1.8rem; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
    .five-c-score-medium { color: #f59e0b; font-size: 1.8rem; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
    .five-c-score-low    { color: #ef4444; font-size: 1.8rem; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
    .red-flag-item {
        background: rgba(239, 68, 68, 0.08);
        border-left: 3px solid #ef4444;
        padding: 0.5rem 1rem;
        margin: 0.3rem 0;
        border-radius: 0 4px 4px 0;
        font-size: 0.88rem;
        color: #fca5a5;
    }
    .cross-ref-box {
        background: #0d1f33;
        border: 1px solid #1e3a5f;
        border-radius: 8px;
        padding: 1.2rem;
        margin: 0.5rem 0;
    }
    .cross-ref-title {
        color: #00d4ff;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.8rem;
        letter-spacing: 1px;
        margin-bottom: 0.5rem;
    }
    .integrity-clean    { color: #10b981; font-weight: 600; }
    .integrity-suspect  { color: #f59e0b; font-weight: 600; }
    .integrity-highrisk { color: #ef4444; font-weight: 600; }
    .doc-badge {
        display: inline-block;
        background: rgba(0, 102, 204, 0.15);
        border: 1px solid rgba(0, 102, 204, 0.4);
        color: #7aadcc;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-family: 'IBM Plex Mono', monospace;
        margin: 2px;
    }
    .stButton > button {
        background: linear-gradient(135deg, #0a3d6b, #0066cc);
        color: white;
        border: 1px solid #0088ff;
        border-radius: 6px;
        padding: 0.6rem 2rem;
        font-family: 'IBM Plex Mono', monospace;
        font-weight: 600;
        letter-spacing: 1px;
        width: 100%;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #0d4f8a, #0077ee);
        border-color: #00aaff;
    }
    div[data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace;
    }
</style>
""", unsafe_allow_html=True)


# ── Session State ─────────────────────────────────────────────
def init_session():
    defaults = {
        "financials": None,
        "research": None,
        "five_cs": None,
        "recommendation": None,
        "cam_path": None,
        "cross_ref": None,
        "doc_types_found": [],
        "company_name": "",
        "analysis_done": False,
        "research_cache": {},
        "agent_statuses": {
            "classifier": "pending",
            "ingestor": "pending",
            "cross_ref": "pending",
            "research": "pending",
            "scoring": "pending",
            "cam": "pending",
        },
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session()


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 1rem 0;'>
        <div style='font-family: IBM Plex Mono, monospace; font-size: 1.2rem;
                    color: #00d4ff; letter-spacing: 3px; font-weight: 600;'>
            INTELLI-CREDIT
        </div>
        <div style='color: #7aadcc; font-size: 0.75rem; margin-top: 4px;'>
            by DOMINIX
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**AGENT PIPELINE**", help="Real-time status of all AI agents")

    status_icons = {"pending": "⬜", "running": "🔄", "done": "✅", "error": "❌"}
    dot_classes  = {"pending": "dot-pending", "running": "dot-running",
                    "done": "dot-done", "error": "dot-error"}

    agent_labels = {
        "classifier": "Doc Classifier",
        "ingestor":   "Data Ingestor",
        "cross_ref":  "Cross-Reference",
        "research":   "Research Agent",
        "scoring":    "Scoring Agent",
        "cam":        "CAM Generator",
    }

    for agent, label in agent_labels.items():
        status = st.session_state.agent_statuses[agent]
        st.markdown(
            f"<div class='agent-card'>"
            f"<div class='status-dot {dot_classes[status]}'></div>"
            f"<span style='color:#c8dcea'>{label}</span>"
            f"<span style='margin-left:auto; color:#555; font-size:0.75rem; "
            f"font-family:IBM Plex Mono'>{status.upper()}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    if st.session_state.doc_types_found:
        st.markdown("---")
        st.markdown("**DOCUMENTS DETECTED**")
        for dtype in st.session_state.doc_types_found:
            st.markdown(f"<span class='doc-badge'>{dtype.replace('_',' ').upper()}</span>",
                        unsafe_allow_html=True)

    st.markdown("---")
    show_raw = st.checkbox("Show Raw Agent Output", value=False)
    st.markdown("---")
    st.markdown(
        "<div style='color:#3a5f7a; font-size:0.75rem; text-align:center;'>"
        "Vivriti Capital Hackathon 2026<br>IIT Hyderabad · YUVAAN 2026"
        "</div>",
        unsafe_allow_html=True
    )


# ── Header ────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🏦 INTELLI-CREDIT</h1>
    <p>AI-Powered Corporate Credit Appraisal Engine</p>
    <p style="color:#3a5f7a; font-size:0.8rem;">
        Automates end-to-end CAM preparation · Weeks of work in minutes
    </p>
    <div class="tag-row">
        <span class="tag">VectorLess RAG</span>
        <span class="tag">Multi-Agent</span>
        <span class="tag">Cross-Document Intelligence</span>
        <span class="tag">Indian Context</span>
        <span class="tag">Gemini 2.5</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Step 1: Upload ─────────────────────────────────────────────
st.markdown("<div class='section-header'>01 / UPLOAD DOCUMENTS</div>",
            unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])
with col1:
    uploaded_files = st.file_uploader(
        "Upload all available documents for the company",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload multiple document types for cross-referencing intelligence"
    )
with col2:
    st.markdown("""
    <div style='background:#0d1f33; border:1px solid #1e3a5f;
                border-radius:8px; padding:1rem; font-size:0.82rem; color:#7aadcc;'>
        <div style='color:#00d4ff; font-family:IBM Plex Mono;
                    font-size:0.75rem; margin-bottom:8px;'>
            SUPPORTED TYPES
        </div>
        📊 Annual Reports<br>
        🧾 GST Returns / ITR<br>
        🏦 Bank Statements<br>
        ⚖️ Legal Notices<br>
        📋 Sanction Letters<br>
        📈 Rating Reports
    </div>
    """, unsafe_allow_html=True)

    if uploaded_files and len(uploaded_files) > 1:
        st.success(f"✅ {len(uploaded_files)} files — cross-referencing enabled")
    elif uploaded_files:
        st.info("💡 Upload multiple document types for deeper analysis")


# ── Step 2: Company Details ────────────────────────────────────
st.markdown("<div class='section-header'>02 / COMPANY DETAILS</div>",
            unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    company_name = st.text_input(
        "Company Name *",
        placeholder="e.g. Tata Motors Limited",
        value=st.session_state.company_name,
    )
with col2:
    promoters_input = st.text_input(
        "Promoter Names (comma separated)",
        placeholder="e.g. N. Chandrasekaran",
    )
with col3:
    sector = st.selectbox("Industry Sector", [
        "Manufacturing", "NBFC/Financial Services",
        "Real Estate", "Infrastructure", "IT/Technology",
        "Retail/FMCG", "Healthcare/Pharma",
        "Renewable Energy", "Logistics", "Other"
    ])

col1, col2 = st.columns(2)
with col1:
    loan_amount = st.text_input("Requested Loan Amount",
                                placeholder="e.g. ₹ 50 Crores")
with col2:
    loan_purpose = st.text_input("Loan Purpose",
                                 placeholder="e.g. Working Capital Expansion")


# ── Step 3: Field Notes ────────────────────────────────────────
st.markdown("<div class='section-header'>03 / CREDIT OFFICER FIELD NOTES</div>",
            unsafe_allow_html=True)
st.caption("Qualitative observations from site visits and management interviews — "
           "AI adjusts the risk score in real-time based on these inputs")

manual_notes = st.text_area(
    "Field Observations",
    placeholder=(
        "e.g. Factory found operating at 40% capacity. "
        "Management was evasive about pending litigation. "
        "Inventory levels appeared inflated compared to GST filings..."
    ),
    height=100,
    label_visibility="collapsed",
)


# ── Step 4: Run ────────────────────────────────────────────────
st.markdown("<div class='section-header'>04 / RUN ANALYSIS</div>",
            unsafe_allow_html=True)

run_button = st.button(
    "⚡  RUN FULL CREDIT ANALYSIS",
    disabled=not (uploaded_files and company_name),
)

if not uploaded_files:
    st.markdown(
        "<div style='background:rgba(0,102,204,0.08); border:1px solid #1e3a5f; "
        "border-radius:6px; padding:0.7rem 1rem; color:#7aadcc; font-size:0.85rem;'>"
        "👆 Upload at least one document to proceed</div>",
        unsafe_allow_html=True
    )
if uploaded_files and not company_name:
    st.warning("⚠️ Please enter the company name.")


# ── ANALYSIS ENGINE ────────────────────────────────────────────
if run_button and uploaded_files and company_name:
    st.session_state.company_name = company_name
    promoter_list = [p.strip() for p in promoters_input.split(",") if p.strip()]

    # save uploaded files to temp
    import tempfile
    temp_paths = []
    for uf in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uf.read())
            temp_paths.append((uf.name, tmp.name))

    progress      = st.progress(0)
    status_text   = st.empty()
    log_expander  = st.expander("📋 Live Processing Log", expanded=True)
    log_container = log_expander.empty()
    log_lines     = []

    def add_log(msg: str, level: str = "info"):
        import datetime
        icons = {"info": "ℹ️", "success": "✅", "warn": "⚠️", "error": "❌"}
        ts    = datetime.datetime.now().strftime("%H:%M:%S")
        log_lines.append(f"`{ts}` {icons.get(level,'ℹ️')} {msg}")
        log_container.markdown("\n\n".join(log_lines[-20:]))

    try:
        # ── Agent 1+2: Ingestor (classifier + extraction together) ──
        status_text.markdown("🔄 **Data Ingestor** — Classifying and parsing documents...")
        st.session_state.agent_statuses["classifier"] = "running"
        st.session_state.agent_statuses["ingestor"] = "running"
        progress.progress(8)

        from agents.ingestor_agent import IngestorAgent

        ingestor = IngestorAgent(pdf_paths=temp_paths, log_fn=add_log)
        ingest_result = ingestor.run()

        all_financials        = ingest_result["financials"]
        documents_by_type     = ingest_result["documents_by_type"]
        doc_types_found       = ingest_result["doc_types_found"]
        parsers_by_type       = ingest_result["parsers_by_type"]

        st.session_state.financials       = all_financials
        st.session_state.doc_types_found  = doc_types_found
        st.session_state.agent_statuses["classifier"] = "done"
        st.session_state.agent_statuses["ingestor"] = "done"
        progress.progress(35)

        # ── Agent 3: Cross-Reference ──────────────────────────
        status_text.markdown("🔄 **Cross-Reference Agent** — Reconciling documents...")
        st.session_state.agent_statuses["cross_ref"] = "running"

        cross_ref_results = {}
        if len(documents_by_type) > 1:
            add_log(
                f"Multiple document types detected: "
                f"{', '.join(documents_by_type.keys())} — "
                f"running cross-document analysis"
            )
            from agents.cross_reference_agent import CrossReferenceAgent
            from google import genai as _genai
            _cr_client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            cross_agent = CrossReferenceAgent(
                documents_by_type, _cr_client, "gemini-2.5-flash"
            )
            cross_ref_results = cross_agent.run()

            # inject cross-ref flags into financials red flags
            cr_flags = cross_ref_results.get(
                "overall_integrity_score", {}
            ).get("flags", [])
            if cr_flags:
                existing = all_financials["red_flags"].get("red_flags", [])
                all_financials["red_flags"]["red_flags"] = existing + cr_flags
                add_log(
                    f"Cross-reference found {len(cr_flags)} integrity flag(s)",
                    "warn"
                )
            else:
                add_log("Cross-reference: no integrity issues detected", "success")
        else:
            add_log(
                "Single document uploaded — cross-reference skipped. "
                "Upload GST filing or bank statement alongside annual report "
                "for fraud detection.",
                "warn"
            )

        st.session_state.cross_ref = cross_ref_results
        st.session_state.agent_statuses["cross_ref"] = "done"
        progress.progress(52)

        # ── Agent 4: Research ─────────────────────────────────
        status_text.markdown("🔄 **Research Agent** — Web intelligence gathering...")
        st.session_state.agent_statuses["research"] = "running"

        cache_key = company_name.lower().strip()
        if cache_key in st.session_state.research_cache:
            research_results = st.session_state.research_cache[cache_key]
            add_log(
                f"Research cache hit for '{company_name}' — skipping web search",
                "success"
            )
        else:
            add_log(
                f"Searching: {company_name} news, litigation, promoters, "
                f"sector headwinds..."
            )
            from agents.research_agent import ResearchAgent
            ra = ResearchAgent(
                company_name   = company_name,
                promoter_names = promoter_list,
                sector         = sector,
            )
            research_results = ra.run_full_research()
            st.session_state.research_cache[cache_key] = research_results
            add_log("Web research and synthesis complete", "success")

        st.session_state.research = research_results
        st.session_state.agent_statuses["research"] = "done"
        progress.progress(68)

        # ── Agent 5: Scoring ──────────────────────────────────
        status_text.markdown("🔄 **Scoring Agent** — Computing Five Cs...")
        st.session_state.agent_statuses["scoring"] = "running"
        add_log("Computing weighted Five Cs score with penalty adjustments...")

        # enrich notes with cross-ref findings before scoring
        enriched_notes = manual_notes or ""
        if cross_ref_results:
            integrity = cross_ref_results.get("overall_integrity_score", {})
            if integrity.get("verdict") in ["SUSPECT", "HIGH_RISK"]:
                enriched_notes += (
                    f"\n[SYSTEM] Cross-document integrity: "
                    f"{integrity.get('verdict')} — "
                    f"{'; '.join(integrity.get('flags', []))}"
                )

        from agents.scoring_agent import ScoringAgent
        scoring_agent = ScoringAgent(
            company_name = company_name,
            financials   = all_financials,
            research     = research_results,
            manual_notes = enriched_notes,
        )
        scoring_results = scoring_agent.run()
        st.session_state.five_cs        = scoring_results["five_cs"]
        st.session_state.recommendation = scoring_results["recommendation"]
        st.session_state.agent_statuses["scoring"] = "done"
        add_log(
            f"Score: {scoring_results['recommendation'].get('final_score')}/100 "
            f"| Rating: {scoring_results['recommendation'].get('rating')} "
            f"| Decision: {scoring_results['recommendation'].get('decision')}",
            "success"
        )
        progress.progress(82)

        # ── Agent 6: CAM Generator ────────────────────────────
        status_text.markdown("🔄 **CAM Generator** — Writing Credit Appraisal Memo...")
        st.session_state.agent_statuses["cam"] = "running"
        add_log("Generating professional Credit Appraisal Memo (Word document)...")

        from agents.cam_agent import CAMAgent
        cam_agent = CAMAgent(
            company_name   = company_name,
            financials     = all_financials,
            research       = research_results,
            five_cs        = st.session_state.five_cs,
            recommendation = st.session_state.recommendation,
            manual_notes   = enriched_notes,
            loan_amount    = loan_amount or "Not specified",
            loan_purpose   = loan_purpose or "General Corporate Purpose",
            cross_ref      = cross_ref_results,
            log_fn         = add_log,
        )
        cam_path = cam_agent.run()
        st.session_state.cam_path = cam_path
        st.session_state.agent_statuses["cam"] = "done"
        st.session_state.analysis_done = True
        add_log("Analysis complete — CAM ready for download", "success")
        progress.progress(100)
        status_text.markdown("✅ **Analysis Complete**")

        for _, path in temp_paths:
            try:
                os.unlink(path)
            except Exception:
                pass

    except Exception as e:
        status_text.markdown(f"❌ **Error:** {str(e)}")
        st.error(f"Analysis failed: {str(e)}")
        st.exception(e)
        for agent in st.session_state.agent_statuses:
            if st.session_state.agent_statuses[agent] == "running":
                st.session_state.agent_statuses[agent] = "error"


# ── RESULTS ────────────────────────────────────────────────────
if st.session_state.analysis_done:
    st.markdown("---")
    st.markdown("<div class='section-header'>CREDIT ANALYSIS RESULTS</div>",
                unsafe_allow_html=True)

    rec      = st.session_state.recommendation or {}
    five_cs  = st.session_state.five_cs or {}
    research = st.session_state.research or {}
    cross_ref = st.session_state.cross_ref or {}

    # ── Decision Banner ───────────────────────────────────────
    decision = rec.get("decision", "PENDING")
    css_class = {
        "APPROVE":             "decision-approve",
        "CONDITIONAL_APPROVE": "decision-conditional",
        "REJECT":              "decision-reject",
    }.get(decision, "decision-conditional")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"<div class='{css_class}'>DECISION: {decision}</div>",
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Key Metrics ───────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    metrics = [
        ("CREDIT SCORE", f"{rec.get('final_score','N/A')}/100", m1),
        ("RATING",        rec.get("rating", "N/A"),             m2),
        ("AMOUNT",
         f"₹{rec.get('recommended_amount_crores','N/A')}Cr"
         if rec.get("recommended_amount_crores") else "N/A",    m3),
        ("RATE",
         f"{rec.get('interest_rate_percent','N/A')}% p.a."
         if rec.get("interest_rate_percent") else "N/A",        m4),
        ("TENURE",
         f"{rec.get('tenure_months','N/A')} mo"
         if rec.get("tenure_months") else "N/A",                m5),
    ]
    for label, value, col in metrics:
        with col:
            st.markdown(
                f"<div class='metric-box'>"
                f"<div class='metric-label'>{label}</div>"
                f"<div class='metric-value'>{value}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Five Cs ───────────────────────────────────────────────
    st.markdown("**FIVE Cs ASSESSMENT**")
    c1, c2, c3, c4, c5 = st.columns(5)
    five_c_data = [
        ("CHARACTER",  "character_score",  "👤", "25%", c1),
        ("CAPACITY",   "capacity_score",   "💰", "30%", c2),
        ("CAPITAL",    "capital_score",    "🏛️", "20%", c3),
        ("COLLATERAL", "collateral_score", "🔒", "15%", c4),
        ("CONDITIONS", "conditions_score", "🌍", "10%", c5),
    ]
    for label, key, icon, weight, col in five_c_data:
        score = five_cs.get(key, 0)
        try:
            sn = float(score)
        except Exception:
            sn = 0
        css = ("five-c-score-high" if sn >= 70 else
               "five-c-score-medium" if sn >= 50 else
               "five-c-score-low")
        with col:
            st.markdown(
                f"<div class='five-c-card'>"
                f"<div style='font-size:1.5rem'>{icon}</div>"
                f"<div class='five-c-label'>{label}</div>"
                f"<div class='{css}'>{score}</div>"
                f"<div style='color:#3a5f7a; font-size:0.72rem; "
                f"font-family:IBM Plex Mono'>{weight}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    # ── Detailed Tabs ─────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏢 Company & Financials",
        "🔗 Cross-Reference",
        "🔍 Research Intelligence",
        "⚠️ Risk Signals",
        "📝 Decision Rationale",
    ])

    # Tab 1 — Company & Financials
    with tab1:
        fin      = st.session_state.financials or {}
        basic    = fin.get("basic_info", {})
        financials = fin.get("financials", {})

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Company Information**")
            if basic and not basic.get("parse_error"):
                for label, key in [
                    ("Name", "company_name"), ("CIN", "cin"),
                    ("Business", "business_nature"),
                    ("Incorporated", "incorporation_year"),
                ]:
                    val = basic.get(key, "N/A")
                    st.write(f"**{label}:** {val}")
                directors = basic.get("directors", [])
                if directors:
                    st.write(f"**Directors:** {', '.join(directors)}")
            else:
                st.info("Company info extracted from uploaded documents.")

        with col2:
            st.markdown("**Key Financial Metrics**")
            if financials and not financials.get("parse_error"):
                fin_metrics = {
                    "Revenue (Current)": f"₹{financials.get('revenue_current','N/A')} Cr",
                    "EBITDA":            f"₹{financials.get('ebitda','N/A')} Cr",
                    "PAT":               f"₹{financials.get('pat','N/A')} Cr",
                    "Net Worth":         f"₹{financials.get('net_worth','N/A')} Cr",
                    "Total Debt":        f"₹{financials.get('total_debt','N/A')} Cr",
                    "Debt/Equity":       str(financials.get("debt_to_equity","N/A")),
                    "Current Ratio":     str(financials.get("current_ratio","N/A")),
                }
                for k, v in fin_metrics.items():
                    st.write(f"**{k}:** {v}")

    # Tab 2 — Cross-Reference (NEW)
    with tab2:
        if not cross_ref:
            st.info(
                "💡 Upload multiple document types (e.g. Annual Report + "
                "GST Filing + Bank Statement) to enable cross-document "
                "intelligence and fraud detection."
            )
        else:
            integrity = cross_ref.get("overall_integrity_score", {})
            verdict   = integrity.get("verdict", "N/A")
            verdict_css = {
                "CLEAN":     "integrity-clean",
                "SUSPECT":   "integrity-suspect",
                "HIGH_RISK": "integrity-highrisk",
            }.get(verdict, "")

            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(
                    f"<div class='cross-ref-box' style='text-align:center'>"
                    f"<div class='cross-ref-title'>INTEGRITY VERDICT</div>"
                    f"<div class='{verdict_css}' "
                    f"style='font-size:1.3rem'>{verdict}</div>"
                    f"<div style='color:#7aadcc; font-size:0.8rem; margin-top:4px'>"
                    f"Score: {integrity.get('score','N/A')}/100</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with col2:
                flags = integrity.get("flags", [])
                if flags:
                    st.markdown("**Integrity Flags Detected:**")
                    for flag in flags:
                        st.markdown(
                            f"<div class='red-flag-item'>⚠️ {flag}</div>",
                            unsafe_allow_html=True
                        )
                else:
                    st.success("✅ No integrity flags detected across documents")

            # GST-Bank reconciliation
            gst_bank = cross_ref.get("gst_bank_reconciliation", {})
            if gst_bank and not gst_bank.get("parse_error"):
                st.markdown("---")
                st.markdown("**GST vs Bank Statement Reconciliation**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("GST Reported Revenue",
                              f"₹{gst_bank.get('gst_reported_revenue','N/A')} Cr")
                with col2:
                    st.metric("Bank Credited Revenue",
                              f"₹{gst_bank.get('bank_credited_revenue','N/A')} Cr")
                with col3:
                    var = gst_bank.get("variance_percent", "N/A")
                    st.metric("Variance", f"{var}%",
                              delta_color="inverse")

                flag_val = gst_bank.get("integrity_flag", "")
                if flag_val == "HIGH_RISK":
                    st.error(f"🚨 HIGH RISK: {gst_bank.get('summary','')}")
                elif flag_val == "SUSPECT":
                    st.warning(f"⚠️ SUSPECT: {gst_bank.get('summary','')}")
                else:
                    st.success(f"✅ {gst_bank.get('summary','Clean reconciliation')}")

            # Revenue verification
            rev_ver = cross_ref.get("revenue_verification", {})
            if rev_ver and not rev_ver.get("parse_error"):
                st.markdown("---")
                st.markdown("**Annual Report vs GST Revenue Verification**")
                if rev_ver.get("red_flag"):
                    st.error(
                        f"🚨 Revenue mismatch detected — "
                        f"Severity: {rev_ver.get('severity','N/A')} | "
                        f"Difference: ₹{rev_ver.get('difference_crores','N/A')} Cr "
                        f"({rev_ver.get('difference_percent','N/A')}%)"
                    )
                    st.write(rev_ver.get("explanation", ""))
                else:
                    st.success("✅ Revenue figures consistent across documents")

    # Tab 3 — Research
    with tab3:
        if research:
            col1, col2 = st.columns(2)
            with col1:
                news = research.get("company_news", {})
                st.markdown("**📰 Company News**")
                sentiment = news.get("sentiment", "N/A")
                color = ("green" if sentiment == "Positive" else
                         "red" if sentiment == "Negative" else "orange")
                st.markdown(f"<span style='color:{color}; font-weight:600'>"
                            f"{sentiment}</span>", unsafe_allow_html=True)
                st.write(news.get("summary", ""))

                st.markdown("**📊 Sector Analysis**")
                sector_data = research.get("sector_headwinds", {})
                st.write(f"**Health:** {sector_data.get('sector_health','N/A')}")
                st.write(sector_data.get("summary", ""))

            with col2:
                st.markdown("**⚖️ Litigation**")
                lit = research.get("litigation", {})
                risk = lit.get("litigation_risk", "N/A")
                color = ("red" if risk == "High" else
                         "orange" if risk == "Medium" else "green")
                st.markdown(f"<span style='color:{color}; font-weight:600'>"
                            f"Risk: {risk}</span>", unsafe_allow_html=True)
                st.write(lit.get("summary", ""))

                st.markdown("**🏛️ Regulatory**")
                reg = research.get("regulatory", {})
                st.write(f"**Risk:** {reg.get('regulatory_risk','N/A')}")
                st.write(reg.get("summary", ""))

            overall = research.get("overall_sentiment", {})
            if overall:
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Top Risks**")
                    for r in overall.get("top_risks", []):
                        st.markdown(f"<div class='red-flag-item'>🔴 {r}</div>",
                                    unsafe_allow_html=True)
                with col2:
                    st.markdown("**Positive Factors**")
                    for pf in overall.get("positive_factors", []):
                        st.markdown(f"- 🟢 {pf}")

    # Tab 4 — Risk Signals
    with tab4:
        fin       = st.session_state.financials or {}
        red_flags = fin.get("red_flags", {})
        flags     = red_flags.get("red_flags", [])
        gst       = fin.get("gst_analysis", {})

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🚨 Document Red Flags**")
            if flags:
                for flag in flags:
                    st.markdown(
                        f"<div class='red-flag-item'>🔴 {flag}</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.success("✅ No significant red flags")

            st.markdown("**🔄 GST Analysis**")
            if gst and not gst.get("parse_error"):
                if gst.get("gstr_mismatch_detected"):
                    st.error(f"⚠️ GSTR Mismatch: {gst.get('mismatch_details','')}")
                else:
                    st.success("✅ No GSTR mismatch")
                if gst.get("circular_trading_risk"):
                    st.error("⚠️ Circular Trading Risk Detected")
                else:
                    st.success("✅ No circular trading patterns")
            else:
                st.info("GST data not found in documents.")

        with col2:
            st.markdown("**📊 Penalty Analysis**")
            fs = rec.get("final_score", 0)
            try:
                fs = float(fs)
            except Exception:
                fs = 0
            if fs < 60:
                st.error(f"⚠️ Score penalties applied. Final: {fs}/100")
            else:
                st.success(f"✅ Score: {fs}/100")

            if st.session_state.cross_ref:
                st.markdown("**🔗 Cross-Document Integrity**")
                integrity = st.session_state.cross_ref.get(
                    "overall_integrity_score", {}
                )
                verdict = integrity.get("verdict", "N/A")
                if verdict == "CLEAN":
                    st.success(f"✅ Integrity: {verdict} ({integrity.get('score')}/100)")
                elif verdict == "SUSPECT":
                    st.warning(f"⚠️ Integrity: {verdict} ({integrity.get('score')}/100)")
                else:
                    st.error(f"🚨 Integrity: {verdict} ({integrity.get('score')}/100)")

    # Tab 5 — Decision Rationale
    with tab5:
        st.markdown(f"**Decision: `{decision}`**")
        st.write(rec.get("decision_rationale", ""))

        if rec.get("rejection_reason"):
            st.error(f"**Rejection Reason:** {rec['rejection_reason']}")

        conditions = rec.get("key_conditions", [])
        if conditions:
            st.markdown("**Conditions Precedent:**")
            for i, c in enumerate(conditions, 1):
                st.markdown(f"{i}. {c}")

        st.markdown("**Five Cs Rationale:**")
        for label, key in [
            ("Character",  "character_rationale"),
            ("Capacity",   "capacity_rationale"),
            ("Capital",    "capital_rationale"),
            ("Collateral", "collateral_rationale"),
            ("Conditions", "conditions_rationale"),
        ]:
            with st.expander(label):
                st.write(five_cs.get(key, "N/A"))

    # ── Real-Time Re-Score ────────────────────────────────────
    st.markdown("---")
    st.markdown("**⚡ Real-Time Score Adjustment**")
    st.caption("Add new field observations to instantly re-score without re-running full analysis")

    new_notes = st.text_area(
        "Additional Field Notes",
        placeholder="e.g. Follow-up visit: Factory now at 20% capacity. MD confirmed order book decline...",
        height=80,
        key="new_notes_input",
        label_visibility="collapsed",
    )

    if st.button("⚡  RE-SCORE WITH NEW NOTES"):
        if new_notes and st.session_state.financials:
            with st.spinner("Re-scoring..."):
                from agents.scoring_agent import ScoringAgent
                sa = ScoringAgent(
                    company_name=st.session_state.company_name,
                    financials=st.session_state.financials,
                    research=st.session_state.research,
                    manual_notes=new_notes,
                )
                nr = sa.run()
                st.session_state.five_cs        = nr["five_cs"]
                st.session_state.recommendation = nr["recommendation"]
                new_score  = nr["recommendation"].get("final_score")
                new_rating = nr["recommendation"].get("rating")
                st.success(f"✅ Score updated: {new_score}/100 | Rating: {new_rating}")
                st.rerun()

    # ── Download CAM ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("**📥 Download Credit Appraisal Memo**")

    if st.session_state.cam_path and os.path.exists(st.session_state.cam_path):
        with open(st.session_state.cam_path, "rb") as f:
            cam_bytes = f.read()
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.download_button(
                label="📄  Download CAM (Word Document)",
                data=cam_bytes,
                file_name=f"CAM_{company_name.replace(' ','_')}.docx",
                mime="application/vnd.openxmlformats-officedocument"
                     ".wordprocessingml.document",
                use_container_width=True,
            )
            st.caption("Professional Credit Appraisal Memo — Ready for review")

    # ── Raw Output ────────────────────────────────────────────
    if show_raw:
        st.markdown("---")
        st.markdown("**🔧 Raw Agent Output**")
        with st.expander("Financial Extraction"):
            st.json(st.session_state.financials or {})
        with st.expander("Cross-Reference Results"):
            st.json(st.session_state.cross_ref or {})
        with st.expander("Research Intelligence"):
            st.json(st.session_state.research or {})
        with st.expander("Scoring Results"):
            st.json({
                "five_cs":        st.session_state.five_cs,
                "recommendation": st.session_state.recommendation,
            })