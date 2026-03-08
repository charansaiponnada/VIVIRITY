"""
core/risk_engine.py
-------------------
Advanced Credit Risk Intelligence Engine.

Implements:
  1. Research Signal Confidence Engine — source counting + confidence scoring
  2. Temporal Risk Adjustment — event age decay
  3. Dynamic Risk Penalty Engine — severity × confidence × temporal
  4. Source Transparency Layer — traceable source references
  5. Corporate Risk Timeline — chronological event extraction
  6. Fraud Signal Detector — pattern-based anomaly detection
"""

import re
from datetime import datetime
from dataclasses import dataclass, field, asdict


CURRENT_YEAR = datetime.now().year


# ═══════════════════════════════════════════════════════════════════════════ #
# Data Models
# ═══════════════════════════════════════════════════════════════════════════ #

@dataclass
class RiskSignal:
    """A single detected risk signal with full transparency metadata."""
    signal_type: str
    category: str              # litigation / regulatory / fraud / promoter / financial / sector
    description: str
    source: str                # e.g. "NCLT Database", "SEBI Orders", "CIBIL Report"
    source_url: str = ""
    sources_found: int = 1
    confidence: str = "LOW"    # HIGH / MEDIUM / LOW
    severity: str = "MEDIUM"   # CRITICAL / HIGH / MEDIUM / LOW
    event_year: int | None = None
    base_penalty: float = 0.0
    confidence_factor: float = 1.0
    temporal_factor: float = 1.0
    adjusted_penalty: float = 0.0
    reference_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TimelineEvent:
    """A chronological corporate event for the risk timeline."""
    year: int
    event: str
    category: str   # restructuring / regulatory / financial / promoter / litigation / positive
    impact: str     # positive / negative / neutral
    source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FraudSignal:
    """A detected fraud/anomaly signal."""
    signal_type: str
    severity: str       # CRITICAL / HIGH / MEDIUM / LOW
    description: str
    evidence: str = ""
    metric_value: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CreditLimitResult:
    """Output from credit limit optimization."""
    requested_amount: float
    approved_limit: float
    interest_rate: float | None
    debt_service_capacity: float
    sector_adjustment: float
    collateral_coverage: float
    reason: str
    breakdown: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DivergenceReport:
    """Model divergence explanation."""
    rule_decision: str
    ml_decision: str
    rule_score: float
    ml_score: float
    blended_score: float
    divergence_points: float
    severity: str       # NONE / MODERATE / HIGH
    explanation: str
    action: str
    factors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════ #
# 1. Confidence Scoring
# ═══════════════════════════════════════════════════════════════════════════ #

def compute_confidence(sources_found: int) -> tuple[str, float]:
    """
    Determine confidence level and penalty multiplier based on source count.
    Returns (confidence_label, confidence_factor).
    """
    if sources_found >= 3:
        return "HIGH", 1.0
    elif sources_found == 2:
        return "MEDIUM", 0.7
    else:
        return "LOW", 0.4


# ═══════════════════════════════════════════════════════════════════════════ #
# 2. Temporal Adjustment
# ═══════════════════════════════════════════════════════════════════════════ #

def compute_temporal_factor(event_year: int | None) -> float:
    """
    Compute temporal decay factor based on event age.
    >3 years → 25%, 1-3 years → 50%, <1 year → 100%.
    """
    if event_year is None:
        return 1.0  # Unknown age → assume recent

    age = CURRENT_YEAR - event_year
    if age > 3:
        return 0.25
    elif age >= 1:
        return 0.50
    else:
        return 1.0


# ═══════════════════════════════════════════════════════════════════════════ #
# 3. Dynamic Penalty Calculation
# ═══════════════════════════════════════════════════════════════════════════ #

def compute_dynamic_penalty(base_penalty: float, severity: str,
                            confidence: str, confidence_factor: float,
                            temporal_factor: float) -> float:
    """
    Dynamic penalty = base × severity_multiplier × confidence_factor × temporal_factor.
    """
    severity_mult = {
        "CRITICAL": 1.5,
        "HIGH": 1.0,
        "MEDIUM": 0.7,
        "LOW": 0.4,
    }.get(severity, 1.0)

    adjusted = base_penalty * severity_mult * confidence_factor * temporal_factor
    return round(adjusted, 2)


