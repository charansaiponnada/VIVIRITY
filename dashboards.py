"""
dashboards.py
-------------
High-Impact Credit Risk Dashboards for Intelli-Credit.

Three professional dashboards:
  1. Credit Risk Command Center — overall credit profile overview
  2. Risk Intelligence Monitor — risk signals, litigation, fraud, early warnings
  3. Financial Health Analyzer — financial trends, ratios, health score
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
        return float(str(val).replace(",", "").replace("₹", "").strip())
    except (ValueError, TypeError):
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════ #
# DASHBOARD 1 — Credit Risk Command Center
# ═══════════════════════════════════════════════════════════════════════════ #

def render_credit_command_center(scoring: dict, ml_results: dict,
                                  financials: dict, company_name: str):
    """
    Dashboard 1: Instant overview of the company's credit profile.
    - Credit Score Gauge
    - Five Cs Radar Chart
    - Risk Rating Indicator
    - ML Lending Probability
    - Recommended Loan Limit + Interest Rate
    """
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

    # ── Row 1: Score Gauge + ML Probability + Rating ──────────────────── #
    col1, col2, col3 = st.columns([1.3, 1, 1])

    with col1:
        # Credit Score Gauge
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=score,
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
                "threshold": {
                    "line": {"color": RED, "width": 4},
                    "thickness": 0.75,
                    "value": 50,
                },
            },
            number={"suffix": "/100", "font": {"size": 28}},
        ))
        fig.update_layout(height=250, margin=dict(t=40, b=10, l=30, r=30))
        st.plotly_chart(fig, width="stretch")

    with col2:
        # ML Lending Probability Gauge
        fig2 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=ml_prob * 100,
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
        st.plotly_chart(fig2, width="stretch")

    with col3:
        # Rating + Decision card
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

    # ── Row 2: Five Cs Radar Chart + Score Breakdown ──────────────────── #
    col_a, col_b = st.columns([1.2, 1])

    with col_a:
        # Radar Chart
        categories = ["Character", "Capacity", "Capital", "Collateral", "Conditions"]
        values = [
            five_cs.get("character_score", 0),
            five_cs.get("capacity_score", 0),
            five_cs.get("capital_score", 0),
            five_cs.get("collateral_score", 0),
            five_cs.get("conditions_score", 0),
        ]
        # Close the radar
        categories_closed = categories + [categories[0]]
        values_closed = values + [values[0]]

        fig3 = go.Figure()
        fig3.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill="toself",
            fillcolor="rgba(27, 58, 107, 0.15)",
            line=dict(color=VIVRITI_BLUE, width=2.5),
            name="Five Cs",
            marker=dict(size=8, color=VIVRITI_BLUE),
        ))
        fig3.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10)),
                angularaxis=dict(tickfont=dict(size=12, color=VIVRITI_BLUE)),
            ),
            title=dict(text="Five Cs Assessment", font=dict(size=14, color=VIVRITI_BLUE)),
            height=320,
            margin=dict(t=50, b=30, l=50, r=50),
            showlegend=False,
        )
        st.plotly_chart(fig3, width="stretch")

    with col_b:
        # Score Breakdown bars
        st.markdown("**Score Breakdown**")
        breakdown = risk_score.get("score_breakdown", {})
        weights = {"capacity": 0.30, "character": 0.25, "capital": 0.20, "collateral": 0.15, "conditions": 0.10}
        colors = [LIGHT_BLUE, VIVRITI_BLUE, GREEN, ORANGE, PURPLE]

        labels = []
        contributions = []
        for i, (c, w) in enumerate(weights.items()):
            bd = breakdown.get(c, {})
            contrib = bd.get("contribution", 0)
            raw = bd.get("score", 0)
            labels.append(f"{c.title()} ({w:.0%})")
            contributions.append(contrib)

        fig4 = go.Figure(go.Bar(
            x=contributions,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{c:.1f}" for c in contributions],
            textposition="auto",
        ))
        fig4.update_layout(
            height=300,
            margin=dict(t=10, b=10, l=10, r=10),
            xaxis_title="Contribution to Final Score",
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig4, width="stretch")

        penalty = risk_score.get("penalty_applied", 0)
        if penalty > 0:
            st.warning(f"⚠ Penalty Applied: **-{penalty:.1f}** points")

    # ── Row 3: Model Divergence Alert ─────────────────────────────────── #
    divergence = rec.get("divergence_report", {})
    if divergence and divergence.get("severity") != "NONE":
        sev = divergence.get("severity", "MODERATE")
        icon = "🔴" if sev == "HIGH" else "🟠"
        with st.expander(f"{icon} Model Divergence Detected — {sev}", expanded=(sev == "HIGH")):
            c1, c2, c3 = st.columns(3)
            c1.metric("Rule-Based Score", f"{divergence.get('rule_score', 0):.1f}")
            c2.metric("ML Score", f"{divergence.get('ml_score', 0):.1f}")
            c3.metric("Blended Score", f"{divergence.get('blended_score', 0):.1f}")
            st.markdown(f"**Explanation:** {divergence.get('explanation', '')}")
            st.markdown(f"**Action:** {divergence.get('action', '')}")
            for f in divergence.get("factors", []):
                st.write(f"• {f}")


# ═══════════════════════════════════════════════════════════════════════════ #
# DASHBOARD 2 — Risk Intelligence Monitor
# ═══════════════════════════════════════════════════════════════════════════ #

def render_risk_intelligence(scoring: dict, research: dict,
                              cross_ref: dict, company_name: str):
    """
    Dashboard 2: Risk signals, fraud detection, early warnings, timeline.
    - Risk Signal table with confidence + source
    - Fraud Signals panel
    - Risk Timeline
    - Risk Severity Heatmap
    """
    st.markdown("### 🛡️ Risk Intelligence Monitor")
    st.caption(f"Discovered risks and early warning signals for **{company_name}**")

    rec = scoring.get("recommendation", {})

    # ── Risk Signals with Confidence ──────────────────────────────────── #
    signals = rec.get("risk_signals_detail", [])
    fraud_signals = rec.get("fraud_signals", [])
    fraud_level = rec.get("fraud_risk_level", "LOW")
    timeline = rec.get("risk_timeline", [])

    # Top-level metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Risk Signals", len(signals))
    c2.metric("Fraud Signals", len(fraud_signals))
    c3.metric("Fraud Risk", fraud_level,
              delta="Critical" if fraud_level == "CRITICAL" else None,
              delta_color="inverse")
    high_conf = sum(1 for s in signals if s.get("confidence") == "HIGH")
    c4.metric("High Confidence", high_conf)

    # ── Risk Signals Table ────────────────────────────────────────────── #
    if signals:
        st.markdown("---")
        st.markdown("#### 🎯 Risk Signals (with Confidence Engine)")

        # Severity heatmap data
        categories = {}
        for s in signals:
            cat = s.get("category", "other")
            if cat not in categories:
                categories[cat] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
            sev = s.get("severity", "LOW")
            if sev in categories[cat]:
                categories[cat][sev] += 1

        # Render heatmap if enough data
        if len(categories) >= 2:
            cat_names = list(categories.keys())
            sev_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            z = [[categories[cat].get(sev, 0) for sev in sev_levels] for cat in cat_names]
            fig_heat = go.Figure(go.Heatmap(
                z=z, x=sev_levels, y=[c.title() for c in cat_names],
                colorscale=[[0, "#d5f5e3"], [0.33, "#fef9e7"], [0.66, "#fdebd0"], [1, "#fadbd8"]],
                text=z, texttemplate="%{text}", showscale=False,
            ))
            fig_heat.update_layout(
                title="Risk Severity Heatmap",
                height=200, margin=dict(t=40, b=20, l=80, r=20),
            )
            st.plotly_chart(fig_heat, width="stretch")

        # Individual signal cards
        for s in signals:
            conf = s.get("confidence", "LOW")
            sev = s.get("severity", "MEDIUM")
            conf_color = GREEN if conf == "LOW" else ORANGE if conf == "MEDIUM" else RED
            sev_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev, "⚪")

            with st.expander(f"{sev_icon} {s.get('signal_type', 'Unknown')} — Confidence: {conf}"):
                rc1, rc2 = st.columns([2, 1])
                with rc1:
                    st.write(f"**Signal:** {s.get('description', '')}")
                    st.write(f"**Source:** {s.get('source', 'Unknown')}")
                    st.write(f"**Sources Found:** {s.get('sources_found', 1)}")
                    if s.get("reference_text"):
                        st.caption(f"Reference: {s['reference_text']}")
                with rc2:
                    st.markdown(f"""
