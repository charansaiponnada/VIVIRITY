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
    .main-header {
        background: linear-gradient(135deg, #1F3864 0%, #00528C 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
    }
    .metric-card {
        background: #f8f9fa;
        border-left: 4px solid #1F3864;
        padding: 1rem;
        border-radius: 5px;
        margin: 0.5rem 0;
    }
    .approve-badge {
        background: #00B050;
        color: white;
        padding: 0.5rem 1.5rem;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .reject-badge {
        background: #FF0000;
        color: white;
        padding: 0.5rem 1.5rem;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .caution-badge {
        background: #FF8C00;
        color: white;
        padding: 0.5rem 1.5rem;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .agent-status {
        padding: 0.3rem 0.8rem;
        border-radius: 15px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .status-running { background: #FFF3CD; color: #856404; }
    .status-done    { background: #D1E7DD; color: #0A3622; }
    .status-pending { background: #E2E3E5; color: #41464B; }
    .five-c-box {
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .red-flag {
        background: #FFC7CE;
        border-left: 4px solid #FF0000;
        padding: 0.5rem 1rem;
        margin: 0.3rem 0;
        border-radius: 3px;
    }
    .stButton > button {
        background: linear-gradient(135deg, #1F3864, #00528C);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        font-weight: bold;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)


# ── Session State Init ────────────────────────────────────────
def init_session():
    defaults = {
        "parsed_data": None,
        "financials": None,
        "research": None,
        "five_cs": None,
        "recommendation": None,
        "cam_path": None,
        "company_name": "",
        "analysis_done": False,
        "agent_statuses": {
            "ingestor": "pending",
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
    st.image("https://via.placeholder.com/200x60/1F3864/FFFFFF?text=INTELLI-CREDIT",
             use_container_width=True)
    st.markdown("### 🏦 Intelli-Credit Engine")
    st.markdown("*AI-Powered Credit Appraisal*")
    st.markdown("---")

    st.markdown("### 🤖 Agent Status")

    status_icons = {
        "pending": "⬜",
        "running": "🔄",
        "done": "✅",
        "error": "❌"
    }
    agent_labels = {
        "ingestor": "📄 Data Ingestor",
        "research": "🔍 Research Agent",
        "scoring": "📊 Scoring Agent",
        "cam": "📝 CAM Generator",
    }
    for agent, label in agent_labels.items():
        status = st.session_state.agent_statuses[agent]
        st.markdown(
            f"{status_icons[status]} {label} — `{status.upper()}`"
        )

    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    show_raw = st.checkbox("Show Raw Agent Output", value=False)
    st.markdown("---")
    st.markdown("**Built by DOMINIX**")
    st.markdown("*Vivriti Capital Hackathon 2026*")
    st.markdown("*IIT Hyderabad · YUVAAN 2026*")


# ── Main Header ───────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🏦 Intelli-Credit</h1>
    <p style="font-size:1.1rem; opacity:0.9;">
        Next-Gen Corporate Credit Appraisal · Powered by Google ADK + Gemini
    </p>
    <p style="font-size:0.85rem; opacity:0.7;">
        VectorLess RAG · Multi-Agent Architecture · Indian Context Intelligence
    </p>
</div>
""", unsafe_allow_html=True)


# ── STEP 1: Document Upload ───────────────────────────────────
st.markdown("## 📁 Step 1: Upload Company Documents")

col1, col2 = st.columns([2, 1])

with col1:
    uploaded_files = st.file_uploader(
        "Upload Annual Reports, Financial Statements, GST Docs, Sanction Letters",
        type=["pdf"],
        accept_multiple_files=True,
        help="Supports scanned PDFs, annual reports, bank statements"
    )

with col2:
    st.markdown("**Supported Documents:**")
    st.markdown("- 📊 Annual Reports")
    st.markdown("- 🧾 GST Returns / ITR")
    st.markdown("- 🏦 Bank Statements")
    st.markdown("- ⚖️ Legal Notices")
    st.markdown("- 📋 Sanction Letters")

# ── STEP 2: Company Details ───────────────────────────────────
st.markdown("## 🏢 Step 2: Company Details")

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
        placeholder="e.g. Ratan Tata, N. Chandrasekaran",
    )

with col3:
    sector = st.selectbox(
        "Industry Sector",
        [
            "Manufacturing", "NBFC/Financial Services",
            "Real Estate", "Infrastructure", "IT/Technology",
            "Retail/FMCG", "Healthcare/Pharma",
            "Renewable Energy", "Logistics", "Other"
        ]
    )

col1, col2 = st.columns(2)
with col1:
    loan_amount = st.text_input(
        "Requested Loan Amount",
        placeholder="e.g. ₹ 50 Crores"
    )
with col2:
    loan_purpose = st.text_input(
        "Loan Purpose",
        placeholder="e.g. Working Capital Expansion"
    )

# ── STEP 3: Credit Officer Notes ─────────────────────────────
st.markdown("## 📝 Step 3: Credit Officer Field Notes")
st.markdown(
    "*Add qualitative observations from site visits, management interviews etc.*"
)

manual_notes = st.text_area(
    "Field Observations",
    placeholder=(
        "e.g. Factory found operating at 40% capacity. "
        "Management was evasive about pending litigation. "
        "Inventory levels appeared inflated compared to GST filings..."
    ),
    height=120,
)

# ── STEP 4: Run Analysis ──────────────────────────────────────
st.markdown("## 🚀 Step 4: Run AI Credit Analysis")

run_button = st.button(
    "🔍 Run Full Credit Analysis",
    disabled=not (uploaded_files and company_name),
)

if not uploaded_files:
    st.info("👆 Please upload at least one document to proceed.")
if uploaded_files and not company_name:
    st.warning("⚠️ Please enter the company name.")


# ── ANALYSIS ENGINE ───────────────────────────────────────────
if run_button and uploaded_files and company_name:
    st.session_state.company_name = company_name
    promoter_list = [p.strip() for p in promoters_input.split(",") if p.strip()]

    # save uploaded files to temp
    temp_paths = []
    for uploaded_file in uploaded_files:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf"
        ) as tmp:
            tmp.write(uploaded_file.read())
            temp_paths.append(tmp.name)

    progress = st.progress(0)
    status_text = st.empty()

    try:
        # ── Agent 1: Data Ingestor ────────────────────────────
        status_text.markdown("🔄 **Agent 1/4: Data Ingestor** — Parsing documents...")
        st.session_state.agent_statuses["ingestor"] = "running"
        progress.progress(10)

        from core.pdf_parser import PageIndexParser
        from core.financial_extractor import FinancialExtractor

        all_financials = {
            "basic_info": {},
            "financials": {},
            "debt_profile": {},
            "gst_analysis": {},
            "red_flags": {},
        }

        for path in temp_paths:
            parser = PageIndexParser(path)
            parsed = parser.parse()
            extractor = FinancialExtractor(parser)
            extracted = extractor.extract_all()

            # merge results
            for key in all_financials:
                if extracted.get(key) and not extracted[key].get("parse_error"):
                    all_financials[key].update(extracted[key])

        st.session_state.financials = all_financials
        st.session_state.parsed_data = parsed
        st.session_state.agent_statuses["ingestor"] = "done"
        progress.progress(30)

        # ── Agent 2: Research Agent ───────────────────────────
        status_text.markdown(
            "🔄 **Agent 2/4: Research Agent** — "
            "Searching web for company intelligence..."
        )
        st.session_state.agent_statuses["research"] = "running"

        from agents.research_agent import ResearchAgent
        research_agent = ResearchAgent(
            company_name=company_name,
            promoter_names=promoter_list,
            sector=sector,
        )
        research_results = research_agent.run_full_research()
        st.session_state.research = research_results
        st.session_state.agent_statuses["research"] = "done"
        progress.progress(55)

        # ── Agent 3: Scoring Agent ────────────────────────────
        status_text.markdown(
            "🔄 **Agent 3/4: Scoring Agent** — "
            "Computing Five Cs credit score..."
        )
        st.session_state.agent_statuses["scoring"] = "running"

        from agents.scoring_agent import ScoringAgent
        scoring_agent = ScoringAgent(
            company_name=company_name,
            financials=all_financials,
            research=research_results,
            manual_notes=manual_notes,
        )
        scoring_results = scoring_agent.run()
        st.session_state.five_cs = scoring_results["five_cs"]
        st.session_state.recommendation = scoring_results["recommendation"]
        st.session_state.agent_statuses["scoring"] = "done"
        progress.progress(75)

        # ── Agent 4: CAM Generator ────────────────────────────
        status_text.markdown(
            "🔄 **Agent 4/4: CAM Generator** — "
            "Generating Credit Appraisal Memo..."
        )
        st.session_state.agent_statuses["cam"] = "running"

        from core.cam_generator import CAMGenerator
        cam_gen = CAMGenerator(
            company_name=company_name,
            financials=all_financials,
            research=research_results,
            five_cs=st.session_state.five_cs,
            recommendation=st.session_state.recommendation,
            manual_notes=manual_notes,
            loan_amount=loan_amount or "Not specified",
            loan_purpose=loan_purpose or "General Corporate Purpose",
        )
        cam_path = cam_gen.generate()
        st.session_state.cam_path = cam_path
        st.session_state.agent_statuses["cam"] = "done"
        st.session_state.analysis_done = True
        progress.progress(100)

        status_text.markdown("✅ **Analysis Complete!**")

        # cleanup temp files
        for path in temp_paths:
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


# ── RESULTS DASHBOARD ─────────────────────────────────────────
if st.session_state.analysis_done:
    st.markdown("---")
    st.markdown("## 📊 Credit Analysis Results")

    rec = st.session_state.recommendation or {}
    five_cs = st.session_state.five_cs or {}
    research = st.session_state.research or {}

    # ── Decision Banner ───────────────────────────────────────
    decision = rec.get("decision", "PENDING")
    badge_class = {
        "APPROVE": "approve-badge",
        "CONDITIONAL_APPROVE": "caution-badge",
        "REJECT": "reject-badge",
    }.get(decision, "caution-badge")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"<div style='text-align:center; padding:1rem;'>"
            f"<span class='{badge_class}'>"
            f"DECISION: {decision}"
            f"</span></div>",
            unsafe_allow_html=True
        )

    # ── Key Metrics Row ───────────────────────────────────────
    st.markdown("### 📈 Key Credit Metrics")
    m1, m2, m3, m4, m5 = st.columns(5)

    with m1:
        st.metric(
            "Credit Score",
            f"{rec.get('final_score', 'N/A')}/100"
        )
    with m2:
        st.metric("Rating", rec.get("rating", "N/A"))
    with m3:
        amount = rec.get("recommended_amount_crores")
        st.metric(
            "Recommended Amount",
            f"₹{amount}Cr" if amount else "N/A"
        )
    with m4:
        rate = rec.get("interest_rate_percent")
        st.metric(
            "Interest Rate",
            f"{rate}% p.a." if rate else "N/A"
        )
    with m5:
        tenure = rec.get("tenure_months")
        st.metric(
            "Tenure",
            f"{tenure} months" if tenure else "N/A"
        )

    # ── Five Cs Visual ────────────────────────────────────────
    st.markdown("### 🎯 Five Cs Assessment")

    c1, c2, c3, c4, c5 = st.columns(5)
    five_c_cols = [c1, c2, c3, c4, c5]
    five_c_data = [
        ("CHARACTER", "character_score", "👤", "25%"),
        ("CAPACITY", "capacity_score", "💰", "30%"),
        ("CAPITAL", "capital_score", "🏛️", "20%"),
        ("COLLATERAL", "collateral_score", "🔒", "15%"),
        ("CONDITIONS", "conditions_score", "🌍", "10%"),
    ]

    for col, (label, key, icon, weight) in zip(five_c_cols, five_c_data):
        score = five_cs.get(key, 0)
        try:
            score_num = float(score)
        except Exception:
            score_num = 0

        color = (
            "#00B050" if score_num >= 70 else
            "#FF8C00" if score_num >= 50 else
            "#FF0000"
        )

        with col:
            st.markdown(
                f"<div class='five-c-box'>"
                f"<div style='font-size:2rem'>{icon}</div>"
                f"<div style='font-weight:bold; font-size:0.8rem'>{label}</div>"
                f"<div style='font-size:1.8rem; font-weight:bold; color:{color}'>"
                f"{score}</div>"
                f"<div style='font-size:0.75rem; color:#666'>Weight: {weight}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    # ── Tabs for detailed results ─────────────────────────────
    st.markdown("### 📋 Detailed Analysis")
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏢 Company & Financials",
        "🔍 Research Intelligence",
        "⚠️ Risk Signals",
        "📝 Decision Rationale",
    ])

    with tab1:
        fin = st.session_state.financials or {}
        basic = fin.get("basic_info", {})
        financials = fin.get("financials", {})

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Company Information**")
            if basic and not basic.get("parse_error"):
                st.write(f"**Name:** {basic.get('company_name', 'N/A')}")
                st.write(f"**CIN:** {basic.get('cin', 'N/A')}")
                st.write(f"**Business:** {basic.get('business_nature', 'N/A')}")
                directors = basic.get("directors", [])
                if directors:
                    st.write(f"**Directors:** {', '.join(directors)}")
            else:
                st.info("Company info extracted from documents.")

        with col2:
            st.markdown("**Key Financial Metrics**")
            if financials and not financials.get("parse_error"):
                metrics = {
                    "Revenue (Current)": f"₹{financials.get('revenue_current', 'N/A')} Cr",
                    "EBITDA": f"₹{financials.get('ebitda', 'N/A')} Cr",
                    "PAT": f"₹{financials.get('pat', 'N/A')} Cr",
                    "Net Worth": f"₹{financials.get('net_worth', 'N/A')} Cr",
                    "Total Debt": f"₹{financials.get('total_debt', 'N/A')} Cr",
                    "Debt/Equity": str(financials.get("debt_to_equity", "N/A")),
                    "Current Ratio": str(financials.get("current_ratio", "N/A")),
                }
                for k, v in metrics.items():
                    st.write(f"**{k}:** {v}")
            else:
                st.info("Financial data extracted from uploaded documents.")

    with tab2:
        if research:
            col1, col2 = st.columns(2)
            with col1:
                news = research.get("company_news", {})
                st.markdown("**📰 Company News Sentiment**")
                sentiment = news.get("sentiment", "N/A")
                color = (
                    "green" if sentiment == "Positive" else
                    "red" if sentiment == "Negative" else "orange"
                )
                st.markdown(
                    f"<span style='color:{color}; font-weight:bold'>"
                    f"{sentiment}</span>",
                    unsafe_allow_html=True
                )
                st.write(news.get("summary", "No news summary available."))

                st.markdown("**🔍 Sector Analysis**")
                sector_data = research.get("sector_headwinds", {})
                st.write(
                    f"**Sector Health:** "
                    f"{sector_data.get('sector_health', 'N/A')}"
                )
                st.write(sector_data.get("summary", ""))

            with col2:
                st.markdown("**⚖️ Litigation Status**")
                litigation = research.get("litigation", {})
                risk = litigation.get("litigation_risk", "N/A")
                color = (
                    "red" if risk == "High" else
                    "orange" if risk == "Medium" else "green"
                )
                st.markdown(
                    f"<span style='color:{color}; font-weight:bold'>"
                    f"Risk: {risk}</span>",
                    unsafe_allow_html=True
                )
                st.write(litigation.get("summary", "No litigation data."))

                st.markdown("**🏛️ Regulatory Status**")
                regulatory = research.get("regulatory", {})
                reg_risk = regulatory.get("regulatory_risk", "N/A")
                st.write(f"**Risk Level:** {reg_risk}")
                st.write(regulatory.get("summary", ""))

            # Overall sentiment
            overall = research.get("overall_sentiment", {})
            if overall:
                st.markdown("**🎯 Research Summary**")
                prelim = overall.get("preliminary_recommendation", "N/A")
                color = (
                    "green" if prelim == "Proceed" else
                    "red" if prelim == "Reject" else "orange"
                )
                st.markdown(
                    f"Preliminary: <span style='color:{color}; "
                    f"font-weight:bold'>{prelim}</span>",
                    unsafe_allow_html=True
                )
                top_risks = overall.get("top_risks", [])
                if top_risks:
                    st.markdown("**Top Risks:**")
                    for risk in top_risks:
                        st.markdown(f"- 🔴 {risk}")
                pos_factors = overall.get("positive_factors", [])
                if pos_factors:
                    st.markdown("**Positive Factors:**")
                    for factor in pos_factors:
                        st.markdown(f"- 🟢 {factor}")

    with tab3:
        fin = st.session_state.financials or {}
        red_flags = fin.get("red_flags", {})
        flags = red_flags.get("red_flags", [])
        gst = fin.get("gst_analysis", {})

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🚨 Document Red Flags**")
            if flags:
                for flag in flags:
                    st.markdown(
                        f"<div class='red-flag'>🔴 {flag}</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.success("✅ No significant red flags in documents")

            st.markdown("**🔄 GST Analysis**")
            if gst and not gst.get("parse_error"):
                mismatch = gst.get("gstr_mismatch_detected", False)
                circular = gst.get("circular_trading_risk", False)
                if mismatch:
                    st.error("⚠️ GSTR Mismatch Detected!")
                    st.write(gst.get("mismatch_details", ""))
                else:
                    st.success("✅ No GSTR mismatch detected")
                if circular:
                    st.error("⚠️ Circular Trading Risk Identified!")
                else:
                    st.success("✅ No circular trading patterns")
            else:
                st.info("GST data not found in uploaded documents.")

        with col2:
            st.markdown("**📊 Penalty Analysis**")
            score_data = rec or {}
            final_score = score_data.get("final_score", 0)
            try:
                fs = float(final_score)
            except Exception:
                fs = 0
            if fs < 60:
                st.error(f"⚠️ Score penalties applied. Final: {fs}/100")
            else:
                st.success(f"✅ Score: {fs}/100 — No major penalties")

            if manual_notes or st.session_state.get("manual_notes"):
                st.markdown("**📝 Credit Officer Notes Impact**")
                st.info(
                    "Manual notes were factored into the scoring. "
                    "Field observations adjusted the final risk score."
                )

    with tab4:
        rationale = rec.get("decision_rationale", "No rationale available.")
        rejection = rec.get("rejection_reason")
        conditions = rec.get("key_conditions", [])

        st.markdown(f"**Decision: `{decision}`**")
        st.write(rationale)

        if rejection:
            st.error(f"**Rejection Reason:** {rejection}")

        if conditions:
            st.markdown("**Conditions Precedent:**")
            for i, cond in enumerate(conditions, 1):
                st.markdown(f"{i}. {cond}")

        # Five Cs rationale breakdown
        st.markdown("**Five Cs Rationale:**")
        for label, rationale_key in [
            ("Character", "character_rationale"),
            ("Capacity", "capacity_rationale"),
            ("Capital", "capital_rationale"),
            ("Collateral", "collateral_rationale"),
            ("Conditions", "conditions_rationale"),
        ]:
            with st.expander(f"{label}"):
                st.write(five_cs.get(rationale_key, "N/A"))

    # ── Real-time Score Adjustment ────────────────────────────
    st.markdown("---")
    st.markdown("### 🔄 Real-Time Score Adjustment")
    st.markdown(
        "*Add new observations to instantly re-score without re-running full analysis*"
    )

    new_notes = st.text_area(
        "Additional Field Notes",
        placeholder=(
            "e.g. Follow-up visit: Plant now operating at 20% capacity. "
            "MD confirmed order book decline of 40%..."
        ),
        height=80,
    )

    if st.button("⚡ Re-Score with New Notes"):
        if new_notes and st.session_state.financials:
            with st.spinner("Re-scoring..."):
                from agents.scoring_agent import ScoringAgent
                scoring_agent = ScoringAgent(
                    company_name=st.session_state.company_name,
                    financials=st.session_state.financials,
                    research=st.session_state.research,
                    manual_notes=new_notes,
                )
                new_results = scoring_agent.run()
                st.session_state.five_cs = new_results["five_cs"]
                st.session_state.recommendation = new_results["recommendation"]
                st.success(
                    f"✅ Score updated: "
                    f"{new_results['recommendation'].get('final_score')}/100 "
                    f"| Rating: {new_results['recommendation'].get('rating')}"
                )
                st.rerun()

    # ── Download CAM ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📥 Download Credit Appraisal Memo")

    if st.session_state.cam_path and os.path.exists(st.session_state.cam_path):
        with open(st.session_state.cam_path, "rb") as f:
            cam_bytes = f.read()

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.download_button(
                label="📄 Download CAM (Word Document)",
                data=cam_bytes,
                file_name=f"CAM_{st.session_state.company_name.replace(' ', '_')}.docx",
                mime=(
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                ),
                use_container_width=True,
            )
            st.caption(
                "Professional Credit Appraisal Memo — "
                "Ready for bank submission"
            )

    # ── Raw Output ────────────────────────────────────────────
    if show_raw:
        st.markdown("---")
        st.markdown("### 🔧 Raw Agent Output")
        with st.expander("Financial Extraction"):
            st.json(st.session_state.financials or {})
        with st.expander("Research Intelligence"):
            st.json(st.session_state.research or {})
        with st.expander("Scoring Results"):
            st.json({
                "five_cs": st.session_state.five_cs,
                "recommendation": st.session_state.recommendation,
            })