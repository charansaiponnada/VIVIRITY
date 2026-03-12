import os
import json
import time
import re
import tempfile
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ML model and Databricks layer (hackathon requirements)
try:
    from core.ml_credit_model import MLCreditModel
    from core.databricks_layer import DatabricksDataLayer
    ML_AVAILABLE = True
except ImportError as e:
    print(f"[App] ML/Databricks import warning: {e}")
    ML_AVAILABLE = False

st.set_page_config(
    page_title="Intelli-Credit | Vivriti Capital",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.hero {
    background: linear-gradient(135deg, #1B3A6B 0%, #0d2444 60%, #C9A84C 100%);
    padding: 2.5rem 3rem; border-radius: 16px; margin-bottom: 2rem; color: white;
}
.hero h1 { font-size: 2.8rem; font-weight: 700; margin: 0; letter-spacing: -1px; color: white; }
.hero p  { font-size: 1.1rem; opacity: 0.85; margin: 0.5rem 0 1rem 0; color: white; }
.hero-tags span {
    background: rgba(201,168,76,0.2); border: 1px solid rgba(201,168,76,0.5);
    color: #C9A84C; padding: 4px 12px; border-radius: 20px;
    font-size: 0.75rem; font-weight: 600; margin-right: 8px;
}
.metric-card {
    background: rgba(128, 128, 128, 0.05); border: 1px solid rgba(128, 128, 128, 0.1); border-radius: 12px;
    padding: 1.2rem; text-align: center;
}
.metric-card .label { font-size: 0.75rem; color: gray; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
.metric-card .value { font-size: 2rem; font-weight: 700; color: inherit; margin: 4px 0; }
.metric-card .sub   { font-size: 0.85rem; color: gray; }
.section-header {
    font-size: 0.8rem; font-weight: 700; color: #1B3A6B; text-transform: uppercase;
    letter-spacing: 1.5px; border-bottom: 2px solid #1B3A6B;
    padding-bottom: 6px; margin: 1.5rem 0 1rem 0;
}
[data-theme="dark"] .section-header { color: #C9A84C; border-bottom-color: #C9A84C; }
</style>
""", unsafe_allow_html=True)

# ── Hero ─────────────────────────────────────────────────────────────────── #
st.markdown("""
<div class="hero">
    <h1>🏦 INTELLI-CREDIT</h1>
    <p>AI-Powered Corporate Credit Appraisal Engine &nbsp;·&nbsp; Weeks of work in minutes</p>
    <div class="hero-tags">
        <span>VectorLess RAG</span><span>Multi-Agent</span>
        <span>Cross-Document Intelligence</span><span>Indian Context</span><span>Gemini 2.5</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────── #
with st.sidebar:
    st.markdown("### INTELLI-CREDIT\n*by DOMINIX*")
    st.markdown("---")
    st.markdown("**AGENT PIPELINE**")
    agent_placeholders = {k: st.empty() for k in [
        "Doc Classifier", "Data Ingestor", "Cross-Reference",
        "Research Agent", "Scoring Agent",  "CAM Generator",
        "A2A Protocol",
    ]}
    for k in agent_placeholders:
        agent_placeholders[k].markdown(f"⚪ {k}")
    
    st.markdown("---")
    st.markdown("**A2A SERVER STATUS**")
    if st.session_state.get("a2a_thread"):
        st.success("🟢 Running on Port 5000")
    else:
        st.info("⚪ Offline")
        if st.button("🚀 Start A2A Server", key="sb_a2a"):
            from a2a.server import run_a2a_server
            import threading
            t = threading.Thread(target=run_a2a_server, kwargs={"port": 5000}, daemon=True)
            t.start()
            st.session_state.a2a_thread = t
            st.rerun()

    st.markdown("---")
    st.caption("Vivriti Capital Hackathon 2026\nIIT Hyderabad · YUVAAN 2026")

def set_agent(name, status):
    icon = {"pending":"⚪","running":"🔄","done":"✅","error":"❌"}.get(status,"⚪")
    agent_placeholders[name].markdown(f"{icon} {name}")


def _is_missing(val):
    if val is None:
        return True
    if isinstance(val, (list, dict)):
        return len(val) == 0
    if isinstance(val, str):
        if val.strip().lower() in {"", "none", "null", "n/a", "na"}:
            return True
    return False


def _enrich_financials(primary_fin: dict, all_docs: dict, research: dict, company_name: str) -> tuple[dict, list[str], dict]:
    """Backfill missing primary financial fields from structured docs and research signals."""
    fin = dict(primary_fin or {})
    all_docs = all_docs or {}
    research = research or {}
    backfilled = []
    source_map = {}

    def _coerce_num(value):
        if _is_missing(value): return None
        if isinstance(value, (int, float)): return float(value)
        if isinstance(value, str):
            m = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
            if m:
                try: return float(m.group(0))
                except Exception: return value
        return value

    # 1. Inference: If extraction_notes says "debt free", set total_borrowings to 0
    notes = str(fin.get("extraction_notes", "")).lower()
    if _is_missing(fin.get("total_borrowings_crores")) and ("debt free" in notes or "zero debt" in notes):
        fin["total_borrowings_crores"] = 0.0
        backfilled.append("total_borrowings_crores<-inference(notes)")
        source_map["total_borrowings_crores"] = "inference"

    # Tag fields already present
    tracked_fields = ["revenue_crores", "profit_after_tax_crores", "ebitda_crores", "debt_equity_ratio", "current_ratio", "net_worth_crores", "external_credit_rating", "company_name"]
    for f in tracked_fields:
        if not _is_missing(fin.get(f)): source_map[f] = "annual_report"

    # Alias normalization
    alias_map = {
        "profit_after_tax_crores": ["profit_after_tax", "pat_crores", "pat"],
        "net_worth_crores": ["net_worth", "shareholders_funds_crores", "total_equity_crores"],
        "total_borrowings_crores": ["total_borrowings", "borrowings"],
        "revenue_crores": ["revenue", "total_income", "turnover"],
    }
    for canonical, aliases in alias_map.items():
        if _is_missing(fin.get(canonical)):
            for a in aliases:
                if not _is_missing(fin.get(a)):
                    fin[canonical] = fin.get(a)
                    backfilled.append(f"{canonical}<-{a}")
                    source_map[canonical] = f"annual_report:{a}"
                    break

    # Supporting docs (GST, ITR, Bank)
    for src_name in ["gst_filing", "itr_filing", "bank_statement"]:
        doc = all_docs.get(src_name, {})
        if _is_missing(fin.get("revenue_crores")) and not _is_missing(doc.get("revenue_crores")):
            fin["revenue_crores"] = doc.get("revenue_crores")
            backfilled.append(f"revenue_crores<-{src_name}")
            source_map["revenue_crores"] = src_name

    # Ratio derived from components
    if _is_missing(fin.get("debt_equity_ratio")):
        try:
            debt = _coerce_num(fin.get("total_borrowings_crores"))
            nw = _coerce_num(fin.get("net_worth_crores"))
            if debt is not None and nw and nw > 0:
                fin["debt_equity_ratio"] = round(debt / nw, 2)
                backfilled.append("debt_equity_ratio<-computed")
                source_map["debt_equity_ratio"] = "computed"
        except: pass

    # Research backfill
    res_snap = research.get("financial_snapshot", {})
    for fk in ["revenue_crores", "profit_after_tax_crores", "ebitda_crores", "net_worth_crores", "debt_equity_ratio", "current_ratio"]:
        if _is_missing(fin.get(fk)) and not _is_missing(res_snap.get(fk)):
            fin[fk] = _coerce_num(res_snap.get(fk))
            backfilled.append(f"{fk}<-research")
            source_map[fk] = "research"

    if _is_missing(fin.get("company_name")) and company_name:
        fin["company_name"] = company_name
        source_map["company_name"] = "manual_input"

    return fin, backfilled, source_map

# ── Session State Initialization ─────────────────────────────────────────── #
if "step" not in st.session_state:
    st.session_state.step = 1
if "classifications" not in st.session_state:
    st.session_state.classifications = {}
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if "log_lines" not in st.session_state:
    st.session_state.log_lines = []

def next_step(): st.session_state.step += 1
def prev_step(): st.session_state.step -= 1

# ── Navigation Header ────────────────────────────────────────────────────── #
steps = ["Entity Details", "Document Upload", "Review & Schema", "Analysis"]
cols = st.columns(len(steps))
for i, step_label in enumerate(steps):
    step_num = i + 1
    with cols[i]:
        if st.session_state.step == step_num: st.markdown(f"**🔵 Step {step_num}**\n\n**{step_label}**")
        elif st.session_state.step > step_num: st.markdown(f"✅ **Step {step_num}**\n\n{step_label}")
        else: st.markdown(f"⚪ Step {step_num}\n\n{step_label}")
st.markdown("---")

# ── STEP 1: ENTITY & LOAN DETAILS ───────────────────────────────────────── #
if st.session_state.step == 1:
    st.markdown('<div class="section-header">01 / ENTITY ONBOARDING</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.company_name = st.text_input("Company Name *", value=st.session_state.get("company_name", ""), placeholder="e.g. Tata Motors Limited")
        st.session_state.cin = st.text_input("CIN", value=st.session_state.get("cin", ""), placeholder="e.g. L28920MH1945PLC004520")
        st.session_state.sector = st.selectbox("Industry Sector", ["Manufacturing","Automobile","Banking","NBFC / Financial Services","Insurance","Infrastructure","Real Estate","FMCG","Pharma","IT / Technology","Other"], index=0)
    with c2:
        st.session_state.loan_amount = st.text_input("Requested Loan Amount (₹ Crores) *", value=st.session_state.get("loan_amount", ""), placeholder="e.g. 50")
        st.session_state.loan_tenure = st.number_input("Tenure (Months)", 1, 360, int(st.session_state.get("loan_tenure", 36)))
        st.session_state.loan_interest = st.slider("Target Interest Rate (%)", 5.0, 25.0, float(st.session_state.get("loan_interest", 10.5)), 0.25)

    if st.button("Continue to Upload →", type="primary"):
        if not st.session_state.company_name or not st.session_state.loan_amount: st.error("Company Name and Loan Amount are required.")
        else: next_step(); st.rerun()

# ── STEP 2: INTELLIGENT DATA INGESTION ──────────────────────────────────── #
elif st.session_state.step == 2:
    st.markdown('<div class="section-header">02 / DOCUMENT UPLOAD</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Secure Upload Interface", type=["pdf", "json", "csv"], accept_multiple_files=True)
    if uploaded_files: st.session_state.uploaded_files = uploaded_files
    col_b1, col_b2 = st.columns([1, 5])
    if col_b1.button("← Back"): prev_step(); st.rerun()
    if col_b2.button("Run Classification & Review →", type="primary"):
        if not uploaded_files: st.warning("Please upload at least one document.")
        else:
            with st.spinner("Classifying documents..."):
                from agents.document_classifier import DocumentClassifier
                import pdfplumber
                tmp_dir = tempfile.mkdtemp(); classifications = {}
                for f in uploaded_files:
                    p = os.path.join(tmp_dir, f.name)
                    with open(p, "wb") as fh: fh.write(f.getvalue())
                    
                    doc_type = "annual_report" # Default
                    fname_lower = f.name.lower()
                    
                    # 1. Filename-based hint
                    if "gst" in fname_lower: doc_type = "gst_filing"
                    elif "bank" in fname_lower or "statement" in fname_lower: doc_type = "bank_statement"
                    elif "itr" in fname_lower or "tax" in fname_lower: doc_type = "itr_filing"
                    elif "alm" in fname_lower: doc_type = "alm_report"
                    elif "shareholding" in fname_lower: doc_type = "shareholding_pattern"
                    elif "borrowing" in fname_lower or "debt" in fname_lower: doc_type = "borrowing_profile"
                    elif "portfolio" in fname_lower or "cuts" in fname_lower: doc_type = "portfolio_cuts"
                    
                    # 2. Deep content-based for PDFs
                    if f.name.lower().endswith('.pdf'):
                        with pdfplumber.open(p) as pdf:
                            content_type = DocumentClassifier(pdf).classify()
                            # Only override if the content-based classifier actually found something (it defaults to annual_report)
                            if content_type != "annual_report":
                                doc_type = content_type
                            elif doc_type == "annual_report": # If still annual_report, use content-based result anyway
                                doc_type = content_type

                    classifications[f.name] = {"type": doc_type, "path": p, "size": f.size, "approved": True}
                st.session_state.classifications = classifications
                next_step(); st.rerun()

# ── STEP 3: HUMAN-IN-THE-LOOP & DYNAMIC SCHEMA ──────────────────────────── #
elif st.session_state.step == 3:
    st.markdown('<div class="section-header">03 / CLASSIFICATION REVIEW & DYNAMIC SCHEMA</div>', unsafe_allow_html=True)
    doc_types = ["annual_report", "gst_filing", "bank_statement", "itr_filing", "alm_report", "shareholding_pattern", "borrowing_profile", "portfolio_cuts"]
    updated = {}
    for fname, data in st.session_state.classifications.items():
        c1, c2, c3 = st.columns([3, 2, 1])
        c1.write(f"📄 **{fname}**")
        new_type = c2.selectbox(f"Type for {fname}", doc_types, index=doc_types.index(data['type']) if data['type'] in doc_types else 0, key=f"t_{fname}")
        is_app = c3.checkbox("Approve", value=data['approved'], key=f"a_{fname}")
        updated[fname] = {**data, "type": new_type, "approved": is_app}
    st.session_state.classifications = updated
    st.markdown("### Dynamic Extraction Schema")
    c_s1, c_s2 = st.columns(2)
    st.session_state.extract_ratios = c_s1.checkbox("Key Financial Ratios", value=True)
    st.session_state.extract_red_flags = c_s1.checkbox("Red Flags & Contingencies", value=True)
    st.session_state.custom_fields = c_s2.text_area("Custom Fields", value=st.session_state.get("custom_fields", ""), placeholder="e.g. R&D Expenses")
    col_b1, col_b2 = st.columns([1, 5])
    if col_b1.button("← Back"): prev_step(); st.rerun()
    if col_b2.button("⚡ Run Full Credit Analysis →", type="primary"): next_step(); st.rerun()

# ── STEP 4: ANALYSIS & REPORTING ────────────────────────────────────────── #
elif st.session_state.step == 4:
    if not st.session_state.get("analysis_done"):
        cname, sector = st.session_state.company_name, st.session_state.sector
        
        # High-impact status container for better UX
        with st.status("🚀 Deep Credit Analysis in Progress...", expanded=True) as status:
            try:
                from utils.indian_context import detect_entity_type
                st.write("🔍 Identifying entity type and sector context...")
                e_type = detect_entity_type(cname, st.session_state.cin, sector)
                
                from agents.ingestor_agent import IngestorAgent
                t_paths = [d['path'] for d in st.session_state.classifications.values() if d['approved']]
                schema = {"ratios": st.session_state.extract_ratios, "directors": True, "red_flags": st.session_state.extract_red_flags}
                
                st.write("📄 Ingesting and parsing financial documents...")
                set_agent("Data Ingestor", "running")
                def _log_placeholder(msg, lvl="info"): pass # Legacy support
                fin_all = IngestorAgent(t_paths, _log_placeholder, e_type, schema, st.session_state.custom_fields).run()
                
                p_fin = fin_all.get("annual_report") or (list(fin_all.values())[0] if fin_all else {})
                p_fin["_entity_type"] = e_type
                st.session_state.financials_all = fin_all
                set_agent("Data Ingestor", "done")
                
                st.write("🔗 Performing cross-reference and GST validation...")
                from agents.cross_reference_agent import CrossReferenceAgent
                st.session_state.cross_ref = CrossReferenceAgent(fin_all).run()
                
                st.write("🌐 Gathering external intelligence (MCA, e-Courts, News)...")
                from agents.research_agent import ResearchAgent
                res = ResearchAgent(cname, sector).run()
                
                st.write("🧠 Enriching financial data with research signals...")
                p_fin, back, s_map = _enrich_financials(p_fin, fin_all, res, cname)
                st.session_state.financials = p_fin
                st.session_state.financials_source_map = s_map
                st.session_state.research = res
                
                st.write("📈 Calculating risk scores and Pre-Cognitive signals...")
                from agents.scoring_agent import ScoringAgent
                sa = ScoringAgent(cname, p_fin, res, entity_type=e_type)
                sr = sa.run()
                
                # PRE-COGNITIVE SIGNALS (Analytical Depth)
                from core.risk_engine import detect_precognitive_signals
                st.session_state.precognitive_signals = detect_precognitive_signals(res, p_fin)
                
                if ML_AVAILABLE:
                    st.write("🤖 Running ML credit prediction model...")
                    ml_r = MLCreditModel().predict(p_fin, res, "")
                    if ml_r:
                        sr["recommendation"] = sa.generate_recommendation(sr["five_cs"], sr["risk_score"], ml_results=ml_r)
                        st.session_state.ml_results = ml_r
                
                st.session_state.scoring_results = sr
                
                st.write("📝 Generating final Credit Appraisal Memo (CAM)...")
                from agents.cam_agent import CAMAgent
                st.session_state.cam_path = CAMAgent(cname, p_fin, res, sr, st.session_state.cross_ref, output_dir="outputs").run()
                
                status.update(label="✅ Analysis Complete!", state="complete", expanded=False)
                st.session_state.analysis_done = True
                st.rerun()
                
            except Exception as e:
                status.update(label="❌ Analysis Failed", state="error")
                st.error(f"**Critical Error during analysis:** {e}")
                st.exception(e)
                if st.button("Retry"):
                    st.rerun()

# ── Results display ───────────────────────────────────────────────────────── #
if st.session_state.get("analysis_done"):
    sr, fin, res, xref = st.session_state.scoring_results, st.session_state.financials, st.session_state.research, st.session_state.cross_ref
    ml_results, log_lines = st.session_state.get("ml_results", {}), st.session_state.get("log_lines", [])
    precog = st.session_state.get("precognitive_signals", [])
    rec, risk_score, five_cs = sr.get("recommendation", {}), sr.get("risk_score", {}), sr.get("five_cs", {})
    cname, score, rating, decision = st.session_state.company_name, rec.get("final_score", 0), rec.get("rating", "N/A"), rec.get("decision", "N/A")

    # ── TOP ACTION BAR (Improved UX) ─────────────────────────────────────── #
    st.markdown(f"""
    <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 12px; border: 1px solid #e9ecef; margin-bottom: 2rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <div style="font-size: 1.2rem; font-weight: 700; color: #1B3A6B;">🚀 CREDIT DECISION COMPLETE</div>
            <div style="font-size: 0.85rem; color: #6c757d;">Generated at: {datetime.now().strftime("%H:%M")}</div>
        </div>
        <div style="font-size: 1.8rem; font-weight: 800; color: {("#1E8449" if decision=="APPROVE" else "#D68910" if "CONDITIONAL" in decision else "#C0392B")}; margin-bottom: 1.5rem;">
            FINAL RECOMMENDATION: {decision}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Persistent Action Bar
    with st.container():
        act1, act2, act3, act4 = st.columns([1, 1, 1, 1])
        
        cp = st.session_state.get("cam_path")
        # Ensure we have paths even if files are pending
        docx_path = cp if cp and os.path.exists(cp) else None
        pdf_path = cp.replace(".docx", ".pdf") if cp and os.path.exists(cp.replace(".docx", ".pdf")) else None

        if docx_path:
            with open(docx_path, "rb") as f:
                act1.download_button(
                    label="📄 Download CAM (Word)",
                    data=f,
                    file_name=os.path.basename(docx_path),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="btn_docx"
                )
        else:
            act1.button("📄 Word CAM Pending...", disabled=True, use_container_width=True)

        if pdf_path:
            with open(pdf_path, "rb") as f:
                act2.download_button(
                    label="📕 Download CAM (PDF)",
                    data=f,
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf",
                    use_container_width=True,
                    key="btn_pdf"
                )
        else:
            # High-quality fallback if PDF conversion is not available on current host
            act2.button("📕 PDF Export (N/A)", disabled=True, use_container_width=True, help="PDF conversion requires Microsoft Word on host system.")

        full_data = {"company": cname, "scoring": sr, "financials": fin, "research": res, "cross_ref": xref, "precognitive": precog}
        act3.download_button(
            label="🧬 Export JSON Audit",
            data=json.dumps(full_data, indent=2),
            file_name=f"Audit_{cname}.json",
            mime="application/json",
            use_container_width=True,
            key="btn_json"
        )
        
        if act4.button("🔄 Start New Analysis", type="secondary", use_container_width=True, key="btn_new"):
            st.session_state.analysis_done = False
            st.session_state.step = 1
            st.rerun()

    # ── EXPLAINABILITY SUMMARY ─────────────────────────────── #
    with st.container():
        st.markdown("#### 📝 Credit Reasoning & Decision Logic")
        st.info(f"**Primary Driver:** {rec.get('decision_rationale', 'N/A')}")
        
        # Explain the "Why" using the Five Cs rationales
        cols = st.columns(3)
        cols[0].write(f"**Financial Capacity:** {five_cs.get('capacity_rationale', 'N/A')[:120]}...")
        cols[1].write(f"**Solvency (Capital):** {five_cs.get('capital_rationale', 'N/A')[:120]}...")
        cols[2].write(f"**Character & Fraud:** {five_cs.get('character_rationale', 'N/A')[:120]}...")

    st.markdown("---")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("SCORE", f"{score}/100"); c2.metric("RATING", rating); c3.metric("AMOUNT", f"₹{rec.get('recommended_amount_crores','N/A')} Cr"); c4.metric("RATE", f"{rec.get('interest_rate_percent','N/A')}%"); c5.metric("TENURE", f"{rec.get('tenure_months','N/A')}M")

    tabs = st.tabs(["📊 Command Center", "🛡️ Risk Intel", "🚨 Pre-Cognitive", "💰 Financials", "🔍 Specialized", "🔗 Cross-Ref", "🤖 ML", "🔌 A2A"])
    
    with tabs[0]: 
        from dashboards import render_credit_command_center
        render_credit_command_center(sr, ml_results, fin, cname)
    with tabs[1]:
        from dashboards import render_risk_intelligence
        render_risk_intelligence(sr, res, xref, cname, precognitive_signals=precog)
    with tabs[2]:
        st.markdown("### 🚨 Pre-Cognitive Risk Signals")
        st.info("These are leading indicators of future financial stress, detected through deep research and financial trend analysis.")
        if not precog:
            st.success("No critical pre-cognitive risk signals detected.")
        else:
            for p in precog:
                with st.expander(f"Signal: {p['signal']} ({p['impact']})", expanded=True):
                    st.write(f"**Type:** {p['type']}")
                    st.write(f"**Insight:** {p['insight']}")
    with tabs[3]:
        from dashboards import render_financial_health
        render_financial_health(fin, sr, cname)
        st.markdown("---")
        st.markdown("#### 📋 Extraction & Source Audit")
        c_a, c_b = st.columns(2)
        with c_a:
            st.write(f"**CIN:** {fin.get('cin','Not extracted')}")
            if fin.get("extraction_notes"): st.info(f"**Notes:** {fin['extraction_notes']}")
        with c_b:
            dirs = fin.get("directors",[]) or []
            st.write(f"**Directors:** {', '.join([d.get('name',str(d)) if isinstance(d,dict) else str(d) for d in dirs]) or 'Not extracted'}")
        
        # Detailed Table
        metric_keys = [("Revenue", "revenue_crores", "₹ Cr"), ("PAT", "profit_after_tax_crores", "₹ Cr"), ("EBITDA", "ebitda_crores", "₹ Cr"), ("Net Worth", "net_worth_crores", "₹ Cr"), ("Total Debt", "total_borrowings_crores", "₹ Cr"), ("Debt/Equity", "debt_equity_ratio", "x"), ("Current Ratio", "current_ratio", "x")]
        rows = []
        for l, k, u in metric_keys:
            v = fin.get(k); src = st.session_state.get("financials_source_map", {}).get(k, "annual_report")
            rows.append({"Metric": l, "Value": f"{v:,.2f} {u}" if v is not None else "N/A", "Source": src})
        st.table(rows)

    with tabs[4]:
        from dashboards import render_specialized_monitor
        spec_data = st.session_state.financials_all.get("merged_all", st.session_state.financials_all)
        render_specialized_monitor(spec_data, cname)

    with tabs[5]:
        c_x1, c_x2 = st.columns(2)
        with c_x1:
            st.markdown("#### 🔍 Cross-Document Verification")
            if xref.get("cross_reference_performed"): st.json(xref)
            else: st.info(xref.get("reason", "N/A"))
        with c_x2:
            st.markdown("#### ⚠️ Extraction Red Flags")
            for r in res.get("overall_sentiment",{}).get("top_risks",[]): st.warning(r)
            for k,v in fin.get("red_flags",{}).items():
                if v and k not in ["litigation_count", "severity", "source_page"]:
                    st.error(f"**{k.replace('_',' ').title()}:** {v}")

    with tabs[6]:
        if ML_AVAILABLE and ml_results:
            st.markdown("### 🤖 ML Model Intelligence")
            ml_c1, ml_c2 = st.columns(2)
            ml_c1.metric("Lending Prob", f"{ml_results.get('ml_probability_of_lending', 0)*100:.1f}%")
            ml_c1.metric("Risk Tier", ml_results.get("ml_risk_tier", "N/A"))
            ml_c2.write("**Model Confidence & Factors**")
            st.json(ml_results)
            
            st.markdown("#### ⚖️ Five Cs Breakdown")
            for c in ["capacity", "character", "capital", "collateral", "conditions"]:
                with st.expander(f"{c.upper()} Details"):
                    st.write(f"**Score:** {five_cs.get(f'{c}_score', 0)}/100")
                    st.write(f"**Reasoning:** {five_cs.get(f'{c}_rationale', 'N/A')}")
        else:
            st.info("ML model results not available for this analysis.")

    with tabs[7]:
        st.markdown("### 🔌 Google A2A Protocol")
        if "a2a_thread" not in st.session_state: st.session_state.a2a_thread = None
        if st.session_state.a2a_thread is None:
            if st.button("🚀 Start A2A Server", use_container_width=True):
                from a2a.server import run_a2a_server
                import threading
                t = threading.Thread(target=run_a2a_server, kwargs={"port": 5000}, daemon=True); t.start()
                st.session_state.a2a_thread = t; st.success("Started on port 5000"); st.rerun()
        else:
            st.success("🟢 A2A Server Running on Port 5000")
            if st.button("🛑 Stop Server (Restart App)", use_container_width=True):
                st.warning("Restart the Streamlit app to fully release the port.")
        
        from a2a.agent_cards import AGENT_CARDS
        for n, c in AGENT_CARDS.items():
            with st.expander(f"🤖 Agent: {n}"): st.write(c.description)

    # ── REVIEWER DESK (New Feature for UX & Analytical Depth) ────────────── #
    st.markdown("---")
    st.markdown("#### ✍️ Reviewer Desk & Qualitative Overrides")
    with st.container():
        reviewer_notes = st.text_area(
            "Add Qualitative Observations (e.g., Site visit findings, Management evasiveness)",
            value=st.session_state.get("reviewer_notes", ""),
            placeholder="Example: Factory visit revealed 30% idle capacity. Promoter was evasive about subsidiary debt.",
            help="These notes will be synthesized by the AI to adjust the final risk score and decision."
        )
        
        if st.button("⚡ Apply Notes & Re-Score Decision", type="primary", use_container_width=True):
            with st.spinner("Re-calculating risk with qualitative inputs..."):
                st.session_state.reviewer_notes = reviewer_notes
                from agents.scoring_agent import ScoringAgent
                from agents.cam_agent import CAMAgent
                
                # Re-run scoring with the new notes
                sa = ScoringAgent(
                    st.session_state.company_name, fin, res, 
                    manual_notes=reviewer_notes, 
                    entity_type=fin.get("_entity_type", "corporate")
                )
                new_sr = sa.run()
                
                # Re-blend with ML if available
                if ml_results:
                    new_rec = sa.generate_recommendation(new_sr["five_cs"], new_sr["risk_score"], ml_results=ml_results)
                    new_sr["recommendation"] = new_rec
                
                st.session_state.scoring_results = new_sr
                
                # Re-generate CAM with the new notes included
                st.session_state.cam_path = CAMAgent(
                    st.session_state.company_name, fin, res, new_sr, xref, 
                    manual_notes=reviewer_notes, 
                    output_dir="outputs"
                ).run()
                
                st.success("Analysis Updated! Final score and CAM have been adjusted based on your notes.")
                time.sleep(1)
                st.rerun()

    st.markdown("---")
    st.caption(f"Intelli-Credit Analysis System | Vivriti Capital Hackathon 2026")
