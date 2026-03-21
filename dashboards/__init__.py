"""Dashboards package for Intelli-Credit."""

from dashboards_main import (
    render_credit_command_center,
    render_risk_intelligence,
    render_financial_health,
    render_specialized_monitor,
)
from dashboards.trend_dashboard import (
    render_trend_analysis,
    render_trend_summary_card,
)
from dashboards.realtime_dashboard import (
    render_live_data_panel,
    render_live_data_summary,
)
from dashboards.stress_testing_dashboard import (
    render_stress_testing,
    render_stress_summary_card,
)

__all__ = [
    "render_credit_command_center",
    "render_risk_intelligence",
    "render_financial_health",
    "render_specialized_monitor",
    "render_trend_analysis",
    "render_trend_summary_card",
    "render_live_data_panel",
    "render_live_data_summary",
    "render_stress_testing",
    "render_stress_summary_card",
]
