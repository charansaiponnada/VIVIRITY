"""
dashboards/trend_dashboard.py
Trend Analysis Dashboard for Intelli-Credit.

Visualizations:
1. Revenue & Profitability Trend
2. Margin Evolution
3. Leverage & Liquidity
4. CAGR Comparison
5. Momentum Score
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

VIVRITI_BLUE = "#1B3A6B"
VIVRITI_GOLD = "#C9A84C"
GREEN = "#1E8449"
ORANGE = "#D68910"
RED = "#C0392B"


def render_trend_analysis(trend_analysis: dict, company_name: str):
    """
    Render the complete trend analysis dashboard.
    Expects trend_analysis dict from core/trend_analysis.py
    """
    if not trend_analysis:
        st.info("Trend analysis data not available.")
        return

    st.markdown("### 📈 Multi-Year Trend Analysis")
    st.caption(f"Historical performance analysis for {company_name}")

    years = trend_analysis.get("years_analyzed", [])
    yearly_summary = trend_analysis.get("yearly_summary", [])

    if not years or not yearly_summary:
        st.warning("Insufficient historical data for trend analysis.")
        return

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Years Analyzed", len(years))
    col2.metric("Period", f"{min(years)}-{max(years)}")

    overall_momentum = trend_analysis.get("overall_momentum_score", 0)
    overall_trend = trend_analysis.get("overall_trend", "unknown")

    col3.metric("Momentum Score", f"{overall_momentum:.1f}")

    trend_icon = (
        "📈"
        if overall_trend == "improving"
        else "➡️"
        if overall_trend == "stable"
        else "📉"
    )
    col4.metric("Trend Direction", f"{trend_icon} {overall_trend.title()}")

    st.markdown("---")

    tabs = st.tabs(
        ["📊 Revenue Trend", "📉 Margins", "⚖️ Leverage", "📐 CAGR", "🎯 Momentum"]
    )

    with tabs[0]:
        _render_revenue_trend(yearly_summary)

    with tabs[1]:
        _render_margin_trend(yearly_summary)

    with tabs[2]:
        _render_leverage_trend(yearly_summary)

    with tabs[3]:
        _render_cagr_comparison(trend_analysis.get("cagr_summary", []))

    with tabs[4]:
        _render_momentum_score(trend_analysis)

    st.markdown("---")
    _render_insights_and_risks(trend_analysis)


def _render_revenue_trend(yearly_summary: list):
    """Render revenue, EBITDA, PAT trend chart."""
    years = [y["year"] for y in yearly_summary]
    revenue = [y.get("revenue") for y in yearly_summary]
    ebitda = [y.get("ebitda") for y in yearly_summary]
    pat = [y.get("pat") for y in yearly_summary]

    fig = make_subplots(specs=[[{"secondary_y": False}]])

    fig.add_trace(
        go.Bar(
            x=years, y=revenue, name="Revenue", marker_color=VIVRITI_BLUE, opacity=0.7
        )
    )
    fig.add_trace(
        go.Scatter(
            x=years,
            y=ebitda,
            name="EBITDA",
            mode="lines+markers",
            line=dict(color=GREEN, width=3),
            marker=dict(size=8),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=years,
            y=pat,
            name="PAT",
            mode="lines+markers",
            line=dict(color=VIVRITI_GOLD, width=3),
            marker=dict(size=8),
        )
    )

    fig.update_layout(
        title="Revenue, EBITDA & PAT Trend (₹ Crores)",
        xaxis_title="Financial Year",
        yaxis_title="Amount (₹ Crores)",
        height=400,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    st.plotly_chart(fig, use_container_width=True)

    if len(revenue) >= 2 and revenue[0] and revenue[-1]:
        total_growth = ((revenue[-1] - revenue[0]) / revenue[0]) * 100
        st.info(
            f"Total Revenue Growth ({years[0]} to {years[-1]}): **{total_growth:.1f}%**"
        )


def _render_margin_trend(yearly_summary: list):
    """Render margin trend chart."""
    years = [y["year"] for y in yearly_summary]

    ebitda_margin = []
    pat_margin = []

    for y in yearly_summary:
        rev = y.get("revenue")
        ebitda_margin.append(
            round((y.get("ebitda", 0) / rev * 100), 2)
            if rev and y.get("ebitda")
            else None
        )
        pat_margin.append(
            round((y.get("pat", 0) / rev * 100), 2) if rev and y.get("pat") else None
        )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=years,
            y=ebitda_margin,
            name="EBITDA Margin",
            mode="lines+markers",
            line=dict(color=GREEN, width=3),
            marker=dict(size=10),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=years,
            y=pat_margin,
            name="PAT Margin",
            mode="lines+markers",
            line=dict(color=RED, width=3),
            marker=dict(size=10),
        )
    )

    fig.update_layout(
        title="Margin Trend (%)",
        xaxis_title="Financial Year",
        yaxis_title="Margin (%)",
        height=350,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    latest_ebitda = next((v for v in reversed(ebitda_margin) if v is not None), None)
    earliest_ebitda = next((v for v in ebitda_margin if v is not None), None)

    if latest_ebitda and earliest_ebitda:
        margin_change = latest_ebitda - earliest_ebitda
        direction = "expanded" if margin_change > 0 else "contracted"
        st.info(
            f"EBITDA Margin {direction} by **{abs(margin_change):.1f}pp** over the period"
        )


def _render_leverage_trend(yearly_summary: list):
    """Render leverage and liquidity trend."""
    years = [y["year"] for y in yearly_summary]
    de_ratio = [y.get("debt_equity") for y in yearly_summary]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=years,
            y=de_ratio,
            name="Debt/Equity Ratio",
            mode="lines+markers",
            line=dict(color=RED, width=3),
            marker=dict(size=10),
            fill="tozeroy",
            fillcolor="rgba(192,57,43,0.1)",
        ),
        secondary_y=False,
    )

    fig.update_layout(
        title="Leverage Trend (Debt/Equity Ratio)",
        xaxis_title="Financial Year",
        yaxis_title="Debt/Equity Ratio",
        height=350,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    latest_de = next((v for v in reversed(de_ratio) if v is not None), None)
    if latest_de:
        if latest_de < 0.5:
            st.success(
                f"Current D/E ratio of **{latest_de:.2f}x** indicates conservative leverage"
            )
        elif latest_de < 1.5:
            st.info(
                f"Current D/E ratio of **{latest_de:.2f}x** is within acceptable range"
            )
        else:
            st.warning(
                f"Current D/E ratio of **{latest_de:.2f}x** indicates high leverage"
            )


def _render_cagr_comparison(cagr_summary: list):
    """Render CAGR comparison bar chart."""
    if not cagr_summary:
        st.info("CAGR data not available")
        return

    labels = []
    values = []
    colors = []

    for item in cagr_summary[:6]:
        metric = item.get("metric", "")
        label = (
            metric.replace("_crores", "")
            .replace("_percent", "%")
            .replace("_", " ")
            .title()
        )
        labels.append(label)
        values.append(item.get("cagr", 0))
        colors.append(GREEN if item.get("cagr", 0) > 0 else RED)

    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=colors))

    fig.update_layout(
        title="CAGR Comparison (%)",
        xaxis_title="Metric",
        yaxis_title="CAGR (%)",
        height=350,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### CAGR Summary")
    for item in cagr_summary[:6]:
        metric = item.get("metric", "").replace("_", " ").title()
        cagr = item.get("cagr", 0)
        assessment = item.get("assessment", "")
        icon = "🟢" if cagr > 10 else "🟡" if cagr > 0 else "🔴"
        st.write(f"{icon} **{metric}**: {cagr:.1f}% ({assessment})")


def _render_momentum_score(trend_analysis: dict):
    """Render overall momentum score gauge."""
    score = trend_analysis.get("overall_momentum_score", 0)
    trend = trend_analysis.get("overall_trend", "unknown")

    color = GREEN if trend == "improving" else ORANGE if trend == "stable" else RED

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=score,
            title={"text": "Overall Momentum Score"},
            gauge={
                "axis": {"range": [-100, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [-100, -20], "color": "#fadbd8"},
                    {"range": [-20, 20], "color": "#fdebd0"},
                    {"range": [20, 100], "color": "#d5f5e3"},
                ],
                "threshold": {
                    "line": {"color": VIVRITI_BLUE, "width": 4},
                    "thickness": 0.8,
                    "value": 0,
                },
            },
            number={"suffix": "", "font": {"size": 36}},
        )
    )

    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)

    momentum_desc = {
        "strong_positive": "Strong upward momentum - consistent positive growth",
        "moderate_positive": "Moderate positive momentum - generally improving",
        "neutral": "Neutral momentum - stable performance",
        "moderate_negative": "Moderate downward pressure - declining trend",
        "strong_negative": "Strong negative momentum - concerning decline",
    }

    st.info(f"**Assessment:** {momentum_desc.get(trend, 'Unknown')}")


def _render_insights_and_risks(trend_analysis: dict):
    """Render key insights and risk signals."""
    insights = trend_analysis.get("key_insights", [])
    risks = trend_analysis.get("risk_signals", [])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### ✅ Key Insights")
        if insights:
            for insight in insights:
                st.success(f"- {insight}")
        else:
            st.info("No significant positive insights from trend analysis.")

    with col2:
        st.markdown("#### ⚠️ Risk Signals")
        if risks:
            for risk in risks:
                st.warning(f"- {risk}")
        else:
            st.success("No significant risk signals from trend analysis.")


def render_trend_summary_card(trend_analysis: dict) -> dict:
    """
    Render a compact trend summary card for the main dashboard.
    Returns summary dict.
    """
    if not trend_analysis:
        return {"status": "unavailable", "trend": "unknown", "momentum": 0}

    return {
        "status": "analyzed",
        "trend": trend_analysis.get("overall_trend", "unknown"),
        "momentum": trend_analysis.get("overall_momentum_score", 0),
        "years": len(trend_analysis.get("years_analyzed", [])),
        "key_insights_count": len(trend_analysis.get("key_insights", [])),
        "risk_signals_count": len(trend_analysis.get("risk_signals", [])),
    }
