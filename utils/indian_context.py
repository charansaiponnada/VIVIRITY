"""
utils/indian_context.py
-----------------------
Entity-type detection and sector-aware configuration for Indian financial institutions.

Supports 4 entity types:
  - bank       : Scheduled Commercial Banks (SBI, YES Bank, HDFC Bank, etc.)
  - nbfc       : Non-Banking Financial Companies (Bajaj Finance, Muthoot, etc.)
  - insurance  : Insurance companies (LIC, HDFC Life, ICICI Lombard, etc.)
  - corporate  : All other corporates (default)

Each entity type has:
  - Sector-appropriate KPIs and extraction fields
  - Dashboard gauge configurations
  - Scoring anchor thresholds
  - Interest rate ranges
"""

import re
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════ #
# Entity Type Detection
# ═══════════════════════════════════════════════════════════════════════════ #

# Keywords in company name → entity type (checked in order)
_BANK_KEYWORDS = [
    "bank", "banking corporation", "banking company",
]
_NBFC_KEYWORDS = [
    "nbfc", "finance ltd", "finance limited", "financial services",
    "capital ltd", "capital limited", "credit ltd", "credit limited",
    "housing finance", "micro finance", "microfinance",
    "finserv", "fincorp",
]
_INSURANCE_KEYWORDS = [
    "insurance", "life insurance", "general insurance",
    "assurance", "re-insurance", "reinsurance",
]

# NIC-2008 code 65 = Financial service activities (except insurance and pension funding)
# CIN format: L/U + 5-digit NIC code + 2-letter state + 4-digit year + PLC/NPL + 6 digits
_CIN_FINANCIAL_PATTERN = re.compile(r'^[LU]65\d{2}', re.IGNORECASE)
_CIN_INSURANCE_PATTERN = re.compile(r'^[LU]66\d{2}', re.IGNORECASE)

# Sector dropdown values that force entity type
_SECTOR_OVERRIDES = {
    "Banking":                   "bank",
    "NBFC / Financial Services": "nbfc",
    "Insurance":                 "insurance",
}


def detect_entity_type(
    company_name: str = "",
    cin: str = "",
    sector_input: str = "",
) -> str:
    """
    Detect entity type from company name, CIN code, and sector dropdown.

    Priority:
      1. Sector dropdown override (explicit user choice)
      2. Company name keyword matching
      3. CIN NIC code (65 = financial, 66 = insurance)
      4. Default → "corporate"

    Returns one of: "bank", "nbfc", "insurance", "corporate"
    """
    # 1. Sector dropdown override
    if sector_input in _SECTOR_OVERRIDES:
        return _SECTOR_OVERRIDES[sector_input]

    name_lower = (company_name or "").lower().strip()

    # 2. Company name keywords (bank checked first — "Yes Bank" should not match NBFC)
    for kw in _BANK_KEYWORDS:
        if kw in name_lower:
            return "bank"
    for kw in _INSURANCE_KEYWORDS:
        if kw in name_lower:
            return "insurance"
    for kw in _NBFC_KEYWORDS:
        if kw in name_lower:
            return "nbfc"

    # 3. CIN code
    cin_str = (cin or "").strip()
    if cin_str:
        if _CIN_INSURANCE_PATTERN.match(cin_str):
            return "insurance"
        if _CIN_FINANCIAL_PATTERN.match(cin_str):
            # CIN says financial — but could be bank or NBFC
            # If name contains "bank" we already caught it above → default to NBFC
            return "nbfc"

    # 4. Default
    return "corporate"


# ═══════════════════════════════════════════════════════════════════════════ #
# Entity Configuration
# ═══════════════════════════════════════════════════════════════════════════ #

