"""
dashboards.py
-------------
High-Impact Credit Risk Dashboards for Intelli-Credit.

Four professional dashboards:
  1. Credit Risk Command Center — overall credit profile overview
  2. Risk Intelligence Monitor — risk signals, litigation, fraud, early warnings
  3. Financial Health Analyzer — financial trends, ratios, health score
  4. Specialized Monitor — ALM, Shareholding, Borrowing, Portfolio data
"""

import math
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from utils.indian_context import get_ratio_gauges, get_health_score_config, get_top_metrics


# ═══════════════════════════════════════════════════════════════════════════ #
# Colour Constants
# ═══════════════════════════════════════════════════════════════════════════ #
VIVRITI_BLUE = "#1B3A6B"
VIVRITI_GOLD = "#C9A84C"
GREEN = "#1E8449"
ORANGE = "#D68910"
RED = "#C0392B"
LIGHT_BLUE = "#2471A3"
PURPLE = "#884EA0"
GREY = "#7f8c8d"
BG_DARK = "#0d2444"


def _safe_float(val) -> float:
    if val is None:
        return 0.0
    try:
        # Handle cases where value might be a list or dict accidentally
        if isinstance(val, (list, dict)): return 0.0
        return float(str(val).replace(",", "").replace("₹", "").strip())
    except (ValueError, TypeError):
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════ #
# DASHBOARD 1 — Credit Risk Command Center
# ═══════════════════════════════════════════════════════════════════════════ #

def render_credit_command_center(scoring: dict, ml_results: dict,
                                  financials: dict, company_name: str):
    """Dashboard 1: Instant overview of the company's credit profile."""
    st.markdown("### 🏦 Credit Risk Command Center")
    st.caption(f"Real-time credit profile for **{company_name}**")

    rec = scoring.get("recommendation", {})
    risk_score = scoring.get("risk_score", {})
    five_cs = scoring.get("five_cs", {})

    score = rec.get("final_score", risk_score.get("final_score", 0))
    rating = rec.get("rating", risk_score.get("rating", "N/A"))
    decision = rec.get("decision", "N/A")
    amount = rec.get("recommended_amount_crores", "N/A")
    rate = rec.get("interest_rate_percent", "N/A")
    ml_prob = ml_results.get("ml_probability_of_lending", 0) if ml_results else 0

    col1, col2, col3 = st.columns([1.3, 1, 1])

    with col1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=_safe_float(score),
            title={"text": "Credit Score", "font": {"size": 16, "color": VIVRITI_BLUE}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": VIVRITI_BLUE},
                "steps": [
                    {"range": [0, 40], "color": "#fadbd8"},
                    {"range": [40, 60], "color": "#fdebd0"},
                    {"range": [60, 75], "color": "#fef9e7"},
                    {"range": [75, 100], "color": "#d5f5e3"},
                ],
                "threshold": {"line": {"color": RED, "width": 4}, "thickness": 0.75, "value": 50},
            },
            number={"suffix": "/100", "font": {"size": 28}},
        ))
        fig.update_layout(height=250, margin=dict(t=40, b=10, l=30, r=30))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig2 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=_safe_float(ml_prob) * 100,
            title={"text": "ML Lending Probability", "font": {"size": 14, "color": VIVRITI_BLUE}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": LIGHT_BLUE},
                "steps": [
                    {"range": [0, 40], "color": "#fadbd8"},
                    {"range": [40, 72], "color": "#fdebd0"},
                    {"range": [72, 100], "color": "#d5f5e3"},
                ],
            },
            number={"suffix": "%", "font": {"size": 24}},
        ))
        fig2.update_layout(height=250, margin=dict(t=40, b=10, l=30, r=30))
        st.plotly_chart(fig2, use_container_width=True)

    with col3:
        dec_color = GREEN if decision == "APPROVE" else ORANGE if decision == "CONDITIONAL_APPROVE" else RED
        st.markdown(f"""
<div style="text-align: center; padding: 20px; border-radius: 12px; background: white; border: 2px solid {dec_color}; margin-top: 10px;">
    <div style="font-size: 0.75rem; color: {GREY}; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">Risk Rating</div>
    <div style="font-size: 3rem; font-weight: 700; color: {VIVRITI_BLUE}; margin: 5px 0;">{rating}</div>
    <div style="background: {dec_color}; color: white; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 0.85rem; display: inline-block;">{decision}</div>
    <div style="margin-top: 12px; font-size: 0.8rem; color: {GREY};">
        Limit: ₹{amount} Cr &nbsp;|&nbsp; Rate: {rate}%
    </div>
</div>
""", unsafe_allow_html=True)

    # Radar Chart & Breakdown
    col_a, col_b = st.columns([1.2, 1])
    with col_a:
        categories = ["Character", "Capacity", "Capital", "Collateral", "Conditions"]
        values = [_safe_float(five_cs.get(f"{c.lower()}_score", 0)) for c in categories]
        fig3 = go.Figure(go.Scatterpolar(
            r=values + [values[0]], theta=categories + [categories[0]], fill="toself",
            fillcolor="rgba(27, 58, 107, 0.15)", line=dict(color=VIVRITI_BLUE, width=2.5)
        ))
        fig3.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=320, showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)

    with col_b:
        st.markdown("**Score Breakdown**")
        breakdown = risk_score.get("score_breakdown", {})
        for c in ["capacity", "character", "capital", "collateral", "conditions"]:
            bd = breakdown.get(c, {})
            st.write(f"• **{c.title()}**: {bd.get('score',0)} ({bd.get('contribution',0):.1f} pts)")
        penalty = risk_score.get("penalty_applied", 0)
        if penalty > 0: st.warning(f"⚠ Penalty Applied: **-{penalty:.1f}**")