def build_risk_signal(signal_type: str, category: str, description: str,
                      source: str, base_penalty: float,
                      severity: str = "MEDIUM",
                      sources_found: int = 1,
                      event_year: int | None = None,
                      source_url: str = "",
                      reference_text: str = "") -> RiskSignal:
    """Factory: build a fully computed RiskSignal with confidence + temporal adjustments."""
    confidence, conf_factor = compute_confidence(sources_found)
    temp_factor = compute_temporal_factor(event_year)
    adjusted = compute_dynamic_penalty(base_penalty, severity, confidence, conf_factor, temp_factor)

    return RiskSignal(
        signal_type=signal_type,
        category=category,
        description=description,
        source=source,
        source_url=source_url,
        sources_found=sources_found,
        confidence=confidence,
        severity=severity,
        event_year=event_year,
        base_penalty=base_penalty,
        confidence_factor=conf_factor,
        temporal_factor=temp_factor,
        adjusted_penalty=adjusted,
        reference_text=reference_text,
    )


# ═══════════════════════════════════════════════════════════════════════════ #
# 5. Corporate Risk Timeline
# ═══════════════════════════════════════════════════════════════════════════ #

_YEAR_PATTERN = re.compile(r'\b(20[0-2]\d)\b')

def extract_timeline(research: dict, financials: dict = None) -> list[TimelineEvent]:
    """
    Build a chronological risk timeline from research + financial data.
    Scans text fields for year mentions and categorizes events.
    """
    events: list[TimelineEvent] = []
    seen = set()

    def _add(year: int, event: str, category: str, impact: str, source: str = ""):
        key = (year, event[:40])
        if key not in seen:
            seen.add(key)
            events.append(TimelineEvent(year=year, event=event, category=category, impact=impact, source=source))

    # Scan research domains for events with years
    _event_rules = [
        ("legal_disputes", "nclt_proceedings", "NCLT proceedings initiated", "litigation", "negative"),
        ("legal_disputes", "ibc_cirp", "IBC/CIRP insolvency proceedings", "litigation", "negative"),
        ("legal_disputes", "drt_cases", "DRT debt recovery proceedings", "litigation", "negative"),
        ("regulatory", "sebi_actions", "SEBI enforcement action", "regulatory", "negative"),
        ("regulatory", "rbi_issues", "RBI regulatory direction", "regulatory", "negative"),
        ("promoter_background", "criminal_cases", "Criminal cases against promoter", "promoter", "negative"),
        ("promoter_background", "wilful_defaulter", "Promoter flagged as wilful defaulter", "promoter", "negative"),
        ("mca_signals", "director_disqualified", "Director disqualified by MCA", "regulatory", "negative"),
    ]

    for domain, field_key, label, category, impact in _event_rules:
        domain_data = research.get(domain, {})
        if domain_data.get(field_key):
            summary = domain_data.get("summary", "")
            years = _YEAR_PATTERN.findall(summary)
            if years:
                for y in years:
                    _add(int(y), label, category, impact, source=domain)
            else:
                _add(CURRENT_YEAR, label, category, impact, source=domain)

    # Scan narrative text for year-event pairs
    for domain_key in ["company_news", "sector_headwinds"]:
        domain_data = research.get(domain_key, {})
        summary = domain_data.get("summary", "")
        positive_signals = domain_data.get("positive_signals", [])
        risk_signals = domain_data.get("risk_signals", [])

        for sig in positive_signals:
            years = _YEAR_PATTERN.findall(str(sig))
            for y in years:
                _add(int(y), str(sig)[:80], "financial", "positive", source=domain_key)

        for sig in risk_signals:
            years = _YEAR_PATTERN.findall(str(sig))
            for y in years:
                _add(int(y), str(sig)[:80], "financial", "negative", source=domain_key)

    # Add external rating as a positive event
    ext_rating = research.get("company_news", {}).get("external_credit_rating")
    if ext_rating:
        _add(CURRENT_YEAR, f"External credit rating: {ext_rating}", "financial", "positive", source="company_news")

    # Financial milestones from financials
    if financials:
        rev = financials.get("revenue_crores")
        if rev:
            _add(CURRENT_YEAR, f"Revenue: ₹{rev} Cr (latest reported)", "financial", "neutral", source="annual_report")

    events.sort(key=lambda e: e.year)
    return events