ENTITY_CONFIGS = {
    # ── Bank ──────────────────────────────────────────────────────────── #
    "bank": {
        "label": "Scheduled Commercial Bank",
        "revenue_label": "Total Income",
        "profit_label": "PAT",
        "kpis": [
            "net_interest_margin_percent",
            "gross_npa_percent",
            "net_npa_percent",
            "capital_adequacy_ratio_percent",
            "provision_coverage_ratio_percent",
            "cost_to_income_ratio_percent",
            "casa_ratio_percent",
            "return_on_assets_percent",
            "return_on_equity_percent",
        ],
        "skip_metrics": [
            "ebitda_crores", "ebitda_margin_percent",
            "interest_coverage_ratio", "current_ratio",
            "debt_equity_ratio", "dscr_approximate",
        ],
        "rate_table": {
            "AAA": 9.0, "AA": 9.25, "A": 9.5,
            "BBB": 10.0, "BB": 10.5, "B": 11.5,
            "CCC": None, "D": None,
        },
        "loan_nw_ratio": 0.10,       # 10% of net worth for banks
        "loan_assets_ratio": 0.005,   # 0.5% of total assets
        "loan_max_cap_cr": 5000,      # Large institutions
        "exposure_label": "Institutional / Corporate Exposure",
    },

    # ── NBFC ──────────────────────────────────────────────────────────── #
    "nbfc": {
        "label": "Non-Banking Financial Company",
        "revenue_label": "Total Income",
        "profit_label": "PAT",
        "kpis": [
            "net_interest_margin_percent",
            "gross_npa_percent",
            "net_npa_percent",
            "capital_adequacy_ratio_percent",
            "debt_equity_ratio",
            "interest_coverage_ratio",
            "return_on_assets_percent",
            "return_on_equity_percent",
        ],
        "skip_metrics": [
            "ebitda_crores", "ebitda_margin_percent",
            "current_ratio", "dscr_approximate",
        ],
        "rate_table": {
            "AAA": 10.0, "AA": 10.5, "A": 11.0,
            "BBB": 11.5, "BB": 12.0, "B": 13.0,
            "CCC": None, "D": None,
        },
        "loan_nw_ratio": 0.05,
        "loan_assets_ratio": 0.005,
        "loan_max_cap_cr": 2000,
        "exposure_label": "NBFC Lending / On-lending Facility",
    },

    # ── Insurance ─────────────────────────────────────────────────────── #
    "insurance": {
        "label": "Insurance Company",
        "revenue_label": "Gross Written Premium",
        "profit_label": "PAT",
        "kpis": [
            "solvency_ratio",
            "claims_ratio_percent",
            "combined_ratio_percent",
            "expense_ratio_percent",
            "investment_yield_percent",
            "return_on_equity_percent",
        ],
        "skip_metrics": [
            "ebitda_crores", "ebitda_margin_percent",
            "interest_coverage_ratio", "current_ratio",
            "debt_equity_ratio", "dscr_approximate",
        ],
        "rate_table": {
            "AAA": 9.5, "AA": 9.75, "A": 10.0,
            "BBB": 10.5, "BB": 11.0, "B": 12.0,
            "CCC": None, "D": None,
        },
        "loan_nw_ratio": 0.08,
        "loan_assets_ratio": 0.003,
        "loan_max_cap_cr": 3000,
        "exposure_label": "Insurance Company Exposure",
    },

    # ── Corporate (default — unchanged from existing behavior) ────────── #
    "corporate": {
        "label": "Corporate Borrower",
        "revenue_label": "Revenue",
        "profit_label": "PAT",
        "kpis": [
            "interest_coverage_ratio",
            "debt_equity_ratio",
            "current_ratio",
            "ebitda_margin_percent",
            "return_on_equity_percent",
            "dscr_approximate",
        ],
        "skip_metrics": [],
        "rate_table": {
            "AAA": 11.0, "AA": 11.5, "A": 12.5,
            "BBB": 13.0, "BB": 14.0, "B": 15.5,
            "CCC": None, "D": None,
        },
        "loan_nw_ratio": 0.05,
        "loan_assets_ratio": None,
        "loan_max_cap_cr": 2000,
        "exposure_label": "Corporate Lending",
    },
}


# ═══════════════════════════════════════════════════════════════════════════ #
# Dashboard Gauge Configurations
# ═══════════════════════════════════════════════════════════════════════════ #