# ═══════════════════════════════════════════════════════════════════════════ #
# DASHBOARD 2 — Risk Intelligence Monitor
# ═══════════════════════════════════════════════════════════════════════════ #

def render_risk_intelligence(scoring: dict, research: dict, cross_ref: dict, company_name: str, precognitive_signals: list = None):
    """Dashboard 2: Risk signals, fraud detection, early warnings."""
    st.markdown("### 🛡️ Risk Intelligence Monitor")
    
    # 🚨 PRE-COGNITIVE SIGNALS (High-Impact Judging Criterion #3)
    if precognitive_signals:
        st.markdown("#### 🚨 Pre-Cognitive Risk Signals")
        st.caption("Forward-looking leading indicators of future credit stress.")
        
        cols = st.columns(len(precognitive_signals) if len(precognitive_signals) < 4 else 4)
        for i, sig in enumerate(precognitive_signals):
            with cols[i % 4]:
                color = RED if sig['impact'] == "CRITICAL" else ORANGE if sig['impact'] == "HIGH" else VIVRITI_GOLD
                st.markdown(f"""
                <div style="background: {color}15; border-left: 4px solid {color}; padding: 12px; border-radius: 4px; margin-bottom: 10px; height: 180px;">
                    <div style="color: {color}; font-weight: 700; font-size: 0.75rem;">{sig['type']}</div>
                    <div style="font-weight: 800; font-size: 0.95rem; margin: 4px 0;">{sig['signal']}</div>
                    <div style="font-size: 0.8rem; line-height: 1.2;">{sig['insight']}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("---")

    rec = scoring.get("recommendation", {})
    signals = rec.get("risk_signals_detail", [])
    timeline = rec.get("risk_timeline", [])

    c1, c2, c3 = st.columns(3)
    c1.metric("Risk Signals", len(signals))
    c2.metric("Fraud Risk", cross_ref.get("circular_trading_risk", "Low"))
    c3.metric("Litigation Risk", research.get("legal_disputes", {}).get("litigation_risk", "Low"))

    if signals:
        st.markdown("#### 🎯 Risk Signals")
        for s in signals:
            with st.expander(f"Signal: {s.get('signal_type', 'Unknown')}"):
                st.write(s.get("description", ""))
                st.caption(f"Source: {s.get('source', 'N/A')} | Confidence: {s.get('confidence','?')}")

    if timeline:
        st.markdown("#### 📅 Risk Timeline")
        for e in timeline:
            st.write(f"**{e.get('year')}**: {e.get('event')} ({e.get('impact')})")


# ═══════════════════════════════════════════════════════════════════════════ #
# DASHBOARD 3 — Financial Health Analyzer
# ═══════════════════════════════════════════════════════════════════════════ #

def render_financial_health(financials: dict, scoring: dict, company_name: str):
    """Dashboard 3: Financial strength assessment."""
    st.markdown("### 📊 Financial Health Analyzer")
    
    entity_type = financials.get("_entity_type", "corporate")
    
    c1, c2, c3, c4 = st.columns(4)
    rev = _safe_float(financials.get("revenue_crores"))
    pat = _safe_float(financials.get("profit_after_tax_crores"))
    ebitda = _safe_float(financials.get("ebitda_crores"))
    nw = _safe_float(financials.get("net_worth_crores"))
    
    c1.metric("Revenue", f"₹{rev:,.0f} Cr")
    c2.metric("EBITDA", f"₹{ebitda:,.0f} Cr")
    c3.metric("PAT", f"₹{pat:,.0f} Cr")
    c4.metric("Net Worth", f"₹{nw:,.0f} Cr")

    st.markdown("#### Key Ratios")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("D/E Ratio", f"{_safe_float(financials.get('debt_equity_ratio')):.2f}x")
    r2.metric("Current Ratio", f"{_safe_float(financials.get('current_ratio')):.2f}x")
    r3.metric("EBITDA Margin", f"{_safe_float(financials.get('ebitda_margin_percent')):.1f}%")
    r4.metric("ROE", f"{_safe_float(financials.get('return_on_equity_percent')):.1f}%")

    # Credit Limit
    st.markdown("---")
    limit_data = scoring.get("recommendation", {}).get("credit_limit", {})
    if limit_data:
        st.markdown("#### 🎯 Credit Limit Optimizer")
        cl1, cl2 = st.columns([1.5, 1])
        with cl1:
            st.info(f"**Approved Limit:** ₹{_safe_float(limit_data.get('approved_limit')):,.0f} Cr")
            st.write(limit_data.get("reason", ""))
        with cl2:
            for line in limit_data.get("breakdown", []):
                st.write(f"• {line}")


# ═══════════════════════════════════════════════════════════════════════════ #
# DASHBOARD 4 — Specialized Asset/Liability & Portfolio Monitor
# ═══════════════════════════════════════════════════════════════════════════ #

def render_specialized_monitor(financials: dict, company_name: str):
    """Dashboard 4: Advanced monitoring for ALM, Shareholding, and Portfolio."""
    st.markdown("### 🔍 Specialized Asset/Liability & Portfolio Monitor")
    
    # Helper to find data in nested doc_type or flat merge
    def get_data(key):
        return financials.get(key) or financials.get("merged_all", {}).get(key) or {}

    # 1. Shareholding
    sh = get_data("shareholding_pattern")
    if sh and any(sh.get(k) for k in ["promoter_holding_percent", "public_holding_percent"]):
        st.markdown("#### 📊 Shareholding Pattern")
        labels = ["Promoter", "Public", "Institutional"]
        values = [_safe_float(sh.get("promoter_holding_percent")), 
                  _safe_float(sh.get("public_holding_percent")), 
                  _safe_float(sh.get("institutional_holding_percent"))]
        if sum(values) > 0:
            fig = px.pie(names=labels, values=values, hole=0.4, color_discrete_sequence=[VIVRITI_BLUE, VIVRITI_GOLD, LIGHT_BLUE])
            fig.update_layout(height=250, margin=dict(t=0,b=0,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)
    
    # 2. ALM
    alm = get_data("alm_report")
    sl = alm.get("structural_liquidity") or financials.get("structural_liquidity")
    if sl:
        st.markdown("#### ⚖️ ALM Structural Liquidity")
        c1, c2 = st.columns(2)
        c1.metric("Cumulative GAP (Cr)", f"₹{sl.get('cumulative_gap_crores', 0)} Cr")
        c2.metric("Net GAP (%)", f"{sl.get('net_gap_percent', 0)}%")

    # 3. Borrowing
    bp = get_data("borrowing_profile")
    lenders = bp.get("lender_details") or financials.get("lender_details")
    if lenders:
        st.markdown("#### 🏦 Borrowing Profile")
        names = [l.get("name", "Other") for l in lenders]
        outs = [_safe_float(l.get("outstanding", 0)) for l in lenders]
        fig = px.bar(x=names, y=outs, labels={'x':'Lender','y':'Outstanding'}, color_discrete_sequence=[VIVRITI_BLUE])
        st.plotly_chart(fig, use_container_width=True)

    # 4. Portfolio
    pc = get_data("portfolio_cuts")
    pq = pc.get("portfolio_quality") or financials.get("portfolio_quality")
    if pq:
        st.markdown("#### 🎯 Portfolio Performance")
        st.metric("GNPA %", f"{pq.get('gnpa_percent', 0)}%")
