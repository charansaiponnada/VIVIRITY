"""Dashboards package for Intelli-Credit."""

import sys
from importlib import import_module

__all__ = [
    "render_credit_command_center",
    "render_risk_intelligence",
    "render_financial_health",
    "render_specialized_monitor",
    "render_live_data_panel",
    "render_live_data_summary",
    "render_trend_analysis",
    "render_trend_summary_card",
    "render_stress_testing",
    "render_stress_summary_card",
]

_root = sys.modules.get("dashboards") or import_module("dashboards")
sys.modules[f"{__name__}.realtime"] = import_module("dashboards.realtime_dashboard")
sys.modules[f"{__name__}.trend"] = import_module("dashboards.trend_dashboard")
sys.modules[f"{__name__}.stress"] = import_module("dashboards.stress_testing_dashboard")


def __getattr__(name):
    if name in (
        "render_credit_command_center",
        "render_risk_intelligence",
        "render_financial_health",
        "render_specialized_monitor",
    ):
        return getattr(_root, name)
    if name in ("render_live_data_panel", "render_live_data_summary"):
        return getattr(sys.modules[f"{__name__}.realtime"], name)
    if name in ("render_trend_analysis", "render_trend_summary_card"):
        return getattr(sys.modules[f"{__name__}.trend"], name)
    if name in ("render_stress_testing", "render_stress_summary_card"):
        return getattr(sys.modules[f"{__name__}.stress"], name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