def get_ratio_gauges(entity_type: str) -> list[dict]:
    """
    Return list of gauge configs for the Financial Health dashboard.
    Each dict: {name, key, lo, hi, suffix, tip, thresholds}
    thresholds: {green_min, orange_min} — values above green are GREEN, above orange are ORANGE, else RED.
    For inverted metrics (lower=better): set inverted=True.
    """
    if entity_type == "bank":
        return [
            {"name": "Net Interest Margin", "key": "net_interest_margin_percent", "lo": 0, "hi": 6,
             "suffix": "%", "tip": "NII / Avg Interest-Earning Assets",
             "green_min": 3.0, "orange_min": 2.0, "inverted": False},
            {"name": "Gross NPA", "key": "gross_npa_percent", "lo": 0, "hi": 15,
             "suffix": "%", "tip": "Asset quality — lower is better",
             "green_min": 3.0, "orange_min": 6.0, "inverted": True},
            {"name": "Net NPA", "key": "net_npa_percent", "lo": 0, "hi": 10,
             "suffix": "%", "tip": "Net non-performing assets",
             "green_min": 1.5, "orange_min": 3.0, "inverted": True},
            {"name": "Capital Adequacy (CRAR)", "key": "capital_adequacy_ratio_percent", "lo": 0, "hi": 25,
             "suffix": "%", "tip": "RBI minimum: 9% for banks",
             "green_min": 15.0, "orange_min": 11.5, "inverted": False},
            {"name": "Provision Coverage", "key": "provision_coverage_ratio_percent", "lo": 0, "hi": 100,
             "suffix": "%", "tip": "Provisions / Gross NPAs",
             "green_min": 70.0, "orange_min": 50.0, "inverted": False},
            {"name": "Cost-to-Income", "key": "cost_to_income_ratio_percent", "lo": 0, "hi": 80,
             "suffix": "%", "tip": "Operating efficiency — lower is better",
             "green_min": 45.0, "orange_min": 55.0, "inverted": True},
        ]

    if entity_type == "nbfc":
        return [
            {"name": "Net Interest Margin", "key": "net_interest_margin_percent", "lo": 0, "hi": 10,
             "suffix": "%", "tip": "NII / Avg Assets",
             "green_min": 3.5, "orange_min": 2.0, "inverted": False},
            {"name": "Gross NPA", "key": "gross_npa_percent", "lo": 0, "hi": 15,
             "suffix": "%", "tip": "Asset quality — lower is better",
             "green_min": 3.0, "orange_min": 6.0, "inverted": True},
            {"name": "Capital Adequacy", "key": "capital_adequacy_ratio_percent", "lo": 0, "hi": 30,
             "suffix": "%", "tip": "RBI minimum: 15% for NBFCs",
             "green_min": 18.0, "orange_min": 15.0, "inverted": False},
            {"name": "Debt/Equity", "key": "debt_equity_ratio", "lo": 0, "hi": 10,
             "suffix": "x", "tip": "RBI max: 7x for NBFCs",
             "green_min": 4.0, "orange_min": 7.0, "inverted": True},
            {"name": "ROA", "key": "return_on_assets_percent", "lo": 0, "hi": 5,
             "suffix": "%", "tip": "Return on Assets",
             "green_min": 2.0, "orange_min": 1.0, "inverted": False},
            {"name": "ROE", "key": "return_on_equity_percent", "lo": 0, "hi": 30,
             "suffix": "%", "tip": "Return on Equity",
             "green_min": 15.0, "orange_min": 8.0, "inverted": False},
        ]

    if entity_type == "insurance":
        return [
            {"name": "Solvency Ratio", "key": "solvency_ratio", "lo": 0, "hi": 4,
             "suffix": "x", "tip": "IRDAI minimum: 1.5x",
             "green_min": 2.0, "orange_min": 1.5, "inverted": False},
            {"name": "Claims Ratio", "key": "claims_ratio_percent", "lo": 0, "hi": 120,
             "suffix": "%", "tip": "Net claims / Net earned premium",
             "green_min": 85.0, "orange_min": 100.0, "inverted": True},
            {"name": "Combined Ratio", "key": "combined_ratio_percent", "lo": 0, "hi": 130,
             "suffix": "%", "tip": "Claims + expenses vs premium — <100% is profitable",
             "green_min": 100.0, "orange_min": 110.0, "inverted": True},
            {"name": "Expense Ratio", "key": "expense_ratio_percent", "lo": 0, "hi": 40,
             "suffix": "%", "tip": "Operating expenses / Net premium",
             "green_min": 20.0, "orange_min": 30.0, "inverted": True},
            {"name": "Investment Yield", "key": "investment_yield_percent", "lo": 0, "hi": 15,
             "suffix": "%", "tip": "Investment income / Avg investments",
             "green_min": 8.0, "orange_min": 5.0, "inverted": False},
            {"name": "ROE", "key": "return_on_equity_percent", "lo": 0, "hi": 30,
             "suffix": "%", "tip": "Return on Equity",
             "green_min": 12.0, "orange_min": 5.0, "inverted": False},
        ]

    # Corporate (default)
    return [
        {"name": "Interest Coverage", "key": "interest_coverage_ratio", "lo": 0, "hi": 15,
         "suffix": "x", "tip": "ICR = EBITDA / Finance Cost",
         "green_min": 3.0, "orange_min": 1.5, "inverted": False},
        {"name": "Debt/Equity", "key": "debt_equity_ratio", "lo": 0, "hi": 5,
         "suffix": "x", "tip": "Lower is better",
         "green_min": 1.5, "orange_min": 3.0, "inverted": True},
        {"name": "Current Ratio", "key": "current_ratio", "lo": 0, "hi": 4,
         "suffix": "x", "tip": "Liquidity buffer",
         "green_min": 1.5, "orange_min": 1.0, "inverted": False},
        {"name": "EBITDA Margin", "key": "ebitda_margin_percent", "lo": 0, "hi": 40,
         "suffix": "%", "tip": "Operating efficiency",
         "green_min": 15.0, "orange_min": 8.0, "inverted": False},
        {"name": "ROE", "key": "return_on_equity_percent", "lo": 0, "hi": 50,
         "suffix": "%", "tip": "Return on equity",
         "green_min": 12.0, "orange_min": 5.0, "inverted": False},
        {"name": "DSCR", "key": "dscr_approximate", "lo": 0, "hi": 4,
         "suffix": "x", "tip": "Debt service capacity",
         "green_min": 3.0, "orange_min": 1.5, "inverted": False},
    ]