# ═══════════════════════════════════════════════════════════════════════════ #
# 6. Fraud Signal Detection
# ═══════════════════════════════════════════════════════════════════════════ #

def detect_fraud_signals(financials: dict, cross_ref: dict = None,
                          research: dict = None) -> list[FraudSignal]:
    """
    Detect suspicious financial patterns.
    Checks revenue vs cash flow divergence, GST mismatches, related-party,
    auditor issues, promoter pledge.
    """
    signals: list[FraudSignal] = []

    # --- Revenue growth + declining cash flow ---
    rev = _safe_float(financials.get("revenue_crores"))
    rev_growth = _safe_float(financials.get("revenue_growth_percent"))
    pat = _safe_float(financials.get("profit_after_tax_crores"))

    if rev_growth and rev_growth > 10 and pat is not None and pat < 0:
        signals.append(FraudSignal(
            signal_type="REVENUE_CASHFLOW_DIVERGENCE",
            severity="HIGH",
            description="Revenue growing but PAT is negative — potential revenue inflation",
            evidence=f"Revenue growth {rev_growth:.1f}% but PAT ₹{pat:.0f} Cr (negative)",
            metric_value=f"{rev_growth:.1f}% growth, ₹{pat:.0f} Cr PAT",
        ))

    # --- GST revenue mismatch (from cross-ref) ---
    if cross_ref:
        for flag in cross_ref.get("flags", []):
            ftype = flag.get("type", "")
            if ftype in ("REVENUE_MISMATCH", "FAKE_ITC_RISK", "CIRCULAR_TRADING"):
                signals.append(FraudSignal(
                    signal_type=f"GST_{ftype}",
                    severity=flag.get("severity", "MEDIUM"),
                    description=flag.get("description", ftype),
                    evidence=flag.get("description", ""),
                ))

    # --- Related-party transactions ---
    rpt = _safe_float(financials.get("related_party_transactions_crores"))
    if rpt and rev and rev > 0 and rpt / rev > 0.20:
        pct = rpt / rev * 100
        signals.append(FraudSignal(
            signal_type="RELATED_PARTY_HIGH",
            severity="HIGH" if pct > 40 else "MEDIUM",
            description=f"Related-party transactions are {pct:.0f}% of revenue — unusually high",
            evidence=f"₹{rpt:.0f} Cr RPT on ₹{rev:.0f} Cr revenue",
            metric_value=f"{pct:.0f}%",
        ))

    # --- Auditor resignation / qualified opinion ---
    red_flags = financials.get("red_flags", {})
    if red_flags.get("audit_qualified"):
        signals.append(FraudSignal(
            signal_type="AUDITOR_QUALIFIED",
            severity="HIGH",
            description="Auditor issued qualified opinion — accounting integrity concern",
            evidence="Qualified audit report detected in annual report",
        ))
    if red_flags.get("auditor_resigned"):
        signals.append(FraudSignal(
            signal_type="AUDITOR_RESIGNATION",
            severity="CRITICAL",
            description="Auditor resigned — serious governance red flag",
            evidence="Auditor resignation detected",
        ))

    # --- Promoter share pledge (from research) ---
    if research:
        promoter = research.get("promoter_background", {})
        promoter_summary = (promoter.get("summary", "") or "").lower()
        if "pledge" in promoter_summary:
            signals.append(FraudSignal(
                signal_type="PROMOTER_PLEDGE",
                severity="MEDIUM",
                description="Promoter share pledge detected — potential liquidity stress signal",
                evidence="Pledge mention found in promoter background research",
            ))

    # --- Going concern ---
    if red_flags.get("going_concern_issue"):
        signals.append(FraudSignal(
            signal_type="GOING_CONCERN",
            severity="CRITICAL",
            description="Going concern doubt raised by auditor — existence risk",
            evidence="Going concern qualification detected",
        ))

    # Compute overall fraud risk level
    return signals


