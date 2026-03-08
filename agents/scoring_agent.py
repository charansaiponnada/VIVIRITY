"""
agents/scoring_agent.py
-----------------------
Fixes applied in this version:
  #1  Penalty engine — surgical rules, no false positives on demergers
  #2  ML + Five Cs blending layer — single final score and decision
  #6  Loan sizing — calibrated to net worth, revenue, NBFC concentration limits
  #7  Research rating — structured signal-counting rubric
"""
import os
import re
import json
import time
from google import genai
from google.genai.errors import ServerError, ClientError
from dotenv import load_dotenv

load_dotenv()


def _gemini_with_retry(client, model: str, contents,
                        max_retries: int = 5,
                        fallback: str = "gemini-2.0-flash-lite"):
    for attempt in range(max_retries):
        current_model = fallback if attempt == max_retries - 1 else model
        try:
            return client.models.generate_content(model=current_model, contents=contents)
        except ServerError:
            if attempt == max_retries - 1:
                raise
            wait = 8 * (2 ** min(attempt, 3))
            print(f"[Gemini] 503 — retrying in {wait}s (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
        except ClientError as e:
            if "429" in str(e):
                if attempt == max_retries - 1:
                    raise
                wait = 10 * (2 ** min(attempt, 3))
                print(f"[Gemini] 429 — retrying in {wait}s")
                time.sleep(wait)
            else:
                raise


# ── Penalty definitions — each entry has (points, trigger_condition, label) ── #
# Only TRUE credit-risk events are penalised. Corporate actions are EXCLUDED.
PENALTY_RULES = {
    # Financial distress signals (from extracted document)
    "audit_qualified":      (10, "red_flag_field",  "Audit qualified — accounting concerns"),
    "going_concern":        (15, "red_flag_field",  "Going concern doubt — existence risk"),
    "npa_mention":          (12, "red_flag_field",  "NPA classification mentioned"),
    "wilful_default_doc":   (30, "keyword_search",  "Wilful default in document"),
    "circular_trading":     (10, "keyword_search",  "Circular trading pattern detected"),

    # Promoter / character signals (from research)
    "promoter_wilful":      (30, "research_field",  "Promoter on wilful defaulter list"),
    "promoter_criminal":    (20, "research_field",  "Criminal cases against promoter"),
    "sfio_investigation":   (15, "research_field",  "SFIO investigation ongoing"),

    # Regulatory enforcement (from research) — NOT routine compliance
    "sebi_enforcement":     (12, "research_field",  "SEBI enforcement order"),
    "rbi_restriction":      (15, "research_field",  "RBI restriction / direction"),

    # Legal — TRUE distress signals only
    "ibc_cirp":             (25, "research_field",  "IBC/CIRP insolvency proceedings"),
    "drt_cases":            ( 8, "research_field",  "DRT recovery proceedings"),

    # Cross-reference fraud flags
    "revenue_inflation":    (12, "cross_ref_field", "Revenue inflation detected (GST vs AR mismatch)"),
    "circular_bank":        (15, "cross_ref_field", "Circular trading (bank vs AR mismatch)"),

    # Manual field notes
    "factory_idle":         (10, "manual_notes",    "Factory underutilisation / idle"),
    "mgmt_evasive":         ( 8, "manual_notes",    "Management evasive / uncooperative"),
    "revenue_mismatch":     (12, "manual_notes",    "Revenue mismatch / discrepancy noted"),
}

# ── EXCLUDED events — these must NEVER trigger penalties ── #
EXCLUDED_NCLT_TYPES = [
    "demerger", "merger", "amalgamation", "restructuring", "scheme of arrangement",
    "capital reduction", "buy-back", "subdivision", "bonus issue",
]

EXCLUDED_NCLT_KEYWORDS = [
    "demerger", "merger", "amalgamat", "scheme of arrangement",
    "restructur", "capital reduction", "buy back", "subdivision",
    "bonus", "split", "approval granted", "nclt approved",
]

# ── Interest rate table (Base 10.5% + risk premium) ── #
RATE_TABLE = {
    "AAA": 11.0, "AA": 11.5, "A": 12.5,
    "BBB": 13.0, "BB": 14.0, "B": 15.5,
    "CCC": None, "D": None,
}

# ── Loan sizing parameters (RBI single-borrower exposure norms) ── #
LOAN_NW_RATIO      = 0.05   # 5% of net worth (NBFC prudential norm)
LOAN_REV_RATIO     = 0.015  # 1.5% of annual revenue
LOAN_MAX_CAP_CR    = 2000   # Hard cap per borrower for mid-NBFC (₹ Cr)
LOAN_MIN_CR        = 10     # Minimum meaningful loan


class ScoringAgent:
    """
    All 8 mandatory methods present:
    1. run()
    2. score_five_cs()
    3. calculate_risk_score()
    4. generate_recommendation()
    5. adjust_for_manual_notes()
    6. _calculate_penalties()
    7. _score_to_rating()
    8. _parse_json()

    Additional methods (fixes):
    - _compute_ratio_anchors()
    - _blend_scores()            ← FIX #2
    - _calibrated_loan_amount()  ← FIX #6
    - _research_rating()         ← FIX #7
    - _penalty_from_research()   ← FIX #1 (surgical rules)
    - _is_excluded_nclt()        ← FIX #1 (demerger guard)
    """

    def __init__(self, company_name: str, financials: dict,
                 research: dict, manual_notes: str = ""):
        self.company_name = company_name
        self.financials   = financials or {}
        self.research     = research   or {}
        self.manual_notes = manual_notes or ""
        self.model        = "gemini-2.5-flash"
        self.client       = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # ══════════════════════════════════════════════════════════════════════ #
    # 1. run()
    # ══════════════════════════════════════════════════════════════════════ #
    def run(self) -> dict:
        print(f"[ScoringAgent] Scoring {self.company_name}...")

        ratio_anchors = self._compute_ratio_anchors()
        five_cs       = self.score_five_cs(ratio_anchors)
        risk_score    = self.calculate_risk_score(five_cs)
        recommendation = self.generate_recommendation(five_cs, risk_score)

        return {
            "five_cs":        five_cs,
            "risk_score":     risk_score,
            "recommendation": recommendation,
            "ratio_anchors":  ratio_anchors,
        }

    # ══════════════════════════════════════════════════════════════════════ #
    # 2. score_five_cs()
    # ══════════════════════════════════════════════════════════════════════ #
    def score_five_cs(self, ratio_anchors: dict = None) -> dict:
        print("[ScoringAgent] Scoring Five Cs...")

        anchors     = ratio_anchors or {}
        fin_summary = json.dumps(self.financials, indent=2)[:3000]
        res_summary = json.dumps(self.research,   indent=2)[:2000]

        anchor_block = f"""
MATHEMATICALLY COMPUTED RATIO ANCHORS — HARD MINIMUM FLOORS:
- Capacity  ≥ {anchors.get('capacity_floor',  'N/A')} — {anchors.get('capacity_reason',  '')}
- Capital   ≥ {anchors.get('capital_floor',   'N/A')} — {anchors.get('capital_reason',   '')}
- Character ≥ {anchors.get('character_floor', 'N/A')} — {anchors.get('character_reason', '')}
- Collateral≥ {anchors.get('collateral_floor','N/A')} — {anchors.get('collateral_reason','')}
{f"- EXTERNAL RATING: {anchors['external_rating_override']} → overall MUST be ≥ {anchors.get('external_rating_floor',70)}" if anchors.get('external_rating_override') else ''}

KEY RATIOS (mathematically computed):
- ICR (EBITDA/FinCost): {anchors.get('icr','N/A')}x
- Debt/Equity: {anchors.get('de','N/A')}x
- Current Ratio: {anchors.get('cr','N/A')}x
- DSCR (approx): {anchors.get('dscr','N/A')}x
- EBITDA Margin: {anchors.get('ebitda_margin','N/A')}%
- ROE: {anchors.get('roe','N/A')}%

YOU MUST NOT SCORE BELOW THESE FLOORS.
"""

        prompt = f"""
You are a senior credit analyst at Vivriti Capital, an Indian NBFC.
Score the Five Cs of Credit for: {self.company_name}

Financial data:
{fin_summary}

Research intelligence:
{res_summary}

Manual field notes: {self.manual_notes or "None provided."}

{anchor_block}

SCORING CONTEXT (RBI IRAC norms):
- Capacity (30%): Revenue trend, EBITDA margin, ICR, DSCR, cash flow
- Character (25%): Promoter track record, governance, no wilful default
- Capital (20%): Net worth, debt-equity, leverage
- Collateral (15%): Fixed assets, security coverage, charges
- Conditions (10%): Sector health, macro, RBI regulations

SCALE: 85-100 Excellent | 70-84 Good | 55-69 Moderate | 40-54 Weak | 0-39 Critical

RULES:
1. NCLT demerger/restructuring = neutral. Do NOT penalise Character or Conditions.
2. Missing data for a large listed company is NOT bad data. Use scale inference.
3. Sector "Strong" + "Low lending risk" → Conditions ≥ 65.
4. Each rationale must cite a specific number or data point.

Return ONLY valid JSON. No markdown. No thinking tokens.
{{
    "character_score": 0, "character_rationale": "cite data",
    "capacity_score":  0, "capacity_rationale":  "cite ICR/margin/DSCR",
    "capital_score":   0, "capital_rationale":   "cite D/E or net worth",
    "collateral_score":0, "collateral_rationale":"cite assets or charges",
    "conditions_score":0, "conditions_rationale":"cite sector/macro"
}}
"""
        try:
            time.sleep(3)
            response = _gemini_with_retry(self.client, self.model, prompt)
            raw = re.sub(r'<think>.*?</think>', '', response.text, flags=re.DOTALL).strip()
            print(f"[DEBUG FIVE CS RAW]: {repr(raw[:300])}")
            result = self._parse_json(raw)
            if result.get("parse_error"):
                raise ValueError("JSON parse failed")

            print(f"[DEBUG FIVE CS PARSED]: capacity={result.get('capacity_score')} "
                  f"character={result.get('character_score')} capital={result.get('capital_score')}")

            # Enforce hard floors from ratio anchors
            floors = {
                "capacity_score":    anchors.get("capacity_floor",   0),
                "capital_score":     anchors.get("capital_floor",    0),
                "character_score":   anchors.get("character_floor",  0),
                "collateral_score":  anchors.get("collateral_floor", 0),
            }
            for key, floor in floors.items():
                if result.get(key, 0) < floor:
                    print(f"  [FloorEnforced] {key}: {result.get(key)} → {floor}")
                    result[key] = floor
                    result[f"{key}_floor_enforced"] = True

            return result

        except Exception as e:
            print(f"[ScoringAgent] Five Cs failed: {e}")
            insufficient = "DATA INSUFFICIENT — manual review required."
            return {
                "character_score":0,"character_rationale":insufficient,
                "capacity_score": 0,"capacity_rationale": insufficient,
                "capital_score":  0,"capital_rationale":  insufficient,
                "collateral_score":0,"collateral_rationale":insufficient,
                "conditions_score":0,"conditions_rationale":insufficient,
                "scoring_failed":True,"failure_reason":str(e),
            }

    # ══════════════════════════════════════════════════════════════════════ #
    # 3. calculate_risk_score()
    # ══════════════════════════════════════════════════════════════════════ #
    def calculate_risk_score(self, five_cs: dict) -> dict:
        weights = {"capacity":0.30,"character":0.25,"capital":0.20,"collateral":0.15,"conditions":0.10}

        if five_cs.get("scoring_failed"):
            return {
                "raw_scores":{c:0 for c in weights}, "weights":weights,
                "weighted_score":0, "penalty_applied":0, "final_score":0,
                "rating":"UNRATED", "scoring_failed":True,
                "failure_reason":five_cs.get("failure_reason","AI unavailable"),
                "score_breakdown":{c:{"score":0,"weight":weights[c],"contribution":0} for c in weights},
                "penalty_breakdown":[],
            }

        scores = {c: max(five_cs.get(f"{c}_score", 1), 1) for c in weights}
        weighted_score = sum(scores[c] * weights[c] for c in weights)

        penalty, penalty_breakdown = self._calculate_penalties()
        final_score = max(0, weighted_score - penalty)
        rating      = self._score_to_rating(final_score)

        return {
            "raw_scores":      scores,
            "weights":         weights,
            "weighted_score":  round(weighted_score, 2),
            "penalty_applied": round(penalty, 2),
            "penalty_breakdown": penalty_breakdown,
            "final_score":     round(final_score, 2),
            "rating":          rating,
            "score_breakdown": {
                c: {"score":scores[c],"weight":weights[c],"contribution":round(scores[c]*weights[c],2)}
                for c in weights
            },
        }

    # ══════════════════════════════════════════════════════════════════════ #
    # 4. generate_recommendation()  — now uses blended score
    # ══════════════════════════════════════════════════════════════════════ #
    def generate_recommendation(self, five_cs: dict, risk_score: dict,
                                 ml_results: dict = None) -> dict:
        print("[ScoringAgent] Generating recommendation...")

        if risk_score.get("scoring_failed"):
            return {
                "decision": "CANNOT_ASSESS",
                "decision_rationale": f"AI scoring failed: {risk_score.get('failure_reason')}. Manual review required.",
                "recommended_amount_crores": None, "interest_rate_percent": None,
                "tenure_months": None,
                "key_conditions": ["Manual underwriter review mandatory before any disbursement"],
                "rejection_reason": "System could not complete automated scoring.",
                "final_score": 0, "rating": "UNRATED",
            }

        # FIX #2 — Blend Five Cs + ML scores
        blend = self._blend_scores(risk_score, ml_results)
        final_score = blend["blended_score"]
        rating      = self._score_to_rating(final_score)

        # Decision from blended score
        if final_score >= 75:
            decision = "APPROVE"
        elif final_score >= 50:
            decision = "CONDITIONAL_APPROVE"
        else:
            decision = "REJECT"
        if rating in ("CCC", "D"):
            decision = "REJECT"

        rate = RATE_TABLE.get(rating)

        # FIX #6 — calibrated loan amount
        amount = self._calibrated_loan_amount()

        # FIX #7 — research rating
        research_rating = self._research_rating()

        prompt = f"""
You are a senior credit officer at Vivriti Capital, an Indian NBFC.
Generate the final lending recommendation for: {self.company_name}

Five Cs Assessment:
{json.dumps(five_cs, indent=2)[:2000]}

Blended Risk Score: {final_score}/100
Rating: {rating}
Decision (pre-determined): {decision}
Interest Rate: {rate or 'REJECT'}%
Recommended Loan Amount: ₹{amount} Cr
Research Rating: {research_rating['grade']}
Penalty Applied: {risk_score['penalty_applied']} pts — {[p['label'] for p in risk_score.get('penalty_breakdown', [])]}
Model Divergence: {blend.get('divergence_alert', 'None')}

Manual field notes: {self.manual_notes or "None"}

Generate:
1. A 3-5 sentence decision rationale citing Five Cs scores and key data points
2. 2-3 specific, actionable conditions if CONDITIONAL_APPROVE
3. rejection_reason if REJECT

Return ONLY valid JSON. No markdown. No thinking tokens.
{{
    "decision": "{decision}",
    "decision_rationale": "3-5 sentences citing Five Cs",
    "recommended_amount_crores": {amount},
    "interest_rate_percent": {rate or "null"},
    "tenure_months": 36,
    "key_conditions": [],
    "rejection_reason": null
}}
"""
        time.sleep(3)
        response = _gemini_with_retry(self.client, self.model, prompt)
        raw      = re.sub(r'<think>.*?</think>', '', response.text, flags=re.DOTALL).strip()
        result   = self._parse_json(raw)

        # Hard-set computed values — Gemini cannot override these
        result["decision"]                  = decision
        result["final_score"]               = round(final_score, 2)
        result["rating"]                    = rating
        result["interest_rate_percent"]     = rate
        result["recommended_amount_crores"] = amount
        result["blend_details"]             = blend
        result["research_rating"]           = research_rating

        return result

    # ══════════════════════════════════════════════════════════════════════ #
    # 5. adjust_for_manual_notes()
    # ══════════════════════════════════════════════════════════════════════ #
    def adjust_for_manual_notes(self, new_notes: str) -> dict:
        self.manual_notes = new_notes
        return self.run()

    # ══════════════════════════════════════════════════════════════════════ #
    # 6. _calculate_penalties()  — FIX #1: surgical rules, no false positives
    # ══════════════════════════════════════════════════════════════════════ #
    def _calculate_penalties(self) -> tuple[float, list[dict]]:
        """
        Returns (total_penalty, breakdown_list).
        ONLY fires on confirmed credit-risk events.
        Corporate actions (demergers, mergers, restructuring) are EXCLUDED.
        """
        penalty   = 0.0
        breakdown = []

        def add(pts: float, label: str):
            nonlocal penalty
            penalty += pts
            breakdown.append({"points": pts, "label": label})
            print(f"  [Penalty] +{pts} pts — {label}")

        # ── Financial document red flags ─────────────────────────────── #
        rf = self.financials.get("red_flags", {})
        if rf.get("audit_qualified"):     add(10, "Audit qualified — accounting concerns")
        if rf.get("going_concern_issue"): add(15, "Going concern doubt")
        if rf.get("npa_mention"):         add(12, "NPA classification mentioned")

        # Keyword scan — only on red_flags dict, NOT full document
        rf_str = json.dumps(rf).lower()
        if "wilful default" in rf_str: add(30, "Wilful default in document")
        if "circular trading" in rf_str: add(10, "Circular trading detected")

        # ── Promoter background ───────────────────────────────────────── #
        promoter = self.research.get("promoter_background", {})
        if promoter.get("wilful_defaulter"): add(30, "Promoter on wilful defaulter list")
        if promoter.get("criminal_cases"):   add(20, "Criminal cases against promoter")
        if promoter.get("sfio_investigation"): add(15, "SFIO investigation active")

        # ── Regulatory enforcement ────────────────────────────────────── #
        reg = self.research.get("regulatory", {})
        if reg.get("sebi_actions") and not reg.get("sebi_settlement"):
            add(12, "SEBI enforcement order (unsettled)")
        if reg.get("rbi_issues"):
            add(15, "RBI restriction / regulatory direction")

        # ── Legal proceedings — ONLY confirmed distress ───────────────── #
        # Check both 'litigation' and 'legal_disputes' for backward compat
        litigation = self.research.get("litigation") or self.research.get("legal_disputes", {})

        # IBC/CIRP — always a hard distress signal
        if litigation.get("ibc_cirp"):
            add(25, "IBC/CIRP insolvency proceedings active")

        # NCLT — ONLY penalise if confirmed insolvency, NOT corporate actions
        if litigation.get("nclt_proceedings"):
            if not self._is_excluded_nclt(litigation):
                nclt_type = litigation.get("nclt_type", "unknown")
                add(20, f"NCLT proceedings — confirmed distress (type: {nclt_type})")
            else:
                nclt_type = litigation.get("nclt_type", "")
                print(f"  [Penalty] NCLT excluded — corporate action: {nclt_type}")

        # DRT — debt recovery is a distress signal
        if litigation.get("drt_cases"):
            add(8, "DRT debt recovery proceedings")

        # ── Cross-reference fraud flags ───────────────────────────────── #
        cross_ref = self.research.get("cross_reference", {})
        if cross_ref.get("circular_trading_risk") == "High":
            add(15, "Circular trading risk (cross-reference)")
        if cross_ref.get("revenue_inflation_risk") == "High":
            add(12, "Revenue inflation detected (cross-reference)")

        # ── Manual field notes ────────────────────────────────────────── #
        if self.manual_notes:
            n = self.manual_notes.lower()
            if any(w in n for w in ["idle","shutdown","operating at","% capacity","underutil"]):
                add(10, "Factory underutilisation / capacity concern")
            if any(w in n for w in ["evasive","uncooperative","refused","avoided"]):
                add(8, "Management evasive / uncooperative")
            if any(w in n for w in ["inflated","mismatch","discrepancy","round-trip","circular"]):
                add(12, "Revenue mismatch / inflation concern")

        # Cap at 30 — no single run can zero-out a healthy company
        total = min(penalty, 30)
        if total < penalty:
            print(f"  [Penalty] Cap applied: {penalty:.1f} → {total:.1f}")

        return total, breakdown

    # ── Helper: is this NCLT filing a corporate action? ────────────────── #
    def _is_excluded_nclt(self, litigation: dict) -> bool:
        """
        Returns True if the NCLT proceedings are a corporate action
        (demerger, merger, restructuring) — these should NOT be penalised.
        """
        nclt_type = (litigation.get("nclt_type") or "").lower()
        summary   = (litigation.get("summary")   or "").lower()
        combined  = nclt_type + " " + summary

        # Check against excluded event types
        if any(excl in combined for excl in EXCLUDED_NCLT_KEYWORDS):
            return True

        # Extra safety: if insolvency keywords are present, it IS distress
        distress_keywords = [
            "insolvency", "liquidation", "winding up", "resolution professional",
            "moratorium", "cirp", "ibc", "corporate debtor", "suspended board",
        ]
        if any(kw in combined for kw in distress_keywords):
            return False

        # Default: if unclear, lean toward exclusion (avoid false positives)
        return True

    # ══════════════════════════════════════════════════════════════════════ #
    # FIX #2 — Model blending layer
    # ══════════════════════════════════════════════════════════════════════ #
    def _blend_scores(self, risk_score: dict, ml_results: dict = None) -> dict:
        """
        Blend Five Cs weighted score + ML probability score into one final score.

        Weights:
          Five Cs (rule-based, auditable)  : 55%
          ML model (probabilistic)          : 45%

        When models diverge > 15 pts → raise alert for senior review.
        When ML not available → use Five Cs only (with note).
        """
        fivecs_score = risk_score.get("final_score", 0)  # Already penalty-adjusted

        if not ml_results or ml_results.get("scoring_failed"):
            return {
                "blended_score":   fivecs_score,
                "fivecs_score":    fivecs_score,
                "ml_score":        None,
                "blend_method":    "Five Cs only (ML unavailable)",
                "divergence_alert": None,
                "weights_used":    {"fivecs": 1.0, "ml": 0.0},
            }

        ml_score = ml_results.get("ml_score", 0)

        # Blending
        W_FIVECS = 0.55
        W_ML     = 0.45
        blended  = round(W_FIVECS * fivecs_score + W_ML * ml_score, 2)

        divergence = abs(fivecs_score - ml_score)
        alert = None
        if divergence > 25:
            alert = (
                f"HIGH DIVERGENCE ({divergence:.1f} pts): "
                f"Five Cs={fivecs_score:.1f} vs ML={ml_score:.1f}. "
                f"Senior credit officer review mandatory before disbursement."
            )
            print(f"  [Blend] HIGH DIVERGENCE: {alert}")
        elif divergence > 15:
            alert = (
                f"MODEL DIVERGENCE ({divergence:.1f} pts): "
                f"Five Cs={fivecs_score:.1f} vs ML={ml_score:.1f}. "
                f"Document rationale for discrepancy."
            )
            print(f"  [Blend] DIVERGENCE: {alert}")

        print(f"  [Blend] FiveCs={fivecs_score:.1f} × 55% + ML={ml_score:.1f} × 45% = Blended={blended:.1f}")

        return {
            "blended_score":    blended,
            "fivecs_score":     fivecs_score,
            "ml_score":         ml_score,
            "blend_method":     f"55% Five Cs + 45% ML (logistic regression)",
            "divergence_points": round(divergence, 1),
            "divergence_alert": alert,
            "weights_used":     {"fivecs": W_FIVECS, "ml": W_ML},
        }

    # ══════════════════════════════════════════════════════════════════════ #
    # FIX #6 — Calibrated loan sizing
    # ══════════════════════════════════════════════════════════════════════ #
    def _calibrated_loan_amount(self) -> float:
        """
        Loan size calibrated to company scale and NBFC prudential norms.

        Formula:
          loan = min(
              net_worth × 5%,           ← capital adequacy link
              revenue   × 1.5%,         ← operating scale link
              NBFC single-borrower cap  ← concentration risk limit
          )

        For working capital specifically, also check:
          working_capital_requirement ≈ (trade_receivables + inventories) × 30%
        """
        def sf(key):
            try:
                v = self.financials.get(key)
                return float(v) if v is not None else None
            except Exception:
                return None

        nw  = sf("net_worth_crores")
        rev = sf("revenue_crores")
        tr  = sf("trade_receivables_crores")
        inv = sf("inventories_crores")

        candidates = []
        reasons    = []

        if nw and nw > 0:
            nw_amt = round(nw * LOAN_NW_RATIO, 0)
            candidates.append(nw_amt)
            reasons.append(f"NW×{LOAN_NW_RATIO*100:.0f}%=₹{nw_amt:.0f}Cr")

        if rev and rev > 0:
            rev_amt = round(rev * LOAN_REV_RATIO, 0)
            candidates.append(rev_amt)
            reasons.append(f"Rev×{LOAN_REV_RATIO*100:.1f}%=₹{rev_amt:.0f}Cr")

        # Working capital proxy
        if tr and inv:
            wc_amt = round((tr + inv) * 0.30, 0)
            candidates.append(wc_amt)
            reasons.append(f"WC proxy (30% of receivables+inventory)=₹{wc_amt:.0f}Cr")

        if not candidates:
            # No financial data — use conservative default
            return 50.0

        raw_amount = min(candidates)
        # Apply hard caps
        final_amount = min(raw_amount, LOAN_MAX_CAP_CR)
        final_amount = max(final_amount, LOAN_MIN_CR)
        final_amount = round(final_amount, 0)

        print(f"  [LoanSizing] Candidates: {reasons} → raw={raw_amount:.0f}Cr → final=₹{final_amount:.0f}Cr")
        return final_amount

    # ══════════════════════════════════════════════════════════════════════ #
    # FIX #7 — Research rating with structured signal counting
    # ══════════════════════════════════════════════════════════════════════ #
    def _research_rating(self) -> dict:
        """
        Maps research signals to a rating using structured scoring.
        Each signal is worth +/- points. Total determines grade.

        Grade thresholds:
          A (Strong Proceed): total ≥ 6
          B (Proceed):        total ≥ 2
          C (Caution):        total ≥ -2
          D (Reject):         total <  -2
        """
        r   = self.research
        pts = 0
        evidence = []

        # Positive signals
        promoter = r.get("promoter_background", {})
        if promoter.get("risk_level") == "Low":
            pts += 2; evidence.append("+2 Clean promoter (Low risk)")
        elif promoter.get("risk_level") == "Medium":
            pts += 1; evidence.append("+1 Moderate promoter risk")

        mca = r.get("mca_signals", {})
        if mca.get("mca_risk") == "Low":
            pts += 1; evidence.append("+1 Clean MCA record")

        reg = r.get("regulatory", {})
        if reg.get("regulatory_risk") == "Low":
            pts += 1; evidence.append("+1 No regulatory actions")

        sector = r.get("sector_headwinds", {})
        if sector.get("sector_health") == "Strong":
            pts += 2; evidence.append("+2 Strong sector")
        elif sector.get("sector_health") == "Stable":
            pts += 1; evidence.append("+1 Stable sector")

        news = r.get("company_news", {})
        if news.get("sentiment") == "Positive":
            pts += 1; evidence.append("+1 Positive news sentiment")
        if news.get("external_credit_rating") and any(
            x in str(news.get("external_credit_rating","")).upper()
            for x in ["AA","AAA","A+","A "]):
            pts += 2; evidence.append("+2 Investment-grade external rating")

        lit = r.get("litigation") or r.get("legal_disputes", {})
        if lit.get("litigation_risk") == "Low":
            pts += 1; evidence.append("+1 Low litigation risk")

        # Negative signals
        if promoter.get("wilful_defaulter"):
            pts -= 5; evidence.append("-5 Wilful defaulter")
        if promoter.get("criminal_cases"):
            pts -= 3; evidence.append("-3 Criminal cases")
        if reg.get("sebi_actions") and not reg.get("sebi_settlement"):
            pts -= 2; evidence.append("-2 SEBI enforcement")
        if reg.get("rbi_issues"):
            pts -= 2; evidence.append("-2 RBI issues")
        if lit.get("ibc_cirp"):
            pts -= 4; evidence.append("-4 IBC/CIRP proceedings")
        if lit.get("drt_cases"):
            pts -= 1; evidence.append("-1 DRT cases")
        if sector.get("sector_health") in ("Stressed","Distressed"):
            pts -= 2; evidence.append("-2 Stressed sector")
        if news.get("default_mentions"):
            pts -= 3; evidence.append("-3 Default mentioned in news")

        if pts >= 6:
            grade, label = "A", "Strong Proceed"
        elif pts >= 2:
            grade, label = "B", "Proceed"
        elif pts >= -2:
            grade, label = "C", "Caution"
        else:
            grade, label = "D", "Reject"

        print(f"  [ResearchRating] Score={pts} → {grade} ({label})")
        return {"grade": grade, "label": label, "score": pts, "evidence": evidence}

    # ══════════════════════════════════════════════════════════════════════ #
    # Supporting methods for _compute_ratio_anchors (unchanged logic)
    # ══════════════════════════════════════════════════════════════════════ #
    def _compute_ratio_anchors(self) -> dict:
        f = self.financials

        def sf(key):
            try:
                v = f.get(key)
                return float(v) if v is not None else None
            except Exception:
                return None

        icr    = sf("interest_coverage_ratio")
        de     = sf("debt_equity_ratio")
        cr     = sf("current_ratio")
        dscr   = sf("dscr_approximate")
        roe    = sf("return_on_equity_percent")
        ebitda_m = sf("ebitda_margin_percent")
        rev    = sf("revenue_crores")

        anchors = {"icr":icr,"de":de,"cr":cr,"dscr":dscr,"roe":roe,"ebitda_margin":ebitda_m}

        # Capacity floor
        capacity_floor, capacity_reason = 40, "No ratio data"
        if icr is not None:
            if icr >= 10:   capacity_floor, capacity_reason = 85, f"ICR {icr:.1f}x (>10x — excellent)"
            elif icr >= 7:  capacity_floor, capacity_reason = 80, f"ICR {icr:.1f}x (7-10x — strong)"
            elif icr >= 5:  capacity_floor, capacity_reason = 73, f"ICR {icr:.1f}x (5-7x — good)"
            elif icr >= 3:  capacity_floor, capacity_reason = 63, f"ICR {icr:.1f}x (3-5x — adequate)"
            elif icr >= 1.5:capacity_floor, capacity_reason = 50, f"ICR {icr:.1f}x (marginal)"
            else:           capacity_floor, capacity_reason = 28, f"ICR {icr:.1f}x (weak)"
        if ebitda_m is not None:
            em_floor = 28
            if ebitda_m >= 20:   em_floor = 80
            elif ebitda_m >= 13: em_floor = 70
            elif ebitda_m >= 8:  em_floor = 58
            if em_floor > capacity_floor:
                capacity_floor  = em_floor
                capacity_reason = f"EBITDA margin {ebitda_m:.1f}%"

        anchors["capacity_floor"]  = capacity_floor
        anchors["capacity_reason"] = capacity_reason

        # Capital floor
        capital_floor, capital_reason = 40, "No leverage data"
        if de is not None:
            if de <= 0.3:   capital_floor, capital_reason = 85, f"D/E {de:.2f}x (≤0.3x very low)"
            elif de <= 0.75:capital_floor, capital_reason = 75, f"D/E {de:.2f}x (0.3-0.75x low)"
            elif de <= 1.5: capital_floor, capital_reason = 62, f"D/E {de:.2f}x (0.75-1.5x moderate)"
            elif de <= 3:   capital_floor, capital_reason = 48, f"D/E {de:.2f}x (1.5-3x high)"
            else:           capital_floor, capital_reason = 28, f"D/E {de:.2f}x (>3x very high)"
        if rev and rev > 10000 and capital_floor < 55:
            capital_floor = 55
            capital_reason += " (floor: large listed company)"

        anchors["capital_floor"]  = capital_floor
        anchors["capital_reason"] = capital_reason

        # Character floor
        promoter = self.research.get("promoter_background", {})
        if promoter.get("wilful_defaulter"):
            character_floor, character_reason = 10, "HARD STOP: Wilful defaulter"
        elif promoter.get("criminal_cases"):
            character_floor, character_reason = 20, "Criminal cases against promoter"
        elif promoter.get("risk_level") == "Low" and promoter.get("reputation") == "Good":
            character_floor, character_reason = 72, "Clean promoter, good reputation"
        else:
            character_floor, character_reason = 50, "Standard assessment"

        anchors["character_floor"]  = character_floor
        anchors["character_reason"] = character_reason

        # Collateral floor
        if rev and rev > 100000:   collateral_floor = 70
        elif rev and rev > 50000:  collateral_floor = 62
        elif rev and rev > 10000:  collateral_floor = 52
        elif rev and rev > 1000:   collateral_floor = 43
        else:                      collateral_floor = 38

        anchors["collateral_floor"]  = collateral_floor
        anchors["collateral_reason"] = f"Revenue {rev:.0f}Cr inferred asset base" if rev else "No revenue data"

        # External rating anchor
        ext_rating = f.get("external_credit_rating") or ""
        if any(x in str(ext_rating).upper() for x in ["AAA","AA+","AA"]):
            anchors["external_rating_override"] = ext_rating
            anchors["external_rating_floor"]    = 82
        elif any(x in str(ext_rating).upper() for x in ["A+","A "]):
            anchors["external_rating_override"] = ext_rating
            anchors["external_rating_floor"]    = 72

        print(f"  [RatioAnchors] CapacityFloor={capacity_floor}, CapitalFloor={capital_floor}, CharacterFloor={character_floor}")
        return anchors

    # ══════════════════════════════════════════════════════════════════════ #
    # 7. _score_to_rating()
    # ══════════════════════════════════════════════════════════════════════ #
    def _score_to_rating(self, score: float) -> str:
        if score >= 90: return "AAA"
        if score >= 82: return "AA"
        if score >= 75: return "A"
        if score >= 68: return "BBB"
        if score >= 60: return "BB"
        if score >= 50: return "B"
        if score >= 35: return "CCC"
        return "D"

    # ══════════════════════════════════════════════════════════════════════ #
    # 8. _parse_json()
    # ══════════════════════════════════════════════════════════════════════ #
    def _parse_json(self, text: str) -> dict:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*',     '', text)
            return json.loads(text.strip())
        except Exception:
            return {"raw_response": text[:300], "parse_error": True}