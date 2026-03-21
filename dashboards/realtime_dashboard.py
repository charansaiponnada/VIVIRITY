"""
dashboards/realtime_dashboard.py
Real-Time Data Dashboard for Intelli-Credit.

Displays live data from:
- MCA Company Registry
- GST Portal Filing Status
- CIBIL Credit Bureau
- RBI Rates
- NCLT Case Tracker
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

VIVRITI_BLUE = "#1B3A6B"
VIVRITI_GOLD = "#C9A84C"
GREEN = "#1E8449"
ORANGE = "#D68910"
RED = "#C0392B"
LIGHT_BLUE = "#2471A3"


def render_live_data_panel(live_profile: dict, enrichment_report: dict = None):
    """
    Render the live data verification panel.
    Shows real-time data sources and their verification status.
    """
    st.markdown("### 📡 Live Data Verification Panel")
    st.caption("Real-time data fetched from government APIs")

    if not live_profile:
        st.info("Live data not available. Running in offline mode.")
        return

    data_sources = live_profile.get("data_sources", [])
    verification_timestamp = live_profile.get("verification_timestamp", "N/A")

    cols = st.columns(len(data_sources) + 1)
    with cols[0]:
        st.metric("Data Sources", len(data_sources))
    for i, source in enumerate(data_sources):
        with cols[i + 1]:
            st.metric(f"{source}", "✓ Active")

    st.caption(f"Last verified: {verification_timestamp}")
    st.markdown("---")

    tabs = st.tabs(
        ["MCA Registry", "GST Portal", "CIBIL Bureau", "RBI Rates", "NCLT Cases"]
    )

    with tabs[0]:
        _render_mca_tab(live_profile.get("mca_data"))

    with tabs[1]:
        _render_gst_tab(live_profile.get("gst_data"))

    with tabs[2]:
        _render_cibil_tab(live_profile.get("cibil_data"))

    with tabs[3]:
        _render_rbi_tab(live_profile.get("rbi_rates"))

    with tabs[4]:
        _render_nclt_tab(live_profile.get("nclt_cases"))

    if enrichment_report:
        st.markdown("---")
        _render_enrichment_report(enrichment_report)


def _render_mca_tab(mca_data: dict):
    """Render MCA company registry data."""
    if not mca_data:
        st.info("MCA data not available")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Company Details")
        st.write(f"**CIN:** {mca_data.get('cin', 'N/A')}")
        st.write(f"**Company Name:** {mca_data.get('company_name', 'N/A')}")
        st.write(f"**Status:** {mca_data.get('status', 'N/A')}")
        st.write(f"**Incorporation:** {mca_data.get('incorporation_date', 'N/A')}")
        st.write(f"**Class:** {mca_data.get('class_description', 'N/A')}")
        st.write(f"**Nature of Business:** {mca_data.get('nature_of_business', 'N/A')}")

    with col2:
        st.markdown("#### Capital & Compliance")
        authorised = mca_data.get("authorised_capital", 0) or 0
        paid_up = mca_data.get("paid_up_capital", 0) or 0

        st.write(f"**Authorised Capital:** ₹{authorised:,.0f}")
        st.write(f"**Paid-up Capital:** ₹{paid_up:,.0f}")
        st.write(f"**Members:** {mca_data.get('number_of_members', 0)}")
        st.write(f"**Directors:** {mca_data.get('directors_count', 0)}")
        st.write(f"**Charges:** {mca_data.get('charges_count', 0)}")

        filing = mca_data.get("latest_filing_status", {})
        if filing:
            st.markdown("**Filing Status:**")
            for k, v in filing.items():
                st.write(f"  - {k.upper()}: {v}")

    status_color = GREEN if mca_data.get("status", "").upper() == "ACTIVE" else RED
    st.markdown(
        f"""
    <div style="padding: 10px; border-radius: 8px; background: {status_color}20; border-left: 4px solid {status_color};">
        <strong>Company Status:</strong> {mca_data.get("status", "UNKNOWN")}
    </div>
    """,
        unsafe_allow_html=True,
    )


def _render_gst_tab(gst_data: dict):
    """Render GST portal filing status."""
    if not gst_data:
        st.info("GST data not available")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Registration")
        st.write(f"**GSTIN:** {gst_data.get('gstin', 'N/A')}")
        st.write(f"**Legal Name:** {gst_data.get('legal_name', 'N/A')}")
        st.write(f"**Status:** {gst_data.get('status', 'N/A')}")
        st.write(f"**Constitution:** {gst_data.get('constitution_of_business', 'N/A')}")
        st.write(
            f"**Date of Registration:** {gst_data.get('date_of_registration', 'N/A')}"
        )

    with col2:
        st.markdown("#### Filing Compliance")
        st.write(f"**Filing Status:** {gst_data.get('filing_status', 'N/A')}")
        st.write(f"**Last Return:** {gst_data.get('last_return_filed', 'N/A')}")
        st.write(
            f"**GSTR-1 Filed:** {'✓ Yes' if gst_data.get('gstr1_filed') else '✗ No'}"
        )
        st.write(
            f"**GSTR-3B Filed:** {'✓ Yes' if gst_data.get('gstr3b_filed') else '✗ No'}"
        )
        st.write(
            f"**Annual Return:** {'✓ Yes' if gst_data.get('annual_return_filed') else '✗ No'}"
        )

    compliance = gst_data.get("compliance_score", 0) or 0
    risk_level = gst_data.get("risk_level", "MEDIUM")

    risk_color = (
        GREEN if risk_level == "LOW" else ORANGE if risk_level == "MEDIUM" else RED
    )

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=compliance,
            title={"text": "Compliance Score"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": VIVRITI_BLUE},
                "steps": [
                    {"range": [0, 50], "color": "#fadbd8"},
                    {"range": [50, 70], "color": "#fdebd0"},
                    {"range": [70, 100], "color": "#d5f5e3"},
                ],
            },
            number={"suffix": "%", "font": {"size": 24}},
        )
    )
    fig.update_layout(height=200, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        f"""
    <div style="padding: 10px; border-radius: 8px; background: {risk_color}20; border-left: 4px solid {risk_color};">
        <strong>GST Risk Level:</strong> {risk_level}
    </div>
    """,
        unsafe_allow_html=True,
    )


def _render_cibil_tab(cibil_data: dict):
    """Render CIBIL credit bureau data."""
    if not cibil_data:
        st.info("CIBIL data not available")
        return

    score = cibil_data.get("bureau_score", 0) or 0

    score_color = GREEN if score >= 700 else ORANGE if score >= 600 else RED

    fig = go.Figure(
        go.Indicator(
            mode="number",
            value=score,
            title={"text": "CIBIL Commercial Score"},
            number={"font": {"size": 48, "color": score_color}},
        )
    )
    fig.update_layout(height=150, margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.write(f"**Score Range:** {cibil_data.get('score_range', 'N/A')}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### Outstanding")
        st.write(f"**Total:** ₹{cibil_data.get('total_outstanding', 0):,.0f}")
        st.write(f"**Secured:** ₹{cibil_data.get('secured_outstanding', 0):,.0f}")
        st.write(f"**Unsecured:** ₹{cibil_data.get('unsecured_outstanding', 0):,.0f}")

    with col2:
        st.markdown("#### Account Status")
        st.write(f"**Total Accounts:** {cibil_data.get('total_accounts', 0)}")
        st.write(f"**Active:** {cibil_data.get('active_accounts', 0)}")
        st.write(f"**Delinquent:** {cibil_data.get('delinquent_accounts', 0)}")

    with col3:
        st.markdown("#### Risk Flags")
        wilful = cibil_data.get("wilful_defaulter_flag", False)
        suit = cibil_data.get("suit_filed_accounts", 0)
        dpd90 = cibil_data.get("dpd_90_plus_count", 0)

        flag_color = RED if wilful else GREEN
        st.write(f"**Wilful Defaulter:** {'⚠️ YES' if wilful else '✓ No'}")
        st.write(f"**Suit Filed:** {suit}")
        st.write(f"**DPD 90+:** {dpd90}")

    if wilful or suit > 0:
        st.error("🚨 Critical: Wilful Defaulter or Suit Filed status detected!")

    st.caption(f"Last updated: {cibil_data.get('last_updated', 'N/A')}")


def _render_rbi_tab(rbi_data: dict):
    """Render current RBI rates and indices."""
    if not rbi_data:
        st.info("RBI rates not available")
        return

    st.markdown(f"**Reference Date:** {rbi_data.get('reference_date', 'N/A')}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### Policy Rates")
        st.write(f"**Repo Rate:** {rbi_data.get('repo_rate', 0):.2f}%")
        st.write(f"**Reverse Repo:** {rbi_data.get('reverse_repo_rate', 0):.2f}%")
        st.write(f"**MSF Rate:** {rbi_data.get('msf_rate', 0):.2f}%")
        st.write(f"**Bank Rate:** {rbi_data.get('bank_rate', 0):.2f}%")

    with col2:
        st.markdown("#### Reserve Ratios")
        st.write(f"**CRR:** {rbi_data.get('crr', 0):.2f}%")
        st.write(f"**SLR:** {rbi_data.get('slr', 0):.2f}%")

    with col3:
        st.markdown("#### Economic Indicators")
        st.write(f"**Inflation:** {rbi_data.get('inflation_rate', 0):.2f}%")
        st.write(f"**GDP Growth:** {rbi_data.get('gdp_growth', 0):.2f}%")
        st.write(f"**PMI Mfg:** {rbi_data.get('pmi_manufacturing', 0):.1f}")
        st.write(f"**PMI Services:** {rbi_data.get('pmi_services', 0):.1f}")

    base_rate = rbi_data.get("repo_rate", 6.5) + 3.0
    st.info(f"💡 **Implied Base Rate Indicator:** {base_rate:.2f}% (Repo + 3%)")


def _render_nclt_tab(nclt_data: dict):
    """Render NCLT case tracker data."""
    if not nclt_data:
        st.info("NCLT data not available")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Case Summary")
        st.write(f"**Total Cases:** {nclt_data.get('total_cases', 0)}")
        st.write(f"**Insolvency Cases:** {nclt_data.get('insolvency_cases', 0)}")
        st.write(f"**Liquidation Cases:** {nclt_data.get('liquidation_cases', 0)}")
        st.write(f"**Pending Cases:** {nclt_data.get('pending_cases', 0)}")
        st.write(f"**Resolved Cases:** {nclt_data.get('resolved_cases', 0)}")

    with col2:
        st.markdown("#### Latest Case Status")
        st.write(f"**Latest Case Date:** {nclt_data.get('latest_case_date', 'N/A')}")
        st.write(f"**Case Type:** {nclt_data.get('latest_case_type', 'N/A')}")
        st.write(f"**Case Status:** {nclt_data.get('latest_case_status', 'N/A')}")
        st.write(f"**IIRC Number:** {nclt_data.get('iirc_case_number', 'N/A')}")

    moratorium = nclt_data.get("moratorium_status", False)
    resolution = nclt_data.get("resolution_plan_approved", False)

    if nclt_data.get("insolvency_cases", 0) > 0:
        st.error("🚨 Active NCLT proceedings detected!")
    elif moratorium:
        st.warning("⚠️ Moratorium period active")
    elif resolution:
        st.success("✓ Resolution plan approved")
    else:
        st.success("✓ No active NCLT proceedings")


def _render_enrichment_report(report: dict):
    """Render data enrichment verification report."""
    st.markdown("#### 🔍 Data Enrichment Report")

    verified = report.get("verified_fields", [])
    mismatched = report.get("mismatched_fields", [])
    overrides = report.get("live_overrides", {})
    warnings = report.get("warnings", [])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Verified Fields", len(verified))
    with col2:
        st.metric("Mismatched Fields", len(mismatched))
    with col3:
        st.metric("Live Overrides", len(overrides))

    if verified:
        with st.expander("✅ Verified Fields"):
            for field in verified:
                st.write(f"- {field}")

    if mismatched:
        with st.expander("⚠️ Mismatched Fields"):
            for mismatch in mismatched:
                st.write(f"**{mismatch['field']}**:")
                st.write(f"  - MCA Value: ₹{mismatch['mca_value']:,.0f}")
                st.write(f"  - Extracted: ₹{mismatch['extracted_value']:,.0f}")
                st.write(f"  - Variance: {mismatch['variance_pct']}%")

    if overrides:
        with st.expander("🔄 Live Overrides Applied"):
            for field, value in overrides.items():
                st.write(f"- **{field}**: {value}")

    if warnings:
        with st.expander("⚠️ Warnings"):
            for warning in warnings:
                st.warning(warning)


def render_live_data_summary(live_profile: dict) -> dict:
    """Render a compact summary of live data for the main dashboard."""
    if not live_profile:
        return {"status": "unavailable", "risk_level": "unknown"}

    risk_data = live_profile.get("combined_risk_score", {})
    cibil = live_profile.get("cibil_data", {})
    nclt = live_profile.get("nclt_cases", {})

    risk_level = risk_data.get("risk_level", "UNKNOWN")
    risk_color = (
        GREEN if risk_level == "LOW" else ORANGE if risk_level == "MEDIUM" else RED
    )

    return {
        "status": "live",
        "risk_level": risk_level,
        "risk_score": risk_data.get("composite_score", 0),
        "cibil_score": cibil.get("bureau_score", 0),
        "has_insolvency": nclt.get("insolvency_cases", 0) > 0 if nclt else False,
        "wilful_defaulter": cibil.get("wilful_defaulter_flag", False)
        if cibil
        else False,
        "requires_manual_review": risk_data.get("requires_manual_review", False),
    }