<div style="text-align:center; padding:10px; border-radius:8px; background: {'#fadbd8' if conf == 'HIGH' else '#fef9e7' if conf == 'MEDIUM' else '#d5f5e3'};">
<div style="font-size:0.7rem; color: {GREY}; font-weight:600;">CONFIDENCE</div>
<div style="font-size:1.4rem; font-weight:700; color: {conf_color};">{conf}</div>
<div style="font-size:0.7rem; color: {GREY}; margin-top:4px;">
Base: -{s.get('base_penalty',0)} &nbsp; Adjusted: -{s.get('adjusted_penalty',0):.1f}
</div>
<div style="font-size:0.65rem; color: {GREY};">
Conf ×{s.get('confidence_factor',1):.2f} &nbsp; Temp ×{s.get('temporal_factor',1):.2f}
</div>
</div>""", unsafe_allow_html=True)
    else:
        st.success("✅ No risk signals detected.")

    # ── Fraud Signals ─────────────────────────────────────────────────── #
    st.markdown("---")
    st.markdown("#### 🕵️ Fraud Signal Detector")

    if fraud_signals:
        fraud_color = RED if fraud_level in ("CRITICAL", "HIGH") else ORANGE if fraud_level == "MEDIUM" else GREEN
        st.markdown(f"""