# ═══════════════════════════════════════════════════════════════════════════ #
# Scoring Anchor Thresholds
# ═══════════════════════════════════════════════════════════════════════════ #

def get_scoring_anchors_config(entity_type: str) -> dict:
    """Return threshold maps for ratio-based scoring anchor computation."""
    if entity_type == "bank":
        return {
            "capacity_metric": "net_interest_margin_percent",
            "capacity_thresholds": [
                (3.5, 85, "NIM ≥3.5% — excellent spread"),
                (2.5, 73, "NIM 2.5-3.5% — good"),
                (1.5, 58, "NIM 1.5-2.5% — adequate"),
                (0,   35, "NIM <1.5% — weak spread"),
            ],
            "capital_metric": "capital_adequacy_ratio_percent",
            "capital_thresholds": [
                (16.0, 85, "CRAR ≥16% — well-capitalised"),
                (12.0, 72, "CRAR 12-16% — adequately capitalised"),
                (9.0,  55, "CRAR 9-12% — meets RBI minimum"),
                (0,    25, "CRAR <9% — under-capitalised"),
            ],
            "asset_quality_metric": "gross_npa_percent",
            "asset_quality_adjustments": [
                (2.0,  +10, "GNPA <2% — clean book"),
                (3.0,  +5,  "GNPA 2-3% — acceptable"),
                (6.0,  -5,  "GNPA 3-6% — stressed"),
                (10.0, -15, "GNPA 6-10% — highly stressed"),
                (100,  -25, "GNPA >10% — critical"),
            ],
        }

    if entity_type == "nbfc":
        return {
            "capacity_metric": "net_interest_margin_percent",
            "capacity_thresholds": [
                (5.0, 85, "NIM ≥5% — excellent for NBFC"),
                (3.5, 73, "NIM 3.5-5% — good"),
                (2.0, 58, "NIM 2-3.5% — moderate"),
                (0,   35, "NIM <2% — thin spread"),
            ],
            "capital_metric": "capital_adequacy_ratio_percent",
            "capital_thresholds": [
                (20.0, 85, "CRAR ≥20% — well-capitalised"),
                (15.0, 72, "CRAR 15-20% — meets RBI NBFC norm"),
                (12.0, 55, "CRAR 12-15% — below norm"),
                (0,    25, "CRAR <12% — under-capitalised"),
            ],
            "asset_quality_metric": "gross_npa_percent",
            "asset_quality_adjustments": [
                (2.0,  +10, "GNPA <2%"),
                (4.0,  +5,  "GNPA 2-4%"),
                (6.0,  -5,  "GNPA 4-6%"),
                (10.0, -15, "GNPA 6-10%"),
                (100,  -25, "GNPA >10%"),
            ],
        }

    if entity_type == "insurance":
        return {
            "capacity_metric": "solvency_ratio",
            "capacity_thresholds": [
                (2.5, 85, "Solvency ≥2.5x — strong"),
                (1.8, 73, "Solvency 1.8-2.5x — adequate"),
                (1.5, 58, "Solvency 1.5-1.8x — meets IRDAI minimum"),
                (0,   30, "Solvency <1.5x — below IRDAI minimum"),
            ],
            "capital_metric": "combined_ratio_percent",
            "capital_thresholds": [
                (95.0,  85, "Combined ratio <95% — highly profitable"),
                (100.0, 72, "Combined ratio 95-100% — profitable"),
                (110.0, 55, "Combined ratio 100-110% — marginal"),
                (999.0, 30, "Combined ratio >110% — loss-making"),
            ],
            "asset_quality_metric": None,
            "asset_quality_adjustments": [],
        }

    # Corporate — use None to signal "use existing logic"
    return {
        "capacity_metric": None,
        "capital_metric": None,
        "asset_quality_metric": None,
        "asset_quality_adjustments": [],
    }


