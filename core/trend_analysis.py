"""
core/trend_analysis.py
Multi-Year Trend Analysis Module for Intelli-Credit.

Features:
1. Extract multi-year financial data from PDFs
2. Calculate CAGR (Compound Annual Growth Rate)
3. YoY growth tracking
4. Momentum scoring
5. Trend visualization data generation

Usage:
    from core.trend_analysis import TrendAnalyzer, TrendDashboard
    analyzer = TrendAnalyzer()
    trends = analyzer.analyze(multi_year_data)
"""

import json
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class TrendDirection(Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DETERIORATING = "deteriorating"
    VOLATILE = "volatile"


class MomentumScore(Enum):
    STRONG_POSITIVE = "strong_positive"
    MODERATE_POSITIVE = "moderate_positive"
    NEUTRAL = "neutral"
    MODERATE_NEGATIVE = "moderate_negative"
    STRONG_NEGATIVE = "strong_negative"


@dataclass
class YearlyMetric:
    """Single year financial metric."""

    year: str
    revenue_crores: Optional[float] = None
    ebitda_crores: Optional[float] = None
    pat_crores: Optional[float] = None
    net_worth_crores: Optional[float] = None
    total_debt_crores: Optional[float] = None
    debt_equity_ratio: Optional[float] = None
    current_ratio: Optional[float] = None
    ebitda_margin_percent: Optional[float] = None
    pat_margin_percent: Optional[float] = None
    roe_percent: Optional[float] = None
    debt_ebitda_ratio: Optional[float] = None
    interest_coverage_ratio: Optional[float] = None


@dataclass
class CAGRResult:
    """CAGR calculation result for a metric."""

    metric_name: str
    start_year: str
    end_year: str
    start_value: float
    end_value: float
    cagr_percent: float
    is_positive: bool
    assessment: str


@dataclass
class YoYGrowth:
    """Year-over-Year growth result."""

    metric_name: str
    from_year: str
    to_year: str
    from_value: float
    to_value: float
    growth_percent: float
    is_positive: bool
    trend: TrendDirection


@dataclass
class MomentumResult:
    """Momentum scoring result."""

    metric_name: str
    momentum_score: float
    momentum_label: MomentumScore
    recent_trend: TrendDirection
    volatility: float
    consecutive_growth_years: int
    assessment: str


@dataclass
class TrendAnalysis:
    """Complete trend analysis result."""

    company_name: str
    years_analyzed: List[str]
    yearly_data: List[YearlyMetric]
    cagr_results: List[CAGRResult]
    yoy_growth: List[YoYGrowth]
    momentum_results: List[MomentumResult]
    overall_momentum_score: float
    overall_trend: TrendDirection
    key_insights: List[str]
    risk_signals: List[str]


class TrendAnalyzer:
    """
    Multi-year trend analyzer for credit analysis.
    Extracts historical data and calculates growth metrics.
    """

    STANDARD_METRICS = [
        "revenue_crores",
        "ebitda_crores",
        "pat_crores",
        "net_worth_crores",
        "total_borrowings_crores",
        "debt_equity_ratio",
        "current_ratio",
        "ebitda_margin_percent",
        "pat_margin_percent",
        "return_on_equity_percent",
    ]

    def __init__(self):
        self.years = []
        self.yearly_data = []

    def extract_multi_year_data(
        self, pdf_data: dict, max_years: int = 5
    ) -> List[YearlyMetric]:
        """
        Extract financial data for multiple years from the PDF data.
        Tries to identify year-over-year data from various fields.
        """
        yearly_metrics = []

        yearly_revenue = pdf_data.get("yearly_revenue", [])
        yearly_ebitda = pdf_data.get("yearly_ebitda", [])
        yearly_pat = pdf_data.get("yearly_pat", [])
        yearly_networth = pdf_data.get("yearly_net_worth", [])
        yearly_debt = pdf_data.get("yearly_total_debt", [])

        all_years = set()
        for y in yearly_revenue:
            all_years.add(self._extract_year(y))
        for y in yearly_ebitda:
            all_years.add(self._extract_year(y))
        for y in yearly_pat:
            all_years.add(self._extract_year(y))

        sorted_years = sorted(all_years, reverse=True)[:max_years]

        for year in sorted_years:
            ym = YearlyMetric(year=str(year))

            rev_data = self._find_by_year(yearly_revenue, year)
            if rev_data:
                ym.revenue_crores = self._extract_value(rev_data)

            ebitda_data = self._find_by_year(yearly_ebitda, year)
            if ebitda_data:
                ym.ebitda_crores = self._extract_value(ebitda_data)

            pat_data = self._find_by_year(yearly_pat, year)
            if pat_data:
                ym.pat_crores = self._extract_value(pat_data)

            nw_data = self._find_by_year(yearly_networth, year)
            if nw_data:
                ym.net_worth_crores = self._extract_value(nw_data)

            debt_data = self._find_by_year(yearly_debt, year)
            if debt_data:
                ym.total_debt_crores = self._extract_value(debt_data)

            if ym.revenue_crores and ym.ebitda_crores:
                ym.ebitda_margin_percent = round(
                    (ym.ebitda_crores / ym.revenue_crores) * 100, 2
                )

            if ym.revenue_crores and ym.pat_crores:
                ym.pat_margin_percent = round(
                    (ym.pat_crores / ym.revenue_crores) * 100, 2
                )

            if ym.total_debt_crores and ym.net_worth_crores and ym.net_worth_crores > 0:
                ym.debt_equity_ratio = round(
                    ym.total_debt_crores / ym.net_worth_crores, 2
                )

            if ym.ebitda_crores and ym.total_debt_crores:
                ym.debt_ebitda_ratio = round(ym.total_debt_crores / ym.ebitda_crores, 2)

            yearly_metrics.append(ym)

        return yearly_metrics

    def _extract_year(self, value) -> Optional[int]:
        """Extract year from various formats."""
        if isinstance(value, (int, float)):
            year = int(value)
            if 2000 <= year <= 2030:
                return year
        if isinstance(value, str):
            years = re.findall(r"(20\d{2})", str(value))
            if years:
                return int(years[0])
        return None

    def _find_by_year(self, data: List, year: int) -> Optional[Any]:
        """Find data entry for specific year."""
        for item in data:
            if self._extract_year(item) == year:
                return item
        return None

    def _extract_value(self, data) -> Optional[float]:
        """Extract numeric value from data."""
        if isinstance(data, (int, float)):
            return float(data)
        if isinstance(data, dict):
            for key in ["value", "amount", "figures"]:
                if key in data:
                    return self._parse_number(data[key])
        if isinstance(data, str):
            return self._parse_number(data)
        return None

    def _parse_number(self, text: str) -> Optional[float]:
        """Parse number from string like '123.45 Cr' or '1,234'."""
        if text is None:
            return None
        text = (
            str(text)
            .replace(",", "")
            .replace("₹", "")
            .replace("cr", "")
            .replace("crore", "")
            .strip()
        )
        match = re.search(r"(-?\d+(?:\.\d+)?)", text)
        if match:
            return float(match.group(1))
        return None

    def calculate_cagr(
        self, yearly_metrics: List[YearlyMetric], metric_name: str, years_back: int = 3
    ) -> Optional[CAGRResult]:
        """Calculate CAGR for a specific metric."""
        if len(yearly_metrics) < 2:
            return None

        sorted_data = sorted(yearly_metrics, key=lambda x: x.year)
        start_data = sorted_data[-min(years_back + 1, len(sorted_data))]
        end_data = sorted_data[-1]

        start_value = getattr(start_data, metric_name, None)
        end_value = getattr(end_data, metric_name, None)

        if start_value is None or end_value is None or start_value <= 0:
            return None

        n_years = int(end_data.year) - int(start_data.year)
        if n_years <= 0:
            return None

        cagr = ((end_value / start_value) ** (1 / n_years) - 1) * 100

        if cagr > 15:
            assessment = "Strong growth"
        elif cagr > 5:
            assessment = "Moderate growth"
        elif cagr > 0:
            assessment = "Mild growth"
        elif cagr > -5:
            assessment = "Mild decline"
        else:
            assessment = "Significant decline"

        return CAGRResult(
            metric_name=metric_name,
            start_year=start_data.year,
            end_year=end_data.year,
            start_value=start_value,
            end_value=end_value,
            cagr_percent=round(cagr, 2),
            is_positive=cagr > 0,
            assessment=assessment,
        )

    def calculate_all_cagr(
        self, yearly_metrics: List[YearlyMetric], years_back: int = 3
    ) -> List[CAGRResult]:
        """Calculate CAGR for all standard metrics."""
        results = []
        for metric in self.STANDARD_METRICS:
            result = self.calculate_cagr(yearly_metrics, metric, years_back)
            if result:
                results.append(result)
        return results

    def calculate_yoy_growth(
        self, yearly_metrics: List[YearlyMetric], metric_name: str
    ) -> List[YoYGrowth]:
        """Calculate year-over-year growth for a metric."""
        growth_results = []
        sorted_data = sorted(yearly_metrics, key=lambda x: x.year)

        for i in range(1, len(sorted_data)):
            prev = sorted_data[i - 1]
            curr = sorted_data[i]

            prev_value = getattr(prev, metric_name, None)
            curr_value = getattr(curr, metric_name, None)

            if prev_value is None or curr_value is None or prev_value == 0:
                continue

            growth_pct = ((curr_value - prev_value) / prev_value) * 100

            if growth_pct > 5:
                trend = TrendDirection.IMPROVING
            elif growth_pct > -5:
                trend = TrendDirection.STABLE
            elif growth_pct > -15:
                trend = TrendDirection.DETERIORATING
            else:
                trend = TrendDirection.VOLATILE

            growth_results.append(
                YoYGrowth(
                    metric_name=metric_name,
                    from_year=prev.year,
                    to_year=curr.year,
                    from_value=prev_value,
                    to_value=curr_value,
                    growth_percent=round(growth_pct, 2),
                    is_positive=growth_pct > 0,
                    trend=trend,
                )
            )

        return growth_results

    def calculate_all_yoy(self, yearly_metrics: List[YearlyMetric]) -> List[YoYGrowth]:
        """Calculate YoY growth for all metrics."""
        results = []
        for metric in self.STANDARD_METRICS:
            results.extend(self.calculate_yoy_growth(yearly_metrics, metric))
        return results

    def calculate_momentum(
        self, yearly_metrics: List[YearlyMetric], metric_name: str
    ) -> Optional[MomentumResult]:
        """Calculate momentum score for a metric."""
        if len(yearly_metrics) < 2:
            return None

        sorted_data = sorted(yearly_metrics, key=lambda x: x.year)

        values = []
        for data in sorted_data:
            val = getattr(data, metric_name, None)
            if val is not None:
                values.append(val)

        if len(values) < 2:
            return None

        positive_growth_years = 0
        consecutive_growth = 0
        max_consecutive = 0
        improvements = 0
        declines = 0

        for i in range(1, len(values)):
            diff = values[i] - values[i - 1]
            if values[i - 1] != 0:
                pct_change = abs(diff / values[i - 1]) * 100
            else:
                pct_change = 0

            if diff > 0:
                positive_growth_years += 1
                consecutive_growth += 1
                max_consecutive = max(max_consecutive, consecutive_growth)
                improvements += pct_change
            else:
                consecutive_growth = 0
                declines += pct_change

        total_periods = len(values) - 1
        momentum_score = (improvements - declines) / (total_periods * 10)
        momentum_score = max(-100, min(100, momentum_score))

        avg_change = (
            sum(abs(values[i] - values[i - 1]) for i in range(1, len(values)))
            / total_periods
            if total_periods > 0
            else 0
        )
        avg_value = sum(values) / len(values) if values else 1
        volatility = (avg_change / avg_value) * 100 if avg_value != 0 else 0

        if momentum_score > 20:
            label = MomentumScore.STRONG_POSITIVE
            assessment = "Strong upward momentum"
        elif momentum_score > 5:
            label = MomentumScore.MODERATE_POSITIVE
            assessment = "Moderate upward momentum"
        elif momentum_score > -5:
            label = MomentumScore.NEUTRAL
            assessment = "Neutral momentum"
        elif momentum_score > -20:
            label = MomentumScore.MODERATE_NEGATIVE
            assessment = "Moderate downward momentum"
        else:
            label = MomentumScore.STRONG_NEGATIVE
            assessment = "Strong downward momentum"

        recent_values = values[-3:] if len(values) >= 3 else values
        if len(recent_values) >= 2:
            if (
                recent_values[-1]
                > recent_values[-2]
                > (recent_values[-3] if len(recent_values) > 2 else recent_values[-2])
            ):
                recent_trend = TrendDirection.IMPROVING
            elif (
                recent_values[-1]
                < recent_values[-2]
                < (recent_values[-3] if len(recent_values) > 2 else recent_values[-2])
            ):
                recent_trend = TrendDirection.DETERIORATING
            else:
                recent_trend = TrendDirection.STABLE
        else:
            recent_trend = TrendDirection.STABLE

        return MomentumResult(
            metric_name=metric_name,
            momentum_score=round(momentum_score, 2),
            momentum_label=label,
            recent_trend=recent_trend,
            volatility=round(volatility, 2),
            consecutive_growth_years=max_consecutive,
            assessment=assessment,
        )

    def calculate_all_momentum(
        self, yearly_metrics: List[YearlyMetric]
    ) -> List[MomentumResult]:
        """Calculate momentum for all metrics."""
        results = []
        for metric in self.STANDARD_METRICS:
            result = self.calculate_momentum(yearly_metrics, metric)
            if result:
                results.append(result)
        return results

    def analyze(
        self, company_name: str, yearly_metrics: List[YearlyMetric]
    ) -> TrendAnalysis:
        """Complete trend analysis."""
        cagr_results = self.calculate_all_cagr(yearly_metrics)
        yoy_growth = self.calculate_all_yoy(yearly_metrics)
        momentum_results = self.calculate_all_momentum(yearly_metrics)

        years = [ym.year for ym in sorted(yearly_metrics, key=lambda x: x.year)]

        overall_momentum = (
            sum(r.momentum_score for r in momentum_results) / len(momentum_results)
            if momentum_results
            else 0
        )

        if overall_momentum > 15:
            overall_trend = TrendDirection.IMPROVING
        elif overall_momentum > -15:
            overall_trend = TrendDirection.STABLE
        else:
            overall_trend = TrendDirection.DETERIORATING

        key_insights = []
        risk_signals = []

        for cagr in cagr_results:
            if "revenue" in cagr.metric_name and cagr.cagr_percent > 20:
                key_insights.append(
                    f"Revenue CAGR of {cagr.cagr_percent}% over {cagr.start_year}-{cagr.end_year} indicates strong topline growth"
                )
            elif "revenue" in cagr.metric_name and cagr.cagr_percent < 0:
                risk_signals.append(
                    f"Revenue declining at {cagr.cagr_percent}% CAGR - business contraction risk"
                )

            if "debt_equity_ratio" in cagr.metric_name and cagr.cagr_percent > 20:
                risk_signals.append(
                    f"Leverage increasing at {cagr.cagr_percent}% CAGR - rising debt burden"
                )
            elif "debt_equity_ratio" in cagr.metric_name and cagr.cagr_percent < 0:
                key_insights.append(
                    f"Leverage improving - debt/equity declining at {cagr.cagr_percent}% CAGR"
                )

            if "ebitda_margin" in cagr.metric_name and cagr.cagr_percent > 5:
                key_insights.append(
                    f"EBITDA margin expanding - operational efficiency improving"
                )
            elif "ebitda_margin" in cagr.metric_name and cagr.cagr_percent < -5:
                risk_signals.append(
                    f"EBITDA margin contracting - profitability pressure"
                )

        for momentum in momentum_results:
            if momentum.volatility > 50:
                risk_signals.append(
                    f"High volatility in {momentum.metric_name.replace('_', ' ')} - inconsistent performance"
                )

            if momentum.momentum_label == MomentumScore.STRONG_NEGATIVE:
                risk_signals.append(
                    f"Strong negative momentum in {momentum.metric_name.replace('_', ' ')}"
                )

        return TrendAnalysis(
            company_name=company_name,
            years_analyzed=years,
            yearly_data=yearly_metrics,
            cagr_results=cagr_results,
            yoy_growth=yoy_growth,
            momentum_results=momentum_results,
            overall_momentum_score=round(overall_momentum, 2),
            overall_trend=overall_trend,
            key_insights=key_insights,
            risk_signals=risk_signals,
        )


class TrendDashboard:
    """Generate trend visualization data for Streamlit."""

    @staticmethod
    def generate_revenue_chart(trend_analysis: TrendAnalysis) -> dict:
        """Generate revenue trend chart data."""
        years = trend_analysis.years_analyzed
        revenue = []
        ebitda = []
        pat = []

        for ym in sorted(trend_analysis.yearly_data, key=lambda x: x.year):
            revenue.append(ym.revenue_crores)
            ebitda.append(ym.ebitda_crores)
            pat.append(ym.pat_crores)

        return {
            "years": years,
            "revenue": revenue,
            "ebitda": ebitda,
            "pat": pat,
            "chart_type": "multi_line",
            "title": "Revenue, EBITDA & PAT Trend",
        }

    @staticmethod
    def generate_margin_chart(trend_analysis: TrendAnalysis) -> dict:
        """Generate margin trend chart data."""
        years = trend_analysis.years_analyzed
        ebitda_margin = []
        pat_margin = []

        for ym in sorted(trend_analysis.yearly_data, key=lambda x: x.year):
            ebitda_margin.append(ym.ebitda_margin_percent)
            pat_margin.append(ym.pat_margin_percent)

        return {
            "years": years,
            "ebitda_margin": ebitda_margin,
            "pat_margin": pat_margin,
            "chart_type": "dual_bar",
            "title": "Margin Trend (%)",
        }

    @staticmethod
    def generate_leverage_chart(trend_analysis: TrendAnalysis) -> dict:
        """Generate leverage trend chart data."""
        years = trend_analysis.years_analyzed
        de_ratio = []
        current_ratio = []

        for ym in sorted(trend_analysis.yearly_data, key=lambda x: x.year):
            de_ratio.append(ym.debt_equity_ratio)
            current_ratio.append(ym.current_ratio)

        return {
            "years": years,
            "debt_equity": de_ratio,
            "current_ratio": current_ratio,
            "chart_type": "combo",
            "title": "Leverage & Liquidity Trend",
        }

    @staticmethod
    def generate_cagr_bar(trend_analysis: TrendAnalysis) -> dict:
        """Generate CAGR comparison bar chart."""
        labels = []
        values = []

        for cagr in trend_analysis.cagr_results[:6]:
            labels.append(
                cagr.metric_name.replace("_crores", "")
                .replace("_percent", "%")
                .replace("_", " ")
                .title()
            )
            values.append(cagr.cagr_percent)

        return {
            "labels": labels,
            "values": values,
            "chart_type": "bar",
            "title": "CAGR Comparison (%)",
        }

    @staticmethod
    def generate_momentum_gauge(trend_analysis: TrendAnalysis) -> dict:
        """Generate overall momentum gauge."""
        score = trend_analysis.overall_momentum_score
        trend = trend_analysis.overall_trend

        color = (
            "#1E8449"
            if trend == TrendDirection.IMPROVING
            else "#D68910"
            if trend == TrendDirection.STABLE
            else "#C0392B"
        )

        return {
            "score": score,
            "trend": trend.value,
            "color": color,
            "title": "Overall Momentum Score",
        }


def analyze_company_trends(company_name: str, pdf_data: dict) -> dict:
    """
    Quick function to analyze company trends from PDF data.
    Returns a dict suitable for JSON serialization.
    """
    analyzer = TrendAnalyzer()
    yearly_data = analyzer.extract_multi_year_data(pdf_data)
    analysis = analyzer.analyze(company_name, yearly_data)

    return {
        "company_name": analysis.company_name,
        "years_analyzed": analysis.years_analyzed,
        "overall_momentum_score": analysis.overall_momentum_score,
        "overall_trend": analysis.overall_trend.value,
        "cagr_summary": [
            {
                "metric": c.metric_name,
                "cagr": c.cagr_percent,
                "assessment": c.assessment,
            }
            for c in analysis.cagr_results
        ],
        "key_insights": analysis.key_insights,
        "risk_signals": analysis.risk_signals,
        "yearly_summary": [
            {
                "year": ym.year,
                "revenue": ym.revenue_crores,
                "ebitda": ym.ebitda_crores,
                "pat": ym.pat_crores,
                "debt_equity": ym.debt_equity_ratio,
            }
            for ym in analysis.yearly_data
        ],
    }
