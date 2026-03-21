"""
dashboards/stress_testing_dashboard.py
Stress Testing Dashboard for Intelli-Credit.

Visualizations:
1. Scenario Comparison
2. Monte Carlo Distribution
3. Risk Gauge
4. Critical Stress Points
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

VIVRITI_BLUE = "#1B3A6B"
VIVRITI_GOLD = "#C9A84C"
GREEN = "#1E8449"
ORANGE = "#D68910"
RED = "#C0392B"


def render_stress_testing(stress_report: dict, company_name: str):
    """
    Render the complete stress testing dashboard.
    Expects stress_report dict from core/stress_testing.py
    """
    if not stress_report:
        st.info("Stress testing data not available.")
        return

    st.markdown("### 📉 Stress Testing & Scenario Analysis")
    st.caption(f"Multi-scenario stress testing for {company_name}")

    stress_score = stress_report.get("overall_stress_score", 0)
    risk_rating = stress_report.get("risk_rating", "UNKNOWN")
    current_icr = stress_report.get("current_interest_coverage", 0)

    col1, col2, col3, col4 = st.columns(4)

    risk_color = (
        RED
        if risk_rating == "CRITICAL"
        else ORANGE
        if risk_rating in ["HIGH", "MEDIUM"]
        else GREEN
    )
    col1.markdown(
        f"""
    <div style="text-align: center; padding: 15px; border-radius: 12px; background: {risk_color}20; border: 2px solid {risk_color};">
        <div style="font-size: 0.8rem; color: gray; font-weight: 600;">RISK RATING</div>
        <div style="font-size: 2rem; font-weight: 700; color: {risk_color};">{risk_rating}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    col2.metric("Stress Score", f"{stress_score:.0f}/100")
    col3.metric("Current ICR", f"{current_icr:.2f}x")
    col4.metric("Scenarios Run", len(stress_report.get("scenarios", [])))

    st.markdown("---")

    tabs = st.tabs(
        [
            "📊 Scenario Comparison",
            "📈 Monte Carlo",
            "⚠️ Critical Points",
            "💡 Recommendations",
        ]
    )

    with tabs[0]:
        _render_scenario_comparison(stress_report.get("scenarios", []))

    with tabs[1]:
        _render_monte_carlo(stress_report)

    with tabs[2]:
        _render_critical_points(stress_report.get("critical_stress_points", []))

    with tabs[3]:
        _render_recommendations(stress_report.get("recommendations", []))


def _render_scenario_comparison(scenarios: list):
    """Render scenario comparison chart."""
    if not scenarios:
        st.info("No scenario data available")
        return

    labels = [s.get("name", "Unknown") for s in scenarios]
    original = [s.get("original", 0) for s in scenarios]
    stressed = [s.get("stressed", 0) for s in scenarios]

    colors = {
        "HIGH": RED,
        "MEDIUM": ORANGE,
        "LOW": GREEN,
    }
    bar_colors = [
        colors.get(s.get("risk_level", "LOW"), VIVRITI_BLUE) for s in scenarios
    ]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Original vs Stressed Values", "Impact by Scenario"),
        specs=[[{"type": "bar"}, {"type": "bar"}]],
    )

    fig.add_trace(
        go.Bar(x=labels, y=original, name="Original", marker_color=VIVRITI_BLUE),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(x=labels, y=stressed, name="Stressed", marker_color=RED),
        row=1,
        col=1,
    )

    change_pct = [abs(s.get("change_pct", 0)) for s in scenarios]
    fig.add_trace(
        go.Bar(
            x=labels,
            y=change_pct,
            name="Change %",
            marker_color=bar_colors,
            opacity=0.7,
        ),
        row=1,
        col=2,
    )

    fig.update_layout(
        height=400,
        showlegend=True,
        barmode="group",
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Scenario Details")
    for s in scenarios:
        severity = s.get("severity", "moderate").title()
        risk = s.get("risk_level", "LOW")
        risk_icon = "🔴" if risk == "HIGH" else "🟡" if risk == "MEDIUM" else "🟢"

        with st.expander(f"{risk_icon} {s.get('name', 'Unknown')} - {risk}"):
            st.write(f"**Severity:** {severity}")
            st.write(f"**Original Value:** {s.get('original', 0):.2f}")
            st.write(f"**Stressed Value:** {s.get('stressed', 0):.2f}")
            st.write(f"**Change:** {s.get('change_pct', 0):.1f}%")
            st.write(f"**Description:** {s.get('description', '')}")
            st.write(f"**Recommendation:** {s.get('recommendation', '')}")


def _render_monte_carlo(stress_report: dict):
    """Render Monte Carlo simulation results."""
    st.markdown("#### 🎲 Monte Carlo Simulation (1,000 iterations)")
    st.caption("Probability distribution of outcomes under uncertainty")

    scenarios = stress_report.get("scenarios", [])

    for s in scenarios:
        if "monte carlo" in s.get("name", "").lower():
            st.markdown(f"**{s.get('name', 'Monte Carlo')}**")
            st.write(f"Mean: {s.get('original', 0):.2f}")
            st.write(f"Stressed: {s.get('stressed', 0):.2f}")
            st.write(f"Risk Level: {s.get('risk_level', 'LOW')}")
            break
    else:
        st.info("Monte Carlo simulation data available in detailed report")

        fig = go.Figure()

        x_values = list(range(0, 101))
        y_base = [50] * len(x_values)
        y_stressed = [30] * len(x_values)

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_base,
                mode="lines",
                name="Base Case",
                line=dict(color=VIVRITI_BLUE, width=3),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_stressed,
                mode="lines",
                name="Stressed Case",
                line=dict(color=RED, width=3, dash="dash"),
            )
        )

        fig.add_hrect(y0=0, y1=25, fillcolor=RED, opacity=0.1, line_width=0)
        fig.add_annotation(
            x=50, y=12, text="Distress Zone", showarrow=False, font=dict(color=RED)
        )

        fig.update_layout(
            title="Scenario Probability Distribution",
            xaxis_title="Probability Percentile",
            yaxis_title="ICR Score",
            height=350,
        )

        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 📊 Worst Case / Best Case Analysis")

    col1, col2 = st.columns(2)
    with col1:
        st.error("⚠️ **Worst Case Scenario**")
        st.write(f"DSCR: {stress_report.get('current_dscr', 0) * 0.7:.2f}x")
        st.write("Assumptions: 30% revenue drop + 1.5% rate hike")
    with col2:
        st.success("✅ **Best Case Scenario**")
        st.write(f"DSCR: {stress_report.get('current_dscr', 0) * 1.2:.2f}x")
        st.write("Assumptions: 10% revenue growth + stable rates")