# ═══════════════════════════════════════════════════════════════════════════ #
# Financial Health Score Weights
# ═══════════════════════════════════════════════════════════════════════════ #

def get_health_score_config(entity_type: str) -> list[dict]:
    """Return health score component configs for the dashboard composite score."""
    if entity_type == "bank":
        return [
            {"key": "net_interest_margin_percent", "weight": 20, "max_val": 5.0, "label": "NIM (20%)"},
            {"key": "gross_npa_percent", "weight": 25, "max_val": 10.0, "label": "Asset Quality (25%)", "inverted": True},
            {"key": "capital_adequacy_ratio_percent", "weight": 20, "max_val": 20.0, "label": "Capital Adequacy (20%)"},
            {"key": "return_on_assets_percent", "weight": 15, "max_val": 2.0, "label": "ROA (15%)"},
            {"key": "cost_to_income_ratio_percent", "weight": 10, "max_val": 60.0, "label": "Cost Efficiency (10%)", "inverted": True},
            {"key": "provision_coverage_ratio_percent", "weight": 10, "max_val": 100.0, "label": "PCR (10%)"},
        ]

    if entity_type == "nbfc":
        return [
            {"key": "net_interest_margin_percent", "weight": 20, "max_val": 8.0, "label": "NIM (20%)"},
            {"key": "gross_npa_percent", "weight": 25, "max_val": 10.0, "label": "Asset Quality (25%)", "inverted": True},
            {"key": "capital_adequacy_ratio_percent", "weight": 20, "max_val": 25.0, "label": "Capital Adequacy (20%)"},
            {"key": "return_on_assets_percent", "weight": 15, "max_val": 3.0, "label": "ROA (15%)"},
            {"key": "debt_equity_ratio", "weight": 10, "max_val": 7.0, "label": "Leverage (10%)", "inverted": True},
            {"key": "return_on_equity_percent", "weight": 10, "max_val": 25.0, "label": "ROE (10%)"},
        ]

    if entity_type == "insurance":
        return [
            {"key": "solvency_ratio", "weight": 25, "max_val": 3.0, "label": "Solvency (25%)"},
            {"key": "claims_ratio_percent", "weight": 20, "max_val": 100.0, "label": "Claims Ratio (20%)", "inverted": True},
            {"key": "combined_ratio_percent", "weight": 20, "max_val": 120.0, "label": "Combined Ratio (20%)", "inverted": True},
            {"key": "expense_ratio_percent", "weight": 15, "max_val": 35.0, "label": "Expense Ratio (15%)", "inverted": True},
            {"key": "investment_yield_percent", "weight": 10, "max_val": 12.0, "label": "Investment Yield (10%)"},
            {"key": "return_on_equity_percent", "weight": 10, "max_val": 25.0, "label": "ROE (10%)"},
        ]

    # Corporate (default)
    return [
        {"key": "interest_coverage_ratio", "weight": 25, "max_val": 10.0, "label": "Interest Coverage (25%)"},
        {"key": "debt_equity_ratio", "weight": 20, "max_val": 5.0, "label": "Leverage (20%)", "inverted": True},
        {"key": "current_ratio", "weight": 15, "max_val": 3.0, "label": "Liquidity (15%)"},
        {"key": "ebitda_margin_percent", "weight": 20, "max_val": 25.0, "label": "Profitability (20%)"},
        {"key": "return_on_equity_percent", "weight": 10, "max_val": 25.0, "label": "ROE (10%)"},
        {"key": "dscr_approximate", "weight": 10, "max_val": 3.0, "label": "DSCR (10%)"},
    ]