def compute_fraud_risk_level(signals: list[FraudSignal]) -> str:
    if any(s.severity == "CRITICAL" for s in signals):
        return "CRITICAL"
    elif any(s.severity == "HIGH" for s in signals):
        return "HIGH"
    elif len(signals) >= 3:
        return "HIGH"
    elif len(signals) >= 1:
        return "MEDIUM"
    return "LOW"


# ═══════════════════════════════════════════════════════════════════════════ #
# 7. Credit Limit Optimizer
# ═══════════════════════════════════════════════════════════════════════════ #

def optimize_credit_limit(financials: dict, scoring: dict,
                           requested_amount: float = 0,
                           sector: str = "") -> CreditLimitResult:
    """
    Compute optimized credit limit factoring in:
    - Debt service capacity
    - Sector risk adjustment
    - Collateral coverage
    """
    rev = _safe_float(financials.get("revenue_crores")) or 0
    nw = _safe_float(financials.get("net_worth_crores")) or 0
    ebitda = _safe_float(financials.get("ebitda_crores")) or 0
    total_debt = _safe_float(financials.get("total_borrowings_crores")) or 0
    fixed_assets = _safe_float(financials.get("fixed_assets_crores")) or _safe_float(financials.get("total_assets_crores")) or 0
    finance_cost = _safe_float(financials.get("finance_cost_crores")) or 0

    final_score = scoring.get("recommendation", {}).get("final_score", scoring.get("risk_score", {}).get("final_score", 50))
    rating = scoring.get("recommendation", {}).get("rating", "BBB")

    breakdown = []

    # Debt service capacity: (EBITDA - existing finance cost) × 3 years
    dsc = max((ebitda - finance_cost) * 3, 0) if ebitda > 0 else 0
    breakdown.append(f"Debt service capacity: (EBITDA ₹{ebitda:.0f} - Finance Cost ₹{finance_cost:.0f}) × 3 = ₹{dsc:.0f} Cr")

    # Capital adequacy: 5% of net worth
    nw_limit = nw * 0.05 if nw > 0 else 0
    breakdown.append(f"Capital adequacy (5% NW): ₹{nw_limit:.0f} Cr")

    # Revenue-based: 1.5% of revenue
    rev_limit = rev * 0.015 if rev > 0 else 0
    breakdown.append(f"Revenue-based (1.5%): ₹{rev_limit:.0f} Cr")

    # Raw capacity
    candidates = [c for c in [dsc, nw_limit, rev_limit] if c > 0]
    raw_capacity = min(candidates) if candidates else 50

    # Sector adjustment
    stressed_sectors = {"real estate", "infrastructure", "nbfc / financial services", "textile"}
    sector_lower = sector.lower() if sector else ""
    sector_adj = 0.85 if sector_lower in stressed_sectors else 1.0
    breakdown.append(f"Sector adjustment: {'0.85x (stressed)' if sector_adj < 1 else '1.0x (neutral)'}")

    # Collateral coverage
    collateral_coverage = (fixed_assets / max(raw_capacity, 1)) if fixed_assets > 0 else 0
    breakdown.append(f"Collateral coverage ratio: {collateral_coverage:.2f}x")

    # Score-based haircut
    if final_score >= 75:
        score_mult = 1.0
    elif final_score >= 60:
        score_mult = 0.80
    elif final_score >= 50:
        score_mult = 0.60
    else:
        score_mult = 0.0
    breakdown.append(f"Score multiplier ({final_score:.0f}/100): {score_mult:.0%}")

    approved = raw_capacity * sector_adj * score_mult
    approved = max(round(approved, 0), 0)
    approved = min(approved, 2000)  # Hard cap

    # Interest rate
    rate_map = {"AAA": 11.0, "AA": 11.5, "A": 12.5, "BBB": 13.0, "BB": 14.0, "B": 15.5}
    rate = rate_map.get(rating)

    reason_parts = []
    if dsc > 0:
        reason_parts.append(f"Debt service capacity supports ₹{dsc:.0f} Cr")
    if sector_adj < 1:
        reason_parts.append("Sector risk adjustment applied")
    if collateral_coverage > 0:
        reason_parts.append(f"Collateral coverage ratio: {collateral_coverage:.1f}x")

    return CreditLimitResult(
        requested_amount=requested_amount,
        approved_limit=approved,
        interest_rate=rate,
        debt_service_capacity=round(dsc, 0),
        sector_adjustment=sector_adj,
        collateral_coverage=round(collateral_coverage, 2),
        reason="; ".join(reason_parts) if reason_parts else "Based on financial capacity analysis",
        breakdown=breakdown,
    )


