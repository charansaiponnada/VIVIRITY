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
.hero h1 { font-size: 2.8rem; font-weight: 700; margin: 0; letter-spacing: -1px; }
.hero p  { font-size: 1.1rem; opacity: 0.85; margin: 0.5rem 0 1rem 0; }
.hero-tags span {
    background: rgba(201,168,76,0.2); border: 1px solid rgba(201,168,76,0.5);
    color: #C9A84C; padding: 4px 12px; border-radius: 20px;
    font-size: 0.75rem; font-weight: 600; margin-right: 8px;
}
.metric-card {
    background: white; border: 1px solid #e8ecf0; border-radius: 12px;
    padding: 1.2rem; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.metric-card .label { font-size: 0.75rem; color: #7f8c8d; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
.metric-card .value { font-size: 2rem; font-weight: 700; color: #1B3A6B; margin: 4px 0; }
.metric-card .sub   { font-size: 0.85rem; color: #95a5a6; }
.decision-approve     { background: #1E8449; color: white; padding: 1rem 2rem; border-radius: 12px; text-align: center; font-size: 1.4rem; font-weight: 700; }
.decision-conditional { background: #D68910; color: white; padding: 1rem 2rem; border-radius: 12px; text-align: center; font-size: 1.4rem; font-weight: 700; }
.decision-reject      { background: #C0392B; color: white; padding: 1rem 2rem; border-radius: 12px; text-align: center; font-size: 1.4rem; font-weight: 700; }
.section-header {
    font-size: 0.8rem; font-weight: 700; color: #1B3A6B; text-transform: uppercase;
    letter-spacing: 1.5px; border-bottom: 2px solid #1B3A6B;
    padding-bottom: 6px; margin: 1.5rem 0 1rem 0;
}
.c-bar-container { margin: 8px 0; }
.c-bar-outer { background: #ecf0f1; border-radius: 6px; height: 20px; width: 100%; }
.c-bar-inner { height: 20px; border-radius: 6px; display: flex; align-items: center; padding-left: 8px; }
.c-bar-text  { font-size: 0.75rem; font-weight: 600; color: white; }
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
    a2a_mode = st.toggle("A2A Protocol Mode", value=False,
                          help="Enable Google A2A protocol server for agent-to-agent communication")
    if a2a_mode:
        st.success("A2A Protocol: Active")
        st.caption("POST http://localhost:5000/a2a")
        st.caption("Agent Card: /.well-known/agent.json")
    st.markdown("---")
    st.markdown("**AGENT PIPELINE**")
    agent_placeholders = {k: st.empty() for k in [
        "Doc Classifier", "Data Ingestor", "Cross-Reference",
        "Research Agent", "Scoring Agent",  "CAM Generator",
    ]}
    for k in agent_placeholders:
        agent_placeholders[k].markdown(f"⚪ {k}")
    st.markdown("---")
    st.caption("Vivriti Capital Hackathon 2026\nIIT Hyderabad · YUVAAN 2026")

def set_agent(name, status):
    icon = {"pending":"⚪","running":"🔄","done":"✅","error":"❌"}.get(status,"⚪")
    agent_placeholders[name].markdown(f"{icon} {name}")


def _is_missing(val):
    if val is None:
        return True
    if isinstance(val, str) and val.strip().lower() in {"", "none", "null", "n/a", "na"}:
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
        if _is_missing(value):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            m = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
            if m:
                try:
                    return float(m.group(0))
                except Exception:
                    return value
        return value

    # Tag fields already present in primary extraction as annual_report sourced.
    tracked_fields = [
        "revenue_crores",
        "profit_after_tax_crores",
        "ebitda_crores",
        "debt_equity_ratio",
        "current_ratio",
        "net_worth_crores",
        "external_credit_rating",
        "company_name",
    ]
    for f in tracked_fields:
        if not _is_missing(fin.get(f)):
            source_map[f] = "annual_report"

    # Normalize alternate key names to app/scoring canonical keys.
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

    # Pull from supporting structured docs when annual-report extraction is sparse.
    gst = all_docs.get("gst_filing", {})
    itr = all_docs.get("itr_filing", {})
    bank = all_docs.get("bank_statement", {})

    if _is_missing(fin.get("revenue_crores")):
        for source_name, source_doc, key in [
            ("gst_filing", gst, "revenue_crores"),
            ("itr_filing", itr, "revenue_crores"),
            ("bank_statement", bank, "revenue_crores"),
        ]:
            if not _is_missing(source_doc.get(key)):
                fin["revenue_crores"] = source_doc.get(key)
                backfilled.append(f"revenue_crores<-{source_name}.{key}")
                source_map["revenue_crores"] = source_name
                break

    # Derive D/E if not present but components exist.
    if _is_missing(fin.get("debt_equity_ratio")):
        try:
            debt = float(fin.get("total_borrowings_crores"))
            nw = float(fin.get("net_worth_crores"))
            if nw > 0:
                fin["debt_equity_ratio"] = round(debt / nw, 2)
                backfilled.append("debt_equity_ratio<-computed")
                source_map["debt_equity_ratio"] = "computed"
        except Exception:
            pass

    # Research can contribute rating when financial extraction misses it.
    if _is_missing(fin.get("external_credit_rating")):
        ext_rating = research.get("external_credit_rating") or research.get("company_news", {}).get("external_credit_rating")
        if not _is_missing(ext_rating):
            fin["external_credit_rating"] = ext_rating
            backfilled.append("external_credit_rating<-research")
            source_map["external_credit_rating"] = "research"

    # Backfill core financial metrics from structured research snapshot when docs are sparse.
    research_snapshot = research.get("financial_snapshot", {}) if isinstance(research, dict) else {}
    research_metric_map = {
        "revenue_crores": "revenue_crores",
        "profit_after_tax_crores": "profit_after_tax_crores",
        "ebitda_crores": "ebitda_crores",
        "debt_equity_ratio": "debt_equity_ratio",
        "current_ratio": "current_ratio",
        "net_worth_crores": "net_worth_crores",
    }
    for fin_key, research_key in research_metric_map.items():
        if _is_missing(fin.get(fin_key)) and not _is_missing(research_snapshot.get(research_key)):
            fin[fin_key] = _coerce_num(research_snapshot.get(research_key))
            backfilled.append(f"{fin_key}<-research.{research_key}")
            source_map[fin_key] = "research"

    # Keep company name populated in summary even if parser missed identity fields.
    if _is_missing(fin.get("company_name")) and company_name:
        fin["company_name"] = company_name
        source_map["company_name"] = "manual_input"

    return fin, backfilled, source_map

# ── Inputs ───────────────────────────────────────────────────────────────── #
col_l, col_r = st.columns([1.2, 1])
with col_l:
    st.markdown('<div class="section-header">01 / UPLOAD DOCUMENTS</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Upload all available documents for the company",
        type=["pdf", "json", "csv"], accept_multiple_files=True,
        help="Annual Reports (PDF), GST Returns (PDF/JSON), ITR (PDF/JSON), Bank Statements (PDF/CSV), Legal Notices, Sanction Letters, Rating Reports",
    )
    if uploaded_files:
        st.caption(f"✅ {len(uploaded_files)} file(s) uploaded")
        for f in uploaded_files:
            st.caption(f"📄 {f.name} — {f.size/1024/1024:.1f} MB")

with col_r:
    st.markdown('<div class="section-header">02 / COMPANY DETAILS</div>', unsafe_allow_html=True)
    company_name = st.text_input("Company Name *", placeholder="e.g. Tata Motors Limited")
    promoters    = st.text_input("Promoter Names", placeholder="e.g. N. Chandrasekaran")
    sector       = st.selectbox("Industry Sector", [
        "Manufacturing","Automobile","Banking","NBFC / Financial Services",
        "Insurance","Infrastructure","Real Estate","FMCG","Pharma",
        "Textile","Steel / Metals","IT / Technology","Other",
    ])
    loan_amount  = st.text_input("Requested Loan Amount (₹ Crores)", placeholder="e.g. 500")
    loan_purpose = st.text_input("Loan Purpose", placeholder="e.g. Working Capital Expansion")

st.markdown('<div class="section-header">03 / CREDIT OFFICER FIELD NOTES</div>', unsafe_allow_html=True)
manual_notes = st.text_area(
    "Qualitative observations from site visits and management interviews",
    placeholder="e.g. Factory found operating at 40% capacity. Management was cooperative.",
    height=90,
)

st.markdown('<div class="section-header">04 / RUN ANALYSIS</div>', unsafe_allow_html=True)
run_btn = st.button("⚡ Run Credit Analysis", type="primary", width="stretch")

# ── Run ──────────────────────────────────────────────────────────────────── #
if run_btn:
    if not company_name:
        st.error("Please enter a Company Name before running analysis.")
        st.stop()

    for key in ["analysis_done","financials","research","scoring_results","cross_ref","cam_path"]:
        st.session_state[key] = {} if key not in ["analysis_done","cam_path"] else (False if key=="analysis_done" else "")

    st.session_state["company_name"]  = company_name
    st.session_state["manual_notes"]  = manual_notes
    st.session_state["promoters"]     = promoters
    st.session_state["sector"]        = sector
    st.session_state["loan_amount"]   = loan_amount
    st.session_state["loan_purpose"]  = loan_purpose

    log_placeholder = st.empty()
    log_lines: list[str] = []

    def log(msg, level="info"):
        icon = {"info":"ℹ️","success":"✅","warning":"⚠️","error":"❌"}.get(level,"ℹ️")
        ts   = datetime.now().strftime("%H:%M:%S")
        log_lines.append(f"`{ts}` {icon} {msg}")
        log_placeholder.markdown("**📋 Live Processing Log**\n\n" + "\n\n".join(log_lines[-20:]))

    # Save uploads
    temp_paths = []
    if uploaded_files:
        tmp_dir = tempfile.mkdtemp()
        for f in uploaded_files:
            p = os.path.join(tmp_dir, f.name)
            with open(p, "wb") as fh: fh.write(f.getvalue())
            temp_paths.append(p)

    # ── Ingestor ─────────────────────────────────────────────────────────── #
    try:
        from utils.indian_context import detect_entity_type
        pre_entity_type = detect_entity_type(
            company_name=company_name,
            cin="",
            sector_input=sector,
        )
    except Exception:
        pre_entity_type = "corporate"

    set_agent("Doc Classifier", "running"); set_agent("Data Ingestor", "running")
    financials = {}
    if temp_paths:
        try:
            from agents.ingestor_agent import IngestorAgent
            financials = IngestorAgent(
                file_paths=temp_paths,
                log_callback=log,
                entity_type=pre_entity_type,
            ).run()
            set_agent("Doc Classifier", "done"); set_agent("Data Ingestor", "done")
        except Exception as e:
            log(f"Ingestor error: {e}", "error")
            set_agent("Doc Classifier", "error"); set_agent("Data Ingestor", "error")
    else:
        log("No documents uploaded — skipping ingestion.", "warning")
        set_agent("Doc Classifier", "done"); set_agent("Data Ingestor", "done")

    primary_fin = financials.get("annual_report") or \
                  (financials.get(list(financials.keys())[0]) if financials else {})

    # ── Entity Type Detection (bank / nbfc / insurance / corporate) ───── #
    try:
        from utils.indian_context import detect_entity_type
        entity_type = detect_entity_type(
            company_name=company_name,
            cin=primary_fin.get("cin", "") if isinstance(primary_fin, dict) else "",
            sector_input=sector,
        )
        if isinstance(primary_fin, dict):
            primary_fin["_entity_type"] = entity_type
        log(f"Entity type detected: {entity_type.upper()}", "success")
    except Exception as e:
        entity_type = "corporate"
        log(f"Entity detection fallback to CORPORATE: {e}", "warning")

    st.session_state["financials"] = primary_fin
    st.session_state["financials_all"] = financials

    # ── Cross-reference ───────────────────────────────────────────────────── #
    set_agent("Cross-Reference", "running")
    try:
        from agents.cross_reference_agent import CrossReferenceAgent
        if len(financials) >= 2:
            cross_ref = CrossReferenceAgent(documents=financials).run()
        else:
            cross_ref = {
                "cross_reference_performed": False,
                "reason": "Single document uploaded — cross-reference skipped. Upload GST filing or bank statement alongside annual report for fraud detection.",
                "flags": [], "circular_trading_risk": "Unknown", "revenue_inflation_risk": "Unknown",
            }
            log("Single document uploaded — cross-reference skipped. Upload GST filing or bank statement alongside annual report for fraud detection.", "warning")
        st.session_state["cross_ref"] = cross_ref
        set_agent("Cross-Reference", "done")
    except Exception as e:
        log(f"Cross-reference error: {e}", "error")
        cross_ref = {"cross_reference_performed": False, "reason": str(e), "flags": []}
        st.session_state["cross_ref"] = cross_ref
        set_agent("Cross-Reference", "error")

    # ── Research ──────────────────────────────────────────────────────────── #
    set_agent("Research Agent", "running")
    log(f"Searching: {company_name} news, litigation, promoters, sector headwinds...")
    try:
        from agents.research_agent import ResearchAgent
        research = ResearchAgent(company_name=company_name, sector=sector, promoters=promoters).run()
        primary_fin, backfilled_fields, fin_source_map = _enrich_financials(primary_fin, financials, research, company_name)
        st.session_state["financials"] = primary_fin
        st.session_state["financials_source_map"] = fin_source_map
        if backfilled_fields:
            log(f"Backfilled financial fields: {', '.join(backfilled_fields)}", "info")
        st.session_state["research"] = research
        log("Web research and synthesis complete", "success")
        set_agent("Research Agent", "done")
    except Exception as e:
        log(f"Research error: {e}", "error")
        research = {}; st.session_state["research"] = research
        set_agent("Research Agent", "error")

    # ── Scoring ───────────────────────────────────────────────────────────── #
    set_agent("Scoring Agent", "running")
    log("Computing weighted Five Cs score with penalty adjustments...")
    try:
        from agents.scoring_agent import ScoringAgent
        sa = ScoringAgent(
            company_name=company_name,
            financials=primary_fin,
            research=research,
            manual_notes=manual_notes,
            loan_purpose=loan_purpose,
            entity_type=entity_type,
        )
        scoring_results = sa.run()
        st.session_state["scoring_results"]   = scoring_results
        st.session_state["scoring_agent_ref"] = sa
        rec    = scoring_results.get("recommendation", {})
        score  = rec.get("final_score",  scoring_results.get("risk_score",{}).get("final_score",0))
        rating = rec.get("rating",       scoring_results.get("risk_score",{}).get("rating","N/A"))
        dec    = rec.get("decision",     "N/A")
        log(f"Score: {score}/100 | Rating: {rating} | Decision: {dec}", "success")
        set_agent("Scoring Agent", "done")

        # ── ML Model (hackathon: "ML based recommendation") ──────────── #
        ml_results = {}
        if ML_AVAILABLE:
            try:
                ml_model   = MLCreditModel()
                ml_results = ml_model.predict(primary_fin, research, manual_notes)
                ml_score   = ml_results.get("ml_score", 0)
                ml_rating  = ml_results.get("ml_rating", "N/A")
                ml_dec     = ml_results.get("ml_decision", "N/A")
                log(f"ML Model: P(lend)={ml_results.get('ml_probability_of_lending',0):.2f} | Rating: {ml_rating} | Decision: {ml_dec}", "success")
            except Exception as e:
                log(f"ML model error (non-critical): {e}", "warning")
        st.session_state["ml_results"] = ml_results

        # Re-run recommendation with ML blend (FIX #2)
        # Use session_state ml_results to ensure it's populated even if local var is empty
        _ml_for_blend = st.session_state.get("ml_results") or ml_results
        if _ml_for_blend and scoring_results:
            try:
                agent_ref = st.session_state.get("scoring_agent_ref")
                if agent_ref:
                    blend_rec = agent_ref.generate_recommendation(
                        scoring_results.get("five_cs", {}),
                        scoring_results.get("risk_score", {}),
                        ml_results=_ml_for_blend
                    )
                    scoring_results["recommendation"] = blend_rec
                    scoring_results["blend_applied"] = True
                    st.session_state["scoring_results"] = scoring_results
                    final_score = blend_rec.get("final_score", 0)
                    rating = blend_rec.get("rating", "N/A")
                    dec = blend_rec.get("decision", "N/A")
                    log(f"Blended Score: {final_score}/100 | Rating: {rating} | Decision: {dec}", "success")
            except Exception as e:
                log(f"Blend step (non-critical): {e}", "warning")

        # ── Databricks Gold layer write ────────────────────────────────── #
        if ML_AVAILABLE:
            try:
                db_layer = DatabricksDataLayer()
                db_layer.write_bronze("annual_report", company_name, primary_fin)
                db_layer.write_gold_scores(company_name, scoring_results, ml_results)
                log(f"Databricks: Bronze + Gold layers written", "success")
                st.session_state["databricks_audit"] = db_layer.get_audit_trail()
            except Exception as e:
                log(f"Databricks write (non-critical): {e}", "warning")

    except Exception as e:
        log(f"Scoring error: {e}", "error")
        scoring_results = {}; st.session_state["scoring_results"] = scoring_results
        set_agent("Scoring Agent", "error")

    # ── CAM ───────────────────────────────────────────────────────────────── #
    set_agent("CAM Generator", "running")
    log("Generating professional Credit Appraisal Memo (Word document)...")
    try:
        from agents.cam_agent import CAMAgent
        cam_path = CAMAgent(
            company_name=company_name, financials=primary_fin,
            research=research, scoring=scoring_results, cross_ref=cross_ref,
            manual_notes=manual_notes, loan_amount=loan_amount,
            loan_purpose=loan_purpose, output_dir="outputs",
        ).run()
        st.session_state["cam_path"] = cam_path
        log(f"CAM generated: {cam_path}", "success")
        set_agent("CAM Generator", "done")
    except Exception as e:
        log(f"CAM generation error: {e}", "error")
        st.session_state["cam_path"] = ""
        set_agent("CAM Generator", "error")

    log("Analysis complete — CAM ready for download", "success")
    st.session_state["log_lines"]    = log_lines
    st.session_state["analysis_done"] = True

# ── Results display ───────────────────────────────────────────────────────── #
if st.session_state.get("analysis_done"):
    sr       = st.session_state.get("scoring_results", {})
    fin      = st.session_state.get("financials",      {})
    research = st.session_state.get("research",        {})
    xref     = st.session_state.get("cross_ref",       {})
    cam_path = st.session_state.get("cam_path",        "")
    cname    = st.session_state.get("company_name",    "")
    mnotes   = st.session_state.get("manual_notes",    "")
    fin_source_map = st.session_state.get("financials_source_map", {})
    sector_v = st.session_state.get("sector",          "Other")
    promoters_v = st.session_state.get("promoters",    "")
    loan_amount_v = st.session_state.get("loan_amount", "")
    loan_purpose_v = st.session_state.get("loan_purpose", "")

    rec        = sr.get("recommendation", {})
    risk_score = sr.get("risk_score",     {})
    five_cs    = sr.get("five_cs",        {})
    ml_results = st.session_state.get("ml_results", {})
    db_audit   = st.session_state.get("databricks_audit", [])

    def fmt_cr(val):
        """Format crore value cleanly — never shows ₹None Cr."""
        if val is None or str(val).strip() in ("None", "", "null"):
            return "N/A"
        try:
            return f"₹{float(val):,.0f} Cr"
        except Exception:
            return str(val)

    def fmt_val(val, suffix=""):
        if val is None or str(val).strip() in ("None", "", "null"):
            return "N/A"
        try:
            return f"{float(val):.2f}{suffix}"
        except Exception:
            return str(val)

    score    = rec.get("final_score",              risk_score.get("final_score", 0))
    rating   = rec.get("rating",                   risk_score.get("rating", "N/A"))
    decision = rec.get("decision",                  "N/A")
    amount   = rec.get("recommended_amount_crores", "N/A")
    rate     = rec.get("interest_rate_percent",     "N/A")
    tenure   = rec.get("tenure_months",             "N/A")

    st.markdown("---")
    st.markdown("## CREDIT ANALYSIS RESULTS")

    # Warn prominently if AI scoring failed — per hackathon explainability requirement
    if sr.get("risk_score", {}).get("scoring_failed") or decision == "CANNOT_ASSESS":
        st.error(
            "⚠️ **AI SCORING ENGINE FAILED** — Scores shown are NOT valid. "
            "A manual credit underwriter must review this application before any lending decision. "
            f"Reason: {sr.get('risk_score',{}).get('failure_reason','Unknown')}"
        )

    banner_cls = {
        "APPROVE":             "decision-approve",
        "CONDITIONAL_APPROVE": "decision-conditional",
        "REJECT":              "decision-reject",
        "CANNOT_ASSESS":       "decision-reject",
    }.get(decision, "decision-reject")
    st.markdown(f'<div class="{banner_cls}">DECISION: {decision}</div>', unsafe_allow_html=True)

    if decision == "REJECT":
        rejection_reason = rec.get("rejection_reason") or rec.get("decision_rationale") or "Credit score below minimum threshold."
        st.error(f"**LOAN APPLICATION REJECTED** — {rejection_reason}")
    st.markdown("")

    c1,c2,c3,c4,c5 = st.columns(5)
    for col, label, val, sub in [
        (c1,"CREDIT SCORE",f"{score}/100","Weighted Five Cs"),
        (c2,"RATING",str(rating),"Vivriti Scale"),
        (c3,"AMOUNT",f"₹{amount} Cr" if amount not in ["N/A",None] else "N/A","Recommended"),
        (c4,"RATE",f"{rate}%" if rate not in ["N/A",None] else "N/A","Interest p.a."),
        (c5,"TENURE",f"{tenure}M" if tenure not in ["N/A",None] else "N/A","Months"),
    ]:
        col.markdown(f'<div class="metric-card"><div class="label">{label}</div><div class="value">{val}</div><div class="sub">{sub}</div></div>', unsafe_allow_html=True)

    st.markdown("")
    st.markdown('<div class="section-header">FIVE Cs ASSESSMENT</div>', unsafe_allow_html=True)

    cs_items = [
        ("👤 CHARACTER","character","25%","#1B3A6B"),
        ("💰 CAPACITY","capacity","30%","#2471A3"),
        ("🏛️ CAPITAL","capital","20%","#1E8449"),
        ("🔒 COLLATERAL","collateral","15%","#D68910"),
        ("🌍 CONDITIONS","conditions","10%","#884EA0"),
    ]
    cols = st.columns(5)
    for col,(label,key,weight,color) in zip(cols, cs_items):
        s = five_cs.get(f"{key}_score", 0) or 0
        r = five_cs.get(f"{key}_rationale", "N/A")
        col.markdown(f"""
<div class="c-bar-container">
  <div style="font-size:0.85rem;font-weight:600;color:#2c3e50">{label}<br><small style="color:#7f8c8d">{weight}</small></div>
  <div class="c-bar-outer"><div class="c-bar-inner" style="width:{s}%;background:{color}"><span class="c-bar-text">{s}</span></div></div>
</div>""", unsafe_allow_html=True)
        col.caption(str(r)[:120] + ("..." if len(str(r)) > 120 else ""))

    st.markdown("")

    tab1,tab2,tab3,tab4,tab5,tab6,tab7,tab8,tab9,tab10 = st.tabs([
        "📊 Command Center", "🛡️ Risk Intelligence", "💰 Financial Health",
        "🏢 Company & Financials","🔗 Cross-Reference",
        "🔍 Research Intelligence","⚠️ Risk Signals",
        "📝 Decision Rationale", "🤖 ML Intelligence", "🔌 A2A Protocol",
    ])

    # ── Dashboard 1: Credit Risk Command Center ──────────────────────── #
    with tab1:
        try:
            from dashboards import render_credit_command_center
            render_credit_command_center(sr, ml_results, fin, cname)
        except Exception as e:
            st.error(f"Dashboard error: {e}")

    # ── Dashboard 2: Risk Intelligence Monitor ───────────────────────── #
    with tab2:
        try:
            from dashboards import render_risk_intelligence
            render_risk_intelligence(sr, research, xref, cname)
        except Exception as e:
            st.error(f"Dashboard error: {e}")

    # ── Dashboard 3: Financial Health Analyzer ───────────────────────── #
    with tab3:
        try:
            from dashboards import render_financial_health
            render_financial_health(fin, sr, cname)
        except Exception as e:
            st.error(f"Dashboard error: {e}")

    with tab4:
        entity_type = fin.get("_entity_type", "corporate")

        def with_source(label: str, value: str, key: str) -> str:
            src = fin_source_map.get(key, "unknown")
            return f"**{label}:** {value}  `[{src}]`"

        a,b = st.columns(2)
        with a:
            st.markdown("**Company Info**")
            st.write(with_source("Name", fin.get('company_name', cname), "company_name"))
            st.write(f"**CIN:** {fin.get('cin','N/A')}")
            st.write(f"**Entity Type:** {str(entity_type).upper()}")
            try:
                from utils.indian_context import deduplicate_persons
                dirs = deduplicate_persons(fin.get("directors",[]) or [])
                promoters_view = deduplicate_persons(fin.get("promoters",[]) or [])
            except Exception:
                dirs = fin.get("directors",[]) or []
                promoters_view = fin.get("promoters",[]) or []
            dirs_str = ", ".join([d.get("name",str(d)) if isinstance(d,dict) else str(d) for d in dirs]) or "N/A"
            st.write(f"**Directors:** {dirs_str}")
            promoters_str = ", ".join([p.get("name",str(p)) if isinstance(p,dict) else str(p) for p in promoters_view]) or (promoters_v or "N/A")
            st.write(f"**Promoters:** {promoters_str}")
        with b:
            st.markdown("**Key Financials**")
            revenue_label = "Total Income" if entity_type in ("bank", "nbfc") else "Gross Premium" if entity_type == "insurance" else "Revenue"
            st.write(with_source(revenue_label, fmt_cr(fin.get('revenue_crores')), "revenue_crores"))
            st.write(with_source("PAT", fmt_cr(fin.get('profit_after_tax_crores')), "profit_after_tax_crores"))

            if entity_type in ("bank", "nbfc"):
                st.write(f"**NII:** {fmt_cr(fin.get('net_interest_income_crores'))}")
                st.write(f"**NIM:** {fmt_val(fin.get('net_interest_margin_percent'), '%')}")
                st.write(f"**Gross NPA:** {fmt_val(fin.get('gross_npa_percent'), '%')}")
                st.write(f"**Capital Adequacy:** {fmt_val(fin.get('capital_adequacy_ratio_percent'), '%')}")
            elif entity_type == "insurance":
                st.write(f"**Solvency Ratio:** {fmt_val(fin.get('solvency_ratio'), 'x')}")
                st.write(f"**Claims Ratio:** {fmt_val(fin.get('claims_ratio_percent'), '%')}")
                st.write(f"**Combined Ratio:** {fmt_val(fin.get('combined_ratio_percent'), '%')}")
            else:
                st.write(with_source("EBITDA", fmt_cr(fin.get('ebitda_crores')), "ebitda_crores"))
                st.write(with_source("D/E Ratio", fmt_val(fin.get('debt_equity_ratio'), 'x'), "debt_equity_ratio"))
                st.write(with_source("Current Ratio", fmt_val(fin.get('current_ratio'), 'x'), "current_ratio"))

            st.write(with_source("Net Worth", fmt_cr(fin.get('net_worth_crores')), "net_worth_crores"))
            st.write(with_source("External Rating", fin.get('external_credit_rating') or research.get('external_credit_rating') or 'N/A', "external_credit_rating"))

    with tab5:
        if xref.get("cross_reference_performed"):
            st.success(f"✅ Compared: {', '.join(xref.get('documents_compared',[]))}")
            st.write(f"**Circular Trading Risk:** {xref.get('circular_trading_risk','N/A')}")
            st.write(f"**Revenue Inflation Risk:** {xref.get('revenue_inflation_risk','N/A')}")
            flags = xref.get("flags",[])
            if flags:
                for f in flags: st.error(f"[{f.get('severity','?')}] **{f.get('type','?')}**: {f.get('description','')}")
            else:
                st.success("No fraud flags detected.")
        else:
            st.info(xref.get("reason","Cross-reference not performed."))

    with tab6:
        if research:
            ov = research.get("overall_sentiment",{})
            if ov:
                rr = rec.get("research_rating", {})
                rr_grade = rr.get("grade", ov.get("risk_rating","N/A"))
                rr_label = rr.get("label", ov.get("preliminary_recommendation","N/A"))
                st.write(f"**Research Rating:** {rr_grade} — {rr_label} | **Preliminary:** {ov.get('preliminary_recommendation','N/A')}")
                if rr.get("evidence"):
                    with st.expander("Research rating evidence"):
                        for e in rr["evidence"]:
                            colour = "green" if e.startswith("+") else "red"
                            st.markdown(f":{colour}[{e}]")
                st.write(ov.get("recommendation_reason",""))
            st.json(research)
        else:
            st.info("No research data.")

    with tab7:
        risks = research.get("overall_sentiment",{}).get("top_risks",[])
        for r in risks: st.warning(f"⚠ {r}")
        rf = fin.get("red_flags",{})
        for k,v in (rf or {}).items():
            if v: st.error(f"🚨 {k.replace('_',' ').title()}")
        penalty = risk_score.get("penalty_applied",0)
        if penalty: st.warning(f"Score penalty: -{penalty} points")
        if not risks and not any((rf or {}).values()):
            st.success("No major risk signals detected.")

    with tab8:
        rationale = rec.get("decision_rationale") or rec.get("rejection_reason") or "N/A"
        st.write(f"**Decision:** `{decision}`")
        st.write(f"**Rationale:** {rationale}")
        conds = rec.get("key_conditions",[])
        if conds:
            st.write("**Key Conditions:**")
            for c in conds: st.write(f"• {c}")
        st.markdown("---")
        st.markdown("**Score Breakdown:**")
        for c_key,c_data in risk_score.get("score_breakdown",{}).items():
            st.write(f"• **{c_key.title()}**: {c_data.get('score',0)} × {c_data.get('weight',0):.0%} = {c_data.get('contribution',0):.1f} pts")
        st.write(f"Weighted: {risk_score.get('weighted_score',0)} — Penalty: -{risk_score.get('penalty_applied',0)} — **Final: {risk_score.get('final_score',0)}/100**")

    with tab9:
        st.markdown("### 🤖 ML-Based Credit Recommendation")
        st.caption("Logistic regression model calibrated on RBI IRAC norms + CRISIL rating migration matrix 2023")

        if ml_results:
            col_ml1, col_ml2, col_ml3, col_ml4 = st.columns(4)
            p_lend = ml_results.get("ml_probability_of_lending", 0)
            col_ml1.metric("P(Lend)", f"{p_lend:.1%}")
            col_ml2.metric("ML Score", f"{ml_results.get('ml_score',0)}/100")
            col_ml3.metric("ML Rating", ml_results.get("ml_rating","N/A"))
            col_ml4.metric("ML Decision", ml_results.get("ml_decision","N/A"))

            st.markdown("**Top Positive Drivers:**")
            for d in ml_results.get("top_positive_drivers", []):
                st.success(f"✅ **{d['feature'].replace('_',' ').title()}** (+{d['contribution']:.3f}) — {d['interpretation']}")

            neg = ml_results.get("top_negative_drivers", [])
            if neg:
                st.markdown("**Top Negative Drivers:**")
                for d in neg:
                    st.error(f"❌ **{d['feature'].replace('_',' ').title()}** ({d['contribution']:.3f}) — {d['interpretation']}")

            with st.expander("🔬 Full Feature Vector"):
                st.json(ml_results.get("features_used", {}))

            info = ml_results.get("model_info", {})
            st.caption(f"Algorithm: {info.get('algorithm','N/A')} | Calibration: {info.get('calibration','N/A')} | Features: {info.get('features',0)}")
        else:
            st.info("ML model results not available. Ensure core/ml_credit_model.py is present.")

        st.markdown("---")
        st.markdown("### 🏗️ Databricks Lakehouse Audit Trail")
        st.caption("Bronze → Silver → Gold pipeline (mirrors Databricks Delta Lake architecture)")
        if db_audit:
            for entry in db_audit:
                icon = {"WRITE_BRONZE":"🥉","PROMOTE_SILVER":"🥈","WRITE_GOLD":"🥇","CROSS_REFERENCE":"🔗"}.get(entry.get("operation",""),"📋")
                st.write(f"{icon} `{entry.get('timestamp','')[:19]}` **{entry.get('operation','')}** → {entry.get('doc_type','')} | {entry.get('notes','')}")
        else:
            st.info("Databricks audit trail not available. Run analysis to populate.")

    with tab10:
        st.markdown("### 🔌 Google A2A Protocol")
        st.caption("Agent-to-Agent open protocol for inter-agent communication (google.github.io/A2A)")

        st.markdown("**Agent Cards** — Each agent exposes a discoverable card at `/.well-known/agent.json`:")
        try:
            from a2a.agent_cards import AGENT_CARDS, get_orchestrator_card
            orch_card = get_orchestrator_card()
            st.write(f"**Orchestrator:** {orch_card.name}")
            st.write(f"*{orch_card.description}*")
            st.markdown("---")
            for name, card in AGENT_CARDS.items():
                with st.expander(f"🤖 {card.name}"):
                    st.write(f"**URL:** `{card.url}`")
                    st.write(f"**Description:** {card.description}")
                    for skill in card.skills:
                        st.write(f"  - **{skill.name}**: {skill.description}")
        except Exception as e:
            st.error(f"A2A module not available: {e}")

        st.markdown("---")
        st.markdown("**Task Lifecycle:** `submitted` → `working` → `completed` / `failed`")
        st.markdown("**Protocol:** JSON-RPC 2.0 over HTTP with SSE streaming support")
        st.code(
            '# Example: Send a task to the orchestrator\n'
            'curl -X POST http://localhost:5000/a2a \\\n'
            '  -H "Content-Type: application/json" \\\n'
            '  -d \'{"jsonrpc":"2.0","method":"tasks/send","id":"1",\n'
            '       "params":{"message":{"role":"user","parts":[{"type":"text","text":"Analyze Tata Motors"}]},\n'
            '       "metadata":{"company_name":"Tata Motors","sector":"Automobile"}}}\'',
            language="bash"
        )

    # ── Re-score ─────────────────────────────────────────────────────────── #
    st.markdown("---")
    st.markdown('<div class="section-header">⚡ REAL-TIME SCORE ADJUSTMENT</div>', unsafe_allow_html=True)
    st.caption("Add new field observations to instantly re-score without re-running full analysis")
    new_notes = st.text_area("Updated field observations", value=mnotes, height=80, key="new_notes_input")
    if st.button("🔄 Re-Score with New Notes", key="rescore_btn"):
        with st.spinner("Re-scoring..."):
            try:
                from agents.scoring_agent import ScoringAgent

                # Rebuild agent from session data so re-score never depends on stale object state.
                entity_type = fin.get("_entity_type", "corporate")
                sa_ref = ScoringAgent(
                    company_name=cname,
                    financials=fin,
                    research=research,
                    manual_notes=new_notes,
                    loan_purpose=loan_purpose_v,
                    entity_type=entity_type,
                )

                upd = sa_ref.run()

                # Keep ML blend parity with the primary run if ML output exists.
                if ml_results and upd:
                    blend_rec = sa_ref.generate_recommendation(
                        upd.get("five_cs", {}),
                        upd.get("risk_score", {}),
                        ml_results=ml_results,
                    )
                    upd["recommendation"] = blend_rec
                    upd["blend_applied"] = True

                st.session_state["scoring_agent_ref"] = sa_ref
                st.session_state["scoring_results"] = upd
                st.session_state["manual_notes"] = new_notes

                ur = upd.get("recommendation", {})
                st.success(f"✅ Re-scored: {ur.get('final_score', 0)}/100 | {ur.get('rating', 'N/A')} | {ur.get('decision', 'N/A')}")
                st.rerun()
            except Exception as e:
                st.error(f"Re-score failed: {e}")

    # ── Download ─────────────────────────────────────────────────────────── #
    st.markdown("---")
    if cam_path and os.path.exists(cam_path):
        st.markdown('<div class="section-header">📥 DOWNLOAD CREDIT APPRAISAL MEMO</div>', unsafe_allow_html=True)
        with open(cam_path, "rb") as fh:
            st.download_button(
                label="📄 Download CAM (.docx)",
                data=fh.read(),
                file_name=os.path.basename(cam_path),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                width="stretch",
            )

        pdf_path = os.path.splitext(cam_path)[0] + ".pdf"
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as fh:
                st.download_button(
                    label="📕 Download CAM (.pdf)",
                    data=fh.read(),
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf",
                    width="stretch",
                )

    # Full-screen export bundle for all tab data and raw artifacts.
    full_export = {
        "generated_at": datetime.now().isoformat(),
        "inputs": {
            "company_name": cname,
            "sector": sector_v,
            "promoters": promoters_v,
            "loan_amount_crores": loan_amount_v,
            "loan_purpose": loan_purpose_v,
            "manual_notes": st.session_state.get("manual_notes", ""),
        },
        "summary": {
            "final_score": score,
            "rating": rating,
            "decision": decision,
            "recommended_amount_crores": amount,
            "interest_rate_percent": rate,
            "tenure_months": tenure,
        },
        "tabs": {
            "command_center": {
                "recommendation": rec,
                "risk_score": risk_score,
                "five_cs": five_cs,
            },
            "risk_intelligence": {
                "risk_signals_detail": rec.get("risk_signals_detail", []),
                "fraud_signals": rec.get("fraud_signals", []),
                "fraud_risk_level": rec.get("fraud_risk_level", "LOW"),
                "risk_timeline": rec.get("risk_timeline", []),
            },
            "financial_health": fin,
            "company_financials": fin,
            "cross_reference": xref,
            "research_intelligence": research,
            "risk_signals": {
                "top_risks": research.get("overall_sentiment", {}).get("top_risks", []),
                "red_flags": fin.get("red_flags", {}),
                "penalty_applied": risk_score.get("penalty_applied", 0),
            },
            "decision_rationale": {
                "decision": decision,
                "decision_rationale": rec.get("decision_rationale"),
                "key_conditions": rec.get("key_conditions", []),
                "score_breakdown": risk_score.get("score_breakdown", {}),
            },
            "ml_intelligence": {
                "ml_results": ml_results,
                "databricks_audit": db_audit,
            },
            "a2a_protocol": {
                "enabled": True,
                "endpoint": "http://localhost:5000/a2a",
                "agent_card": "/.well-known/agent.json",
            },
        },
        "processing_log": st.session_state.get("log_lines", []),
        "raw_agent_output": {
            "financial_extraction": fin,
            "cross_reference": xref,
            "research": research,
            "scoring": sr,
        },
    }
    st.download_button(
        label="📦 Download Full Analysis (.json)",
        data=json.dumps(full_export, indent=2, ensure_ascii=True),
        file_name=f"{cname.replace(' ', '_').lower() or 'credit_analysis'}_full_output.json",
        mime="application/json",
        width="stretch",
    )

    # ── Live Processing Log (persisted) ──────────────────────────────────── #
    st.markdown("---")
    st.markdown('<div class="section-header">📋 PROCESSING LOG</div>', unsafe_allow_html=True)
    persisted_log = st.session_state.get("log_lines", [])
    if persisted_log:
        log_html = "<br>".join(persisted_log)
        st.markdown(
            f"""<div style="background:#0d1117;color:#58a6ff;font-family:'IBM Plex Mono',monospace;
            font-size:0.8rem;padding:1rem;border-radius:8px;max-height:280px;overflow-y:auto;
            border:1px solid #30363d;">{log_html}</div>""",
            unsafe_allow_html=True,
        )

    # ── Raw Agent Output ──────────────────────────────────────────────────── #
    st.markdown("---")
    st.markdown('<div class="section-header">🔧 RAW AGENT OUTPUT</div>', unsafe_allow_html=True)
    with st.expander("📊 Financial Extraction", expanded=False):
        st.json(fin)
    with st.expander("🔗 Cross-Reference Results", expanded=False):
        st.json(xref)
    with st.expander("🔍 Research Intelligence", expanded=False):
        st.json(research)
    with st.expander("⚖️ Scoring Results", expanded=False):
        st.json(sr)