# ═══════════════════════════════════════════════════════════════════════════ #
# Top-Level Metric Cards Configuration
# ═══════════════════════════════════════════════════════════════════════════ #

def get_top_metrics(entity_type: str) -> list[dict]:
    """Return metric card configs for the top row of Financial Health dashboard."""
    if entity_type == "bank":
        return [
            {"label": "Total Income", "key": "revenue_crores", "fmt": "cr"},
            {"label": "PAT", "key": "profit_after_tax_crores", "fmt": "cr", "delta": True},
            {"label": "Net Interest Income", "key": "net_interest_income_crores", "fmt": "cr"},
            {"label": "Net Worth", "key": "net_worth_crores", "fmt": "cr"},
        ]
    if entity_type == "nbfc":
        return [
            {"label": "Total Income", "key": "revenue_crores", "fmt": "cr"},
            {"label": "PAT", "key": "profit_after_tax_crores", "fmt": "cr", "delta": True},
            {"label": "Net Interest Income", "key": "net_interest_income_crores", "fmt": "cr"},
            {"label": "Net Worth", "key": "net_worth_crores", "fmt": "cr"},
        ]
    if entity_type == "insurance":
        return [
            {"label": "Gross Premium", "key": "revenue_crores", "fmt": "cr"},
            {"label": "PAT", "key": "profit_after_tax_crores", "fmt": "cr", "delta": True},
            {"label": "Investment Income", "key": "investment_income_crores", "fmt": "cr"},
            {"label": "Net Worth", "key": "net_worth_crores", "fmt": "cr"},
        ]
    # Corporate
    return [
        {"label": "Revenue", "key": "revenue_crores", "fmt": "cr"},
        {"label": "PAT", "key": "profit_after_tax_crores", "fmt": "cr", "delta": True},
        {"label": "EBITDA", "key": "ebitda_crores", "fmt": "cr"},
        {"label": "Net Worth", "key": "net_worth_crores", "fmt": "cr"},
    ]


# ═══════════════════════════════════════════════════════════════════════════ #
# Person / Director Deduplication
# ═══════════════════════════════════════════════════════════════════════════ #

_TITLE_PATTERN = re.compile(
    r'^(mr\.?|mrs\.?|ms\.?|dr\.?|shri\.?|smt\.?|prof\.?|justice\.?|hon\.?|ca\.?)\s+',
    re.IGNORECASE,
)


def _normalize_person_name(name: str) -> str:
    """Strip honorifics and normalize whitespace for comparison."""
    cleaned = _TITLE_PATTERN.sub("", name.strip())
    # Collapse whitespace and lowercase
    return re.sub(r'\s+', ' ', cleaned).strip().lower()


def deduplicate_persons(persons: list) -> list:
    """
    Deduplicate a list of person dicts or strings.
    Handles: [{"name": "Mr. X"}, "Dr. X", {"name": "X"}] → single entry.
    """
    seen: set[str] = set()
    result: list = []
    for p in persons:
        if isinstance(p, dict):
            raw_name = p.get("name", "")
        else:
            raw_name = str(p)
        if not raw_name or not raw_name.strip():
            continue
        key = _normalize_person_name(raw_name)
        if key and key not in seen:
            seen.add(key)
            result.append(p)
    return result


# ═══════════════════════════════════════════════════════════════════════════ #
# CAM Financial Table Configuration
# ═══════════════════════════════════════════════════════════════════════════ #

