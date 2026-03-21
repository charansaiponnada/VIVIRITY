"""Dashboards package for Intelli-Credit."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

_dashboards_py = {}
_exec_globals = {"__name__": "dashboards._py"}
exec(
    compile(open("dashboards.py", "rb").read(), "dashboards.py", "exec"), _exec_globals
)

for _name in [
    "render_credit_command_center",
    "render_risk_intelligence",
    "render_financial_health",
    "render_specialized_monitor",
]:
    globals()[_name] = _exec_globals[_name]

from dashboards.trend_dashboard import render_trend_analysis, render_trend_summary_card
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