<div style="padding: 12px 20px; border-radius: 10px; border-left: 5px solid {fraud_color}; background: {'#fadbd8' if fraud_level in ('CRITICAL','HIGH') else '#fef9e7' if fraud_level == 'MEDIUM' else '#d5f5e3'};">
<strong>Fraud Risk: {fraud_level}</strong> — {len(fraud_signals)} signal(s) detected
</div>""", unsafe_allow_html=True)
        st.markdown("")

        for fs in fraud_signals:
            sev_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(fs.get("severity", "LOW"), "⚪")
            st.markdown(f"{sev_icon} **{fs.get('signal_type', '')}** [{fs.get('severity', '')}]")
            st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;{fs.get('description', '')}")
            if fs.get("evidence"):
                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;Evidence: {fs['evidence']}")
    else:
        st.success("✅ No fraud signals detected.")

    # ── Corporate Risk Timeline ───────────────────────────────────────── #
    st.markdown("---")
    st.markdown("#### 📅 Corporate Risk Timeline")

    if timeline:
        # Timeline visualization
        years = [e.get("year", 0) for e in timeline]
        events = [e.get("event", "") for e in timeline]
        impacts = [e.get("impact", "neutral") for e in timeline]
        colors_tl = [GREEN if i == "positive" else RED if i == "negative" else GREY for i in impacts]

        fig_tl = go.Figure()
        fig_tl.add_trace(go.Scatter(
            x=years, y=[0] * len(years),
            mode="markers+text",
            marker=dict(size=14, color=colors_tl, line=dict(width=2, color="white")),
            text=[f"{y}" for y in years],
            textposition="top center",
            textfont=dict(size=10),
            hovertext=[f"{y}: {e}" for y, e in zip(years, events)],
            hoverinfo="text",
        ))
        fig_tl.update_layout(
            height=120, margin=dict(t=10, b=30, l=30, r=30),
            yaxis=dict(visible=False, range=[-0.5, 0.5]),
            xaxis=dict(title="Year", dtick=1),
            showlegend=False,
        )
        st.plotly_chart(fig_tl, width="stretch")

        for e in timeline:
            icon = "🟢" if e.get("impact") == "positive" else "🔴" if e.get("impact") == "negative" else "⚪"
            st.write(f"{icon} **{e.get('year', '')}** — {e.get('event', '')} *({e.get('category', '')})*")
    else:
        st.info("No timeline events extracted from available data.")

    # ── Early Warning Signals ─────────────────────────────────────────── #
    ews = research.get("overall_sentiment", {}).get("early_warning_signals", [])
    if ews:
        st.markdown("---")
        st.markdown("#### ⚡ Early Warning Signals")
        for w in ews:
            st.warning(f"⚡ {w}")


# ═══════════════════════════════════════════════════════════════════════════ #
# DASHBOARD 3 — Financial Health Analyzer
# ═══════════════════════════════════════════════════════════════════════════ #

def render_financial_health(financials: dict, scoring: dict, company_name: str):
    """
    Dashboard 3: Financial strength visualization.
    - Key ratio gauges
    - Financial health score
    - Trend indicators (where available)
    """
    st.markdown("### 📊 Financial Health Analyzer")
    st.caption(f"Financial strength assessment for **{company_name}**")

    entity_type = financials.get("_entity_type", "corporate")

    # ── Key Financial Metrics ─────────────────────────────────────────── #
    metric_cfg = get_top_metrics(entity_type)
    cols = st.columns(4)
    for i, cfg in enumerate(metric_cfg[:4]):
        val = _safe_float(financials.get(cfg["key"]))
        label = cfg["label"]
        if cfg.get("fmt") == "cr":
            display = f"₹{val:,.0f} Cr" if val else "N/A"
        else:
            display = f"{val:,.2f}" if val else "N/A"

        if cfg.get("delta"):
            cols[i].metric(
                label,
                display,
                delta="Positive" if val and val > 0 else "Negative" if val else None,
                delta_color="normal" if val and val > 0 else "inverse",
            )
        else:
            cols[i].metric(label, display)

    nw = _safe_float(financials.get("net_worth_crores"))
    debt = _safe_float(financials.get("total_borrowings_crores"))
    total_assets = _safe_float(financials.get("total_assets_crores"))

    st.markdown("")

    # ── Financial Ratios ──────────────────────────────────────────────── #
    st.markdown("#### Key Financial Ratios")

    ratio_cfgs = get_ratio_gauges(entity_type)

    # Ratio gauges in a 3×2 grid
    cols = st.columns(3)
    for i, cfg in enumerate(ratio_cfgs):
        with cols[i % 3]:
            name = cfg["name"]
            val = _safe_float(financials.get(cfg["key"]))
            lo = cfg["lo"]
            hi = cfg["hi"]
            suffix = cfg["suffix"]
            tip = cfg["tip"]
            if val:
                # Determine colour from configured thresholds
                if cfg.get("inverted"):
                    green_max = cfg.get("green_min")
                    orange_max = cfg.get("orange_min")
                    color = GREEN if val <= green_max else ORANGE if val <= orange_max else RED
                else:
                    green_min = cfg.get("green_min")
                    orange_min = cfg.get("orange_min")
                    color = GREEN if val >= green_min else ORANGE if val >= orange_min else RED

                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=val,
                    title={"text": name, "font": {"size": 12}},
                    gauge={
                        "axis": {"range": [lo, hi]},
                        "bar": {"color": color},
                    },
                    number={"suffix": suffix, "font": {"size": 18}},
                ))
                fig.update_layout(height=180, margin=dict(t=40, b=5, l=20, r=20))
                st.plotly_chart(fig, width="stretch")
                st.caption(tip)
            else:
                st.metric(name, "N/A")
                st.caption(tip)

    # ── Financial Health Score ────────────────────────────────────────── #
    st.markdown("---")
    st.markdown("#### 💪 Financial Health Score")

    # Compute composite health score from configured components
    health_cfg = get_health_score_config(entity_type)
    breakdown_labels = []
    breakdown_values = []
    health_score = 0
    for comp in health_cfg:
        raw = _safe_float(financials.get(comp["key"]))
        if not raw:
            continue
        if comp.get("inverted"):
            score_component = max(1 - (raw / comp["max_val"]), 0) * comp["weight"]
        else:
            score_component = min(max(raw, 0) / comp["max_val"], 1.0) * comp["weight"]
        health_score += score_component
        breakdown_labels.append(comp["label"])
        breakdown_values.append(score_component)

    max_possible = 100
    health_pct = min(health_score, max_possible)

    col_h1, col_h2 = st.columns([1, 2])
    with col_h1:
        fig_h = go.Figure(go.Indicator(
            mode="gauge+number",
            value=health_pct,
            title={"text": "Health Score", "font": {"size": 14, "color": VIVRITI_BLUE}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": GREEN if health_pct >= 60 else ORANGE if health_pct >= 40 else RED},
                "steps": [
                    {"range": [0, 40], "color": "#fadbd8"},
                    {"range": [40, 60], "color": "#fdebd0"},
                    {"range": [60, 100], "color": "#d5f5e3"},
                ],
            },
            number={"suffix": "/100", "font": {"size": 24}},
        ))
        fig_h.update_layout(height=220, margin=dict(t=40, b=10, l=20, r=20))
        st.plotly_chart(fig_h, width="stretch")

    with col_h2:
        if breakdown_labels:
            fig_bd = go.Figure(go.Bar(
                x=breakdown_values,
                y=breakdown_labels,
                orientation="h",
                marker_color=[GREEN if v > 15 else ORANGE if v > 8 else RED for v in breakdown_values],
                text=[f"{v:.1f}" for v in breakdown_values],
                textposition="auto",
            ))
            fig_bd.update_layout(
                height=250,
                margin=dict(t=10, b=10, l=10, r=10),
                xaxis_title="Health Points",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_bd, width="stretch")

    # ── Balance Sheet Composition ─────────────────────────────────────── #
    if total_assets > 0 or nw > 0 or debt > 0:
        st.markdown("---")
        st.markdown("#### 🏗️ Balance Sheet Composition")

        equity = nw if nw > 0 else 0
        other_liab = max(total_assets - equity - debt, 0) if total_assets > 0 else 0

        labels = ["Equity (Net Worth)", "Borrowings", "Other Liabilities"]
        values = [equity, debt, other_liab]
        colors_bs = [GREEN, RED, GREY]

        # Filter out zeros
        filtered = [(l, v, c) for l, v, c in zip(labels, values, colors_bs) if v > 0]
        if filtered:
            fig_bs = go.Figure(go.Pie(
                labels=[f[0] for f in filtered],
                values=[f[1] for f in filtered],
                marker=dict(colors=[f[2] for f in filtered]),
                textinfo="label+percent",
                textfont_size=12,
                hole=0.4,
            ))
            fig_bs.update_layout(
                height=280,
                margin=dict(t=20, b=20, l=20, r=20),
                showlegend=True,
                legend=dict(orientation="h", y=-0.1),
            )
            st.plotly_chart(fig_bs, width="stretch")

    # ── Credit Limit Optimizer Output ─────────────────────────────────── #
    credit_limit = scoring.get("recommendation", {}).get("credit_limit", {})
    if credit_limit:
        st.markdown("---")
        st.markdown("#### 🎯 Credit Limit Optimizer")

        cl1, cl2, cl3 = st.columns(3)
        cl1.metric("Approved Limit", f"₹{credit_limit.get('approved_limit', 0):,.0f} Cr")
        cl2.metric("Debt Service Capacity", f"₹{credit_limit.get('debt_service_capacity', 0):,.0f} Cr")
        cl3.metric("Collateral Coverage", f"{credit_limit.get('collateral_coverage', 0):.2f}x")

        with st.expander("📋 Limit Calculation Breakdown"):
            for line in credit_limit.get("breakdown", []):
                st.write(f"• {line}")
            st.write(f"**Reason:** {credit_limit.get('reason', 'N/A')}")