def get_cam_financial_rows(entity_type: str) -> list[tuple[str, str, str]]:
    """
    Return (label, dict_key, format_type) tuples for CAM financial analysis table.
    format_type: "cr" = crore fmt, "pct" = percentage, "ratio" = 2-decimal x.
    """
    if entity_type == "bank":
        return [
            ("Total Income",                "revenue_crores",                      "cr"),
            ("Net Interest Income",         "net_interest_income_crores",          "cr"),
            ("Net Interest Margin",         "net_interest_margin_percent",         "pct"),
            ("Profit After Tax",            "profit_after_tax_crores",             "cr"),
            ("Total Assets",                "total_assets_crores",                 "cr"),
            ("Total Deposits",              "total_deposits_crores",               "cr"),
            ("Net Worth",                   "net_worth_crores",                    "cr"),
            ("Capital Adequacy (CRAR)",     "capital_adequacy_ratio_percent",      "pct"),
            ("Tier 1 Capital Ratio",        "tier1_capital_ratio_percent",         "pct"),
            ("Gross NPA",                   "gross_npa_percent",                   "pct"),
            ("Net NPA",                     "net_npa_percent",                     "pct"),
            ("Provision Coverage Ratio",    "provision_coverage_ratio_percent",    "pct"),
            ("Cost-to-Income Ratio",        "cost_to_income_ratio_percent",        "pct"),
            ("Return on Assets",            "return_on_assets_percent",            "pct"),
            ("Return on Equity",            "return_on_equity_percent",            "pct"),
            ("CASA Ratio",                  "casa_ratio_percent",                  "pct"),
        ]

    if entity_type == "nbfc":
        return [
            ("Total Income",            "revenue_crores",                      "cr"),
            ("Net Interest Income",     "net_interest_income_crores",          "cr"),
            ("Net Interest Margin",     "net_interest_margin_percent",         "pct"),
            ("Profit After Tax",        "profit_after_tax_crores",             "cr"),
            ("Total Assets",            "total_assets_crores",                 "cr"),
            ("Net Worth",               "net_worth_crores",                    "cr"),
            ("Total Borrowings",        "total_borrowings_crores",             "cr"),
            ("Capital Adequacy (CRAR)", "capital_adequacy_ratio_percent",      "pct"),
            ("Debt / Equity",           "debt_equity_ratio",                   "ratio"),
            ("Gross NPA",               "gross_npa_percent",                   "pct"),
            ("Net NPA",                 "net_npa_percent",                     "pct"),
            ("Return on Assets",        "return_on_assets_percent",            "pct"),
            ("Return on Equity",        "return_on_equity_percent",            "pct"),
        ]

    if entity_type == "insurance":
        return [
            ("Gross Written Premium",  "revenue_crores",                "cr"),
            ("Net Earned Premium",     "net_earned_premium_crores",     "cr"),
            ("Profit After Tax",       "profit_after_tax_crores",       "cr"),
            ("Total Assets",           "total_assets_crores",           "cr"),
            ("Net Worth",              "net_worth_crores",              "cr"),
            ("Solvency Ratio",         "solvency_ratio",               "ratio"),
            ("Claims Ratio",           "claims_ratio_percent",          "pct"),
            ("Combined Ratio",         "combined_ratio_percent",        "pct"),
            ("Expense Ratio",          "expense_ratio_percent",         "pct"),
            ("Investment Yield",       "investment_yield_percent",      "pct"),
            ("Return on Equity",       "return_on_equity_percent",      "pct"),
        ]

    # Corporate (default)
    return [
        ("Revenue",            "revenue_crores",                "cr"),
        ("Revenue Growth",     "revenue_growth_percent",        "pct"),
        ("Profit After Tax",   "profit_after_tax_crores",       "cr"),
        ("EBITDA",             "ebitda_crores",                 "cr"),
        ("EBITDA Margin",      "ebitda_margin_percent",         "pct"),
        ("Total Assets",       "total_assets_crores",           "cr"),
        ("Net Worth",          "net_worth_crores",              "cr"),
        ("Total Borrowings",   "total_borrowings_crores",       "cr"),
        ("Debt / Equity",      "debt_equity_ratio",             "ratio"),
        ("Current Ratio",      "current_ratio",                 "ratio"),
        ("Interest Coverage",  "interest_coverage_ratio",       "ratio"),
        ("Return on Equity",   "return_on_equity_percent",      "pct"),
    ]
