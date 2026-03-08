import os
import json
import time
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

# ── Inputs ───────────────────────────────────────────────────────────────── #
col_l, col_r = st.columns([1.2, 1])
with col_l:
    st.markdown('<div class="section-header">01 / UPLOAD DOCUMENTS</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Upload all available documents for the company",
        type=["pdf"], accept_multiple_files=True,
        help="Annual Reports, GST Returns, Bank Statements, Legal Notices, Rating Reports",
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
        "Manufacturing","Automobile","NBFC / Financial Services",
        "Infrastructure","Real Estate","FMCG","Pharma",
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
run_btn = st.button("⚡ Run Credit Analysis", type="primary", use_container_width=True)

# ── Run ──────────────────────────────────────────────────────────────────── #
if run_btn:
    if not company_name:
        st.error("Please enter a Company Name before running analysis.")
        st.stop()

    for key in ["analysis_done","financials","research","scoring_results","cross_ref","cam_path"]:
        st.session_state[key] = {} if key not in ["analysis_done","cam_path"] else (False if key=="analysis_done" else "")

    st.session_state["company_name"]  = company_name
    st.session_state["manual_notes"]  = manual_notes

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
    set_agent("Doc Classifier", "running"); set_agent("Data Ingestor", "running")
    financials = {}
    if temp_paths:
        try:
            from agents.ingestor_agent import IngestorAgent
            financials = IngestorAgent(file_paths=temp_paths, log_callback=log).run()
            set_agent("Doc Classifier", "done"); set_agent("Data Ingestor", "done")
        except Exception as e:
            log(f"Ingestor error: {e}", "error")
            set_agent("Doc Classifier", "error"); set_agent("Data Ingestor", "error")
    else:
        log("No documents uploaded — skipping ingestion.", "warning")
        set_agent("Doc Classifier", "done"); set_agent("Data Ingestor", "done")

    primary_fin = financials.get("annual_report") or \
                  (financials.get(list(financials.keys())[0]) if financials else {})
    st.session_state["financials"] = primary_fin

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
        "CANNOT_ASSESS":       "decision-reject",
    }.get(decision, "decision-reject")
    st.markdown(f'<div class="{banner_cls}">DECISION: {decision}</div>', unsafe_allow_html=True)
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

    tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs([
        "🏢 Company & Financials","🔗 Cross-Reference",
        "🔍 Research Intelligence","⚠️ Risk Signals",
        "📝 Decision Rationale", "🤖 ML Intelligence",
    ])

    with tab1:
        a,b = st.columns(2)
        with a:
            st.markdown("**Company Info**")
            st.write(f"**Name:** {fin.get('company_name', cname)}")
            st.write(f"**CIN:** {fin.get('cin','N/A')}")
            dirs = fin.get("directors",[]) or []
            dirs_str = ", ".join([d.get("name",str(d)) if isinstance(d,dict) else str(d) for d in dirs]) or "N/A"
            st.write(f"**Directors:** {dirs_str}")
        with b:
            st.markdown("**Key Financials**")
            st.write(f"**Revenue:** {fmt_cr(fin.get('revenue_crores'))}")
            st.write(f"**PAT:** {fmt_cr(fin.get('profit_after_tax_crores'))}")
            st.write(f"**EBITDA:** {fmt_cr(fin.get('ebitda_crores'))}")
            st.write(f"**D/E Ratio:** {fmt_val(fin.get('debt_equity_ratio'), 'x')}")
            st.write(f"**Net Worth:** {fmt_cr(fin.get('net_worth_crores'))}")
            st.write(f"**Current Ratio:** {fmt_val(fin.get('current_ratio'), 'x')}")

    with tab2:
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

    with tab3:
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

    with tab4:
        risks = research.get("overall_sentiment",{}).get("top_risks",[])
        for r in risks: st.warning(f"⚠ {r}")
        rf = fin.get("red_flags",{})
        for k,v in (rf or {}).items():
            if v: st.error(f"🚨 {k.replace('_',' ').title()}")
        penalty = risk_score.get("penalty_applied",0)
        if penalty: st.warning(f"Score penalty: -{penalty} points")
        if not risks and not any((rf or {}).values()):
            st.success("No major risk signals detected.")

    with tab5:
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

    with tab6:
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

    # ── Re-score ─────────────────────────────────────────────────────────── #
    st.markdown("---")
    st.markdown('<div class="section-header">⚡ REAL-TIME SCORE ADJUSTMENT</div>', unsafe_allow_html=True)
    st.caption("Add new field observations to instantly re-score without re-running full analysis")
    new_notes = st.text_area("Updated field observations", value=mnotes, height=80, key="new_notes_input")
    if st.button("🔄 Re-Score with New Notes", key="rescore_btn"):
        sa_ref = st.session_state.get("scoring_agent_ref")
        if sa_ref:
            with st.spinner("Re-scoring..."):
                upd = sa_ref.adjust_for_manual_notes(new_notes)
                st.session_state["scoring_results"] = upd
            ur  = upd.get("recommendation",{})
            st.success(f"✅ Re-scored: {ur.get('final_score',0)}/100 | {ur.get('rating','N/A')} | {ur.get('decision','N/A')}")
            st.rerun()
        else:
            st.error("No scoring agent in session. Please re-run analysis.")

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
                use_container_width=True,
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