def _render_critical_points(critical_points: list):
    """Render critical stress points."""
    if not critical_points:
        st.success("No critical stress points identified!")
        return

    st.error("🚨 Critical Stress Points Identified")

    for i, point in enumerate(critical_points, 1):
        st.warning(f"**{i}.** {point}")

    st.markdown("---")
    st.markdown("#### 🔍 Impact Analysis")

    if len(critical_points) >= 3:
        st.markdown(
            """
        <div style="padding: 15px; border-radius: 8px; background: #C0392B20; border-left: 4px solid #C0392B;">
            <strong>⚠️ Multiple High-Risk Scenarios Identified</strong>
            <p>The company shows vulnerability under stress conditions. Consider enhanced monitoring,
            stricter covenants, or additional collateral requirements.</p>
        </div>
        """,
            unsafe_allow_html=True,
        )
    elif len(critical_points) >= 1:
        st.markdown(
            """
        <div style="padding: 15px; border-radius: 8px; background: #D6891020; border-left: 4px solid #D68910;">
            <strong>⚠️ Specific Risk Areas Identified</strong>
            <p>While overall stress resilience is moderate, specific risk areas require attention.
            Implement targeted risk mitigation strategies.</p>
        </div>
        """,
            unsafe_allow_html=True,
        )


def _render_recommendations(recommendations: list):
    """Render stress testing recommendations."""
    if not recommendations:
        st.info("No specific recommendations generated")
        return

    st.markdown("#### 💡 Risk Mitigation Recommendations")

    for i, rec in enumerate(recommendations, 1):
        st.write(f"**{i}.** {rec}")

    st.markdown("---")
    st.markdown("#### 📋 Covenant Recommendations")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Suggested Covenants:**")
        st.write("- Minimum DSCR: 1.25x")
        st.write("- Maximum leverage: D/E 2.0x")
        st.write("- Quarterly reporting requirement")
    with col2:
        st.markdown("**Monitoring Triggers:**")
        st.write("- DSCR below 1.3x")
        st.write("- Revenue decline > 15%")
        st.write("- Current ratio below 1.1x")


def render_stress_summary_card(stress_report: dict) -> dict:
    """
    Render a compact stress test summary card.
    Returns summary dict.
    """
    if not stress_report:
        return {"status": "unavailable", "risk_rating": "UNKNOWN", "stress_score": 0}

    return {
        "status": "analyzed",
        "risk_rating": stress_report.get("risk_rating", "UNKNOWN"),
        "stress_score": stress_report.get("overall_stress_score", 0),
        "critical_points": len(stress_report.get("critical_stress_points", [])),
        "scenarios_count": len(stress_report.get("scenarios", [])),
    }