# ═══════════════════════════════════════════════════════════════════════════ #
# 3. Model Divergence Detection
# ═══════════════════════════════════════════════════════════════════════════ #

def analyze_divergence(rule_score: float, rule_decision: str,
                       ml_score: float, ml_decision: str,
                       blended_score: float,
                       financials: dict = None,
                       research: dict = None) -> DivergenceReport:
    """
    Detect and explain divergence between rule-based and ML model decisions.
    """
    divergence = abs(rule_score - ml_score)
    factors = []

    if divergence <= 10:
        severity = "NONE"
        explanation = "Rule-based and ML models are aligned."
        action = "No additional review needed."
    elif divergence <= 20:
        severity = "MODERATE"
        explanation = f"Moderate divergence of {divergence:.1f} points between models."
        action = "Document rationale for discrepancy in credit file."
    else:
        severity = "HIGH"
        explanation = f"Significant divergence of {divergence:.1f} points detected."
        action = "Human credit review recommended before final decision."

    # Explain WHY divergence occurred
    if rule_decision != ml_decision:
        if ml_score > rule_score:
            factors.append("ML model sees stronger financial indicators than rule-based assessment")
            if financials:
                icr = _safe_float(financials.get("interest_coverage_ratio"))
                if icr and icr > 5:
                    factors.append(f"Strong interest coverage ({icr:.1f}x) boosting ML confidence")
                dscr = _safe_float(financials.get("dscr_approximate"))
                if dscr and dscr > 2:
                    factors.append(f"Healthy DSCR ({dscr:.1f}x) — strong debt service capacity")
            if research:
                lit = research.get("litigation", research.get("legal_disputes", {}))
                if lit.get("litigation_risk") in ("Medium", "High"):
                    factors.append("Research signals detected litigation risks pulling down rule-based score")
                reg = research.get("regulatory", {})
                if reg.get("sebi_actions") or reg.get("rbi_issues"):
                    factors.append("Regulatory actions penalized rule-based score but not directly in ML features")
        else:
            factors.append("Rule-based assessment more optimistic than ML model")
            if financials:
                de = _safe_float(financials.get("debt_equity_ratio"))
                if de and de > 2:
                    factors.append(f"High leverage ({de:.1f}x D/E) heavily penalized by ML coefficients")
                ebitda_m = _safe_float(financials.get("ebitda_margin_percent"))
                if ebitda_m and ebitda_m < 10:
                    factors.append(f"Low EBITDA margin ({ebitda_m:.1f}%) reduces ML lending probability")

    if not factors:
        factors.append("Models largely agree on risk assessment")

    return DivergenceReport(
        rule_decision=rule_decision,
        ml_decision=ml_decision,
        rule_score=round(rule_score, 1),
        ml_score=round(ml_score, 1),
        blended_score=round(blended_score, 1),
        divergence_points=round(divergence, 1),
        severity=severity,
        explanation=explanation,
        action=action,
        factors=factors,
    )


# ═══════════════════════════════════════════════════════════════════════════ #
# Helpers
# ═══════════════════════════════════════════════════════════════════════════ #

def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").replace("₹", "").strip())
    except (ValueError, TypeError):
        return None
