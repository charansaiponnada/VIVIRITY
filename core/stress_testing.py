"""
core/stress_testing.py
Stress Testing & Scenario Analysis Module for Intelli-Credit.

Features:
1. Rate Hike Scenario (impact on interest costs & DSCR)
2. Revenue Drop Scenario (business stress)
3. Liquidity Stress Test (cash runway)
4. DSCR Under Stress
5. Monte Carlo Simulation (worst/base/best case)

Usage:
    from core.stress_testing import StressTestEngine, ScenarioAnalysis
    engine = StressTestEngine()
    results = engine.run_all_stress_tests(financials)
"""

import json
import random
import math
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class ScenarioType(Enum):
    RATE_HIKE = "rate_hike"
    REVENUE_DROP = "revenue_drop"
    LIQUIDITY_STRESS = "liquidity_stress"
    DSCR_STRESS = "dscr_stress"
    MONTE_CARLO = "monte_carlo"
    COMBINED_STRESS = "combined_stress"


class ScenarioSeverity(Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


@dataclass
class ScenarioResult:
    """Result of a single stress scenario."""

    scenario_name: str
    scenario_type: str
    severity: str
    original_value: float
    stressed_value: float
    change_percent: float
    impact_on_dsscr: float
    risk_level: str
    description: str
    recommendation: str


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation result."""

    metric_name: str
    iterations: int
    mean: float
    median: float
    std_dev: float
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float
    worst_case: float
    best_case: float
    probability_of_default: float
    probability_of_breach: float


@dataclass
class StressTestReport:
    """Complete stress testing report."""

    company_name: str
    current_dsscr: float
    current_interest_coverage: float
    current_liquidity_ratio: float
    scenarios: List[ScenarioResult]
    monte_carlo_results: List[MonteCarloResult]
    overall_stress_score: float
    risk_rating: str
    critical_stress_points: List[str]
    recommendations: List[str]


class StressTestEngine:
    """
    Comprehensive stress testing engine for credit analysis.
    Simulates various economic and business stress scenarios.
    """

    DEFAULT_PARAMS = {
        "rate_hike": {"mild": 0.5, "moderate": 1.0, "severe": 1.5, "extreme": 2.5},
        "revenue_drop": {"mild": 10, "moderate": 20, "severe": 30, "extreme": 50},
        "liquidity_multiplier": {
            "mild": 0.8,
            "moderate": 0.6,
            "severe": 0.4,
            "extreme": 0.2,
        },
        "margin_compression": {"mild": 2, "moderate": 5, "severe": 8, "extreme": 15},
    }

    def __init__(self, params: Dict = None):
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}

    def run_all_stress_tests(
        self, financials: Dict, company_name: str = ""
    ) -> StressTestReport:
        """Run complete stress testing suite."""
        scenarios = []

        rate_hike_result = self.simulate_rate_hike(financials)
        scenarios.append(rate_hike_result)

        revenue_drop_result = self.simulate_revenue_drop(financials)
        scenarios.append(revenue_drop_result)

        liquidity_result = self.simulate_liquidity_stress(financials)
        scenarios.append(liquidity_result)

        dscr_result = self.simulate_dscr_stress(financials)
        scenarios.append(dscr_result)

        monte_carlo_results = self.run_monte_carlo(financials)

        overall_score = self._calculate_overall_stress_score(scenarios)
        risk_rating = self._get_risk_rating(overall_score)
        critical_points = self._get_critical_points(scenarios)
        recommendations = self._generate_recommendations(scenarios)

        return StressTestReport(
            company_name=company_name,
            current_dsscr=self._extract_dsscr(financials),
            current_interest_coverage=self._extract_interest_coverage(financials),
            current_liquidity_ratio=self._extract_current_ratio(financials),
            scenarios=scenarios,
            monte_carlo_results=monte_carlo_results,
            overall_stress_score=overall_score,
            risk_rating=risk_rating,
            critical_stress_points=critical_points,
            recommendations=recommendations,
        )

    def simulate_rate_hike(
        self, financials: Dict, severity: str = "moderate"
    ) -> ScenarioResult:
        """Simulate impact of interest rate hike on borrowing costs."""
        current_rate = self._extract_avg_interest_rate(financials)
        total_debt = self._extract_total_debt(financials)
        ebitda = self._extract_ebitda(financials)

        rate_increase = self.params["rate_hike"].get(severity, 1.0)
        new_rate = current_rate + rate_increase
        current_interest_cost = total_debt * (current_rate / 100)
        new_interest_cost = total_debt * (new_rate / 100)
        additional_interest = new_interest_cost - current_interest_cost

        current_icr = (
            ebitda / current_interest_cost
            if current_interest_cost > 0
            else float("inf")
        )
        new_icr = ebitda / new_interest_cost if new_interest_cost > 0 else float("inf")

        impact_on_icr = (
            ((new_icr - current_icr) / current_icr * 100)
            if current_icr != float("inf")
            else 0
        )
        impact_on_dsscr = new_icr - current_icr

        if severity == "extreme":
            risk_level = "HIGH"
            description = f"Rate hike of {rate_increase}% increases interest cost by ₹{additional_interest:.1f} Cr. ICR drops from {current_icr:.1f}x to {new_icr:.1f}x"
            recommendation = (
                "Consider hedging interest rate risk or renegotiating debt terms"
            )
        elif severity == "severe":
            risk_level = "MEDIUM"
            description = f"Rate hike of {rate_increase}% increases interest cost by ₹{additional_interest:.1f} Cr. ICR drops from {current_icr:.1f}x to {new_icr:.1f}x"
            recommendation = (
                "Maintain adequate liquidity buffer to absorb rate hike impact"
            )
        else:
            risk_level = "LOW"
            description = f"Rate hike of {rate_increase}% increases interest cost by ₹{additional_interest:.1f} Cr. ICR drops from {current_icr:.1f}x to {new_icr:.1f}x"
            recommendation = "Continue monitoring rate environment"

        return ScenarioResult(
            scenario_name=f"Interest Rate Hike ({severity.title()})",
            scenario_type=ScenarioType.RATE_HIKE.value,
            severity=severity,
            original_value=current_icr,
            stressed_value=new_icr,
            change_percent=impact_on_icr,
            impact_on_dsscr=impact_on_dsscr,
            risk_level=risk_level,
            description=description,
            recommendation=recommendation,
        )

    def simulate_revenue_drop(
        self, financials: Dict, severity: str = "moderate"
    ) -> ScenarioResult:
        """Simulate impact of revenue decline on profitability."""
        revenue = self._extract_revenue(financials)
        ebitda_margin = self._extract_ebitda_margin(financials)
        total_debt = self._extract_total_debt(financials)

        revenue_decline = self.params["revenue_drop"].get(severity, 20)
        stressed_revenue = revenue * (1 - revenue_decline / 100)
        stressed_ebitda = stressed_revenue * (ebitda_margin / 100)

        interest_cost = total_debt * (self._extract_avg_interest_rate(financials) / 100)
        stressed_icr = (
            stressed_ebitda / interest_cost if interest_cost > 0 else float("inf")
        )

        current_icr = self._extract_interest_coverage(financials)
        impact_on_dsscr = stressed_icr - current_icr

        if severity == "extreme":
            risk_level = "HIGH"
            description = f"Revenue drop of {revenue_decline}% reduces EBITDA to ₹{stressed_ebitda:.1f} Cr. ICR drops from {current_icr:.1f}x to {stressed_icr:.1f}x"
            recommendation = "Consider additional collateral or personal guarantee"
        elif severity == "severe":
            risk_level = "MEDIUM"
            description = f"Revenue drop of {revenue_decline}% reduces EBITDA to ₹{stressed_ebitda:.1f} Cr. ICR drops from {current_icr:.1f}x to {stressed_icr:.1f}x"
            recommendation = "Ensure adequate cash reserves and credit facilities"
        else:
            risk_level = "LOW"
            description = f"Revenue drop of {revenue_decline}% reduces EBITDA to ₹{stressed_ebitda:.1f} Cr. ICR drops from {current_icr:.1f}x to {stressed_icr:.1f}x"
            recommendation = "Monitor revenue trend and maintain operational efficiency"

        return ScenarioResult(
            scenario_name=f"Revenue Decline ({severity.title()})",
            scenario_type=ScenarioType.REVENUE_DROP.value,
            severity=severity,
            original_value=current_icr,
            stressed_value=stressed_icr,
            change_percent=((stressed_icr - current_icr) / current_icr * 100)
            if current_icr != float("inf")
            else 0,
            impact_on_dsscr=impact_on_dsscr,
            risk_level=risk_level,
            description=description,
            recommendation=recommendation,
        )

    def simulate_liquidity_stress(
        self, financials: Dict, severity: str = "moderate"
    ) -> ScenarioResult:
        """Simulate liquidity crunch (receivables not realized)."""
        current_ratio = self._extract_current_ratio(financials)
        current_assets = self._extract_current_assets(financials)

        liquidity_multiplier = self.params["liquidity_multiplier"].get(severity, 0.6)
        stressed_current_assets = current_assets * liquidity_multiplier

        current_liabilities = self._extract_current_liabilities(financials)
        stressed_current_ratio = (
            stressed_current_assets / current_liabilities
            if current_liabilities > 0
            else float("inf")
        )

        impact = stressed_current_ratio - current_ratio

        if severity == "extreme":
            risk_level = "HIGH"
            description = f"Receivables not realized ({int((1 - liquidity_multiplier) * 100)}% haircut). Current ratio drops from {current_ratio:.2f}x to {stressed_current_ratio:.2f}x"
            recommendation = "Tighten receivables management and maintain credit lines"
        elif severity == "severe":
            risk_level = "MEDIUM"
            description = f"Receivables not realized ({int((1 - liquidity_multiplier) * 100)}% haircut). Current ratio drops from {current_ratio:.2f}x to {stressed_current_ratio:.2f}x"
            recommendation = "Improve collections and monitor debtor days"
        else:
            risk_level = "LOW"
            description = f"Receivables not realized ({int((1 - liquidity_multiplier) * 100)}% haircut). Current ratio drops from {current_ratio:.2f}x to {stressed_current_ratio:.2f}x"
            recommendation = "Continue robust working capital management"

        return ScenarioResult(
            scenario_name=f"Liquidity Stress ({severity.title()})",
            scenario_type=ScenarioType.LIQUIDITY_STRESS.value,
            severity=severity,
            original_value=current_ratio,
            stressed_value=stressed_current_ratio,
            change_percent=(impact / current_ratio * 100)
            if current_ratio != float("inf")
            else 0,
            impact_on_dsscr=0,
            risk_level=risk_level,
            description=description,
            recommendation=recommendation,
        )

    def simulate_dscr_stress(
        self, financials: Dict, severity: str = "moderate"
    ) -> ScenarioResult:
        """Simulate DSCR stress (profitability decline with constant debt service)."""
        dsr = self._extract_debt_service(financials)
        ebitda = self._extract_ebitda(financials)
        current_dsscr = ebitda / dsr if dsr > 0 else float("inf")

        margin_compression = self.params["margin_compression"].get(severity, 5)
        revenue = self._extract_revenue(financials)
        stressed_ebitda = ebitda - (revenue * margin_compression / 100)
        stressed_dsscr = stressed_ebitda / dsr if dsr > 0 else float("inf")

        impact = stressed_dsscr - current_dsscr

        if severity == "extreme":
            risk_level = "HIGH"
            description = f"Margin compression of {margin_compression}% reduces EBITDA to ₹{stressed_ebitda:.1f} Cr. DSCR drops from {current_dsscr:.2f}x to {stressed_dsscr:.2f}x"
            recommendation = "Consider restructuring debt or reducing debt quantum"
        elif severity == "severe":
            risk_level = "MEDIUM"
            description = f"Margin compression of {margin_compression}% reduces EBITDA to ₹{stressed_ebitda:.1f} Cr. DSCR drops from {current_dsscr:.2f}x to {stressed_dsscr:.2f}x"
            recommendation = "Focus on cost optimization and revenue diversification"
        else:
            risk_level = "LOW"
            description = f"Margin compression of {margin_compression}% reduces EBITDA to ₹{stressed_ebitda:.1f} Cr. DSCR drops from {current_dsscr:.2f}x to {stressed_dsscr:.2f}x"
            recommendation = "Maintain operational efficiency and pricing discipline"

        return ScenarioResult(
            scenario_name=f"DSCR Stress ({severity.title()})",
            scenario_type=ScenarioType.DSCR_STRESS.value,
            severity=severity,
            original_value=current_dsscr,
            stressed_value=stressed_dsscr,
            change_percent=(impact / current_dsscr * 100)
            if current_dsscr != float("inf")
            else 0,
            impact_on_dsscr=impact,
            risk_level=risk_level,
            description=description,
            recommendation=recommendation,
        )

    def run_monte_carlo(
        self, financials: Dict, iterations: int = 1000
    ) -> List[MonteCarloResult]:
        """Run Monte Carlo simulation for key metrics."""
        results = []

        ebitda = self._extract_ebitda(financials)
        revenue = self._extract_revenue(financials)
        total_debt = self._extract_total_debt(financials)

        if ebitda and revenue:
            ebitda_results = self._simulate_metric(
                ebitda,
                volatility=0.15,
                iterations=iterations,
                metric_name="EBITDA",
            )
            results.append(ebitda_results)

        if total_debt and ebitda:
            icr_results = self._simulate_metric(
                ebitda / (total_debt * 0.1),
                volatility=0.2,
                iterations=iterations,
                metric_name="Interest Coverage Ratio",
            )
            results.append(icr_results)

        if revenue:
            rev_results = self._simulate_metric(
                revenue,
                volatility=0.1,
                iterations=iterations,
                metric_name="Revenue",
            )
            results.append(rev_results)

        return results

    def _simulate_metric(
        self, base_value: float, volatility: float, iterations: int, metric_name: str
    ) -> MonteCarloResult:
        """Run simulation for a single metric."""
        results = []

        for _ in range(iterations):
            change = random.gauss(0, volatility)
            value = base_value * (1 + change)
            results.append(max(0, value))

        results.sort()
        n = len(results)

        mean_val = sum(results) / n
        median_val = results[n // 2]
        std_dev = math.sqrt(sum((x - mean_val) ** 2 for x in results) / n)

        p5 = results[int(n * 0.05)]
        p25 = results[int(n * 0.25)]
        p75 = results[int(n * 0.75)]
        p95 = results[int(n * 0.95)]

        worst_case = results[0]
        best_case = results[-1]

        if metric_name == "Interest Coverage Ratio":
            prob_default = sum(1 for x in results if x < 1.0) / n
            prob_breach = sum(1 for x in results if x < 1.25) / n
        else:
            prob_default = sum(1 for x in results if x < base_value * 0.5) / n
            prob_breach = sum(1 for x in results if x < base_value * 0.75) / n

        return MonteCarloResult(
            metric_name=metric_name,
            iterations=iterations,
            mean=round(mean_val, 2),
            median=round(median_val, 2),
            std_dev=round(std_dev, 2),
            percentile_5=round(p5, 2),
            percentile_25=round(p25, 2),
            percentile_75=round(p75, 2),
            percentile_95=round(p95, 2),
            worst_case=round(worst_case, 2),
            best_case=round(best_case, 2),
            probability_of_default=round(prob_default * 100, 2),
            probability_of_breach=round(prob_breach * 100, 2),
        )

    def _calculate_overall_stress_score(self, scenarios: List[ScenarioResult]) -> float:
        """Calculate overall stress score from scenarios."""
        if not scenarios:
            return 0

        weights = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        total_weight = sum(weights.get(s.risk_level, 1) for s in scenarios)
        weighted_score = sum(weights.get(s.risk_level, 1) for s in scenarios)

        max_possible_score = total_weight * 3
        stress_score = (
            (weighted_score / max_possible_score * 100) if max_possible_score > 0 else 0
        )

        return round(stress_score, 1)

    def _get_risk_rating(self, stress_score: float) -> str:
        """Get risk rating from stress score."""
        if stress_score >= 70:
            return "CRITICAL"
        elif stress_score >= 50:
            return "HIGH"
        elif stress_score >= 30:
            return "MEDIUM"
        else:
            return "LOW"

    def _get_critical_points(self, scenarios: List[ScenarioResult]) -> List[str]:
        """Identify critical stress points."""
        critical = []
        for s in scenarios:
            if s.risk_level == "HIGH":
                critical.append(f"{s.scenario_name}: {s.description}")
        return critical

    def _generate_recommendations(self, scenarios: List[ScenarioResult]) -> List[str]:
        """Generate recommendations based on stress results."""
        recommendations = []
        seen = set()

        for s in scenarios:
            if s.recommendation not in seen:
                recommendations.append(s.recommendation)
                seen.add(s.recommendation)

        return recommendations

    def _extract_revenue(self, f: Dict) -> float:
        return float(f.get("revenue_crores") or f.get("revenue") or 0)

    def _extract_ebitda(self, f: Dict) -> float:
        return float(f.get("ebitda_crores") or f.get("ebitda") or 0)

    def _extract_ebitda_margin(self, f: Dict) -> float:
        rev = self._extract_revenue(f)
        ebitda = self._extract_ebitda(f)
        if rev > 0:
            return (ebitda / rev) * 100
        return float(f.get("ebitda_margin_percent") or f.get("ebitda_margin") or 15)

    def _extract_total_debt(self, f: Dict) -> float:
        return float(f.get("total_borrowings_crores") or f.get("total_debt") or 0)

    def _extract_avg_interest_rate(self, f: Dict) -> float:
        return float(f.get("avg_interest_rate") or f.get("interest_rate") or 10)

    def _extract_current_ratio(self, f: Dict) -> float:
        return float(f.get("current_ratio") or 1.5)

    def _extract_interest_coverage(self, f: Dict) -> float:
        return float(f.get("interest_coverage_ratio") or f.get("icr") or 3)

    def _extract_dsscr(self, f: Dict) -> float:
        return float(
            f.get("dscr_approximate")
            or f.get("dscr")
            or f.get("interest_coverage_ratio")
            or 3
        )

    def _extract_debt_service(self, f: Dict) -> float:
        debt = self._extract_total_debt(f)
        rate = self._extract_avg_interest_rate(f)
        if debt > 0:
            annual_interest = debt * (rate / 100)
            principal = debt / 10
            return annual_interest + principal
        return 0

    def _extract_current_assets(self, f: Dict) -> float:
        total_assets = float(f.get("total_assets_crores") or f.get("total_assets") or 0)
        return total_assets * 0.3

    def _extract_current_liabilities(self, f: Dict) -> float:
        total_assets = float(f.get("total_assets_crores") or f.get("total_assets") or 0)
        current_ratio = self._extract_current_ratio(f)
        if current_ratio > 0:
            return total_assets * 0.2 / current_ratio
        return total_assets * 0.2


class ScenarioDashboard:
    """Generate stress test visualization data."""

    @staticmethod
    def generate_scenario_comparison(scenarios: List[ScenarioResult]) -> dict:
        """Generate scenario comparison chart data."""
        labels = [s.scenario_name for s in scenarios]
        original = [s.original_value for s in scenarios]
        stressed = [s.stressed_value for s in scenarios]

        return {
            "labels": labels,
            "original": original,
            "stressed": stressed,
            "chart_type": "grouped_bar",
            "title": "Stress Scenario Impact",
        }

    @staticmethod
    def generate_monte_carlo_chart(mc_result: MonteCarloResult) -> dict:
        """Generate Monte Carlo distribution chart."""
        return {
            "metric": mc_result.metric_name,
            "mean": mc_result.mean,
            "percentile_5": mc_result.percentile_5,
            "percentile_95": mc_result.percentile_95,
            "worst_case": mc_result.worst_case,
            "best_case": mc_result.best_case,
            "prob_default": mc_result.probability_of_default,
        }

    @staticmethod
    def generate_stress_gauge(stress_score: float, risk_rating: str) -> dict:
        """Generate stress score gauge."""
        color_map = {
            "CRITICAL": "#C0392B",
            "HIGH": "#D68910",
            "MEDIUM": "#F4D03F",
            "LOW": "#1E8449",
        }

        return {
            "score": stress_score,
            "rating": risk_rating,
            "color": color_map.get(risk_rating, "#7f8c8d"),
        }


def run_stress_test(financials: Dict, company_name: str = "") -> dict:
    """Quick function to run stress tests and return serializable dict."""
    engine = StressTestEngine()
    report = engine.run_all_stress_tests(financials, company_name)

    return {
        "company_name": report.company_name,
        "current_dscr": report.current_dsscr,
        "current_interest_coverage": report.current_interest_coverage,
        "overall_stress_score": report.overall_stress_score,
        "risk_rating": report.risk_rating,
        "scenarios": [
            {
                "name": s.scenario_name,
                "severity": s.severity,
                "original": s.original_value,
                "stressed": s.stressed_value,
                "change_pct": s.change_percent,
                "risk_level": s.risk_level,
                "description": s.description,
                "recommendation": s.recommendation,
            }
            for s in report.scenarios
        ],
        "critical_points": report.critical_stress_points,
        "recommendations": report.recommendations,
    }
