import os
import re
import json
import time
from google import genai
from google.genai.errors import ServerError, ClientError
from utils.prompt_loader import PromptLoader
from dotenv import load_dotenv

load_dotenv()


def _gemini_with_retry(client, model: str, contents,
                        max_retries: int = 5,
                        fallback: str = "gemini-2.0-flash-lite"):
    for attempt in range(max_retries):
        current_model = fallback if attempt == max_retries - 1 else model
        try:
            return client.models.generate_content(
                model=current_model,
                contents=contents
            )
        except ServerError:
            if attempt == max_retries - 1:
                raise
            wait = 8 * (2 ** attempt)
            print(f"[Gemini] 503 — retrying in {wait}s "
                  f"(attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)
        except ClientError as e:
            if "429" in str(e):
                if attempt == max_retries - 1:
                    raise
                wait = 10 * (2 ** attempt)
                print(f"[Gemini] 429 — retrying in {wait}s")
                time.sleep(wait)
            else:
                raise


class ScoringAgent:
    def __init__(
        self,
        company_name: str,
        financials:   dict,
        research:     dict,
        manual_notes: str = "",
    ):
        self.company_name = company_name
        self.financials   = financials
        self.research     = research
        self.manual_notes = manual_notes
        self.model        = "gemini-2.5-flash"
        self.client       = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def run(self) -> dict:
        print(f"[ScoringAgent] Scoring {self.company_name}...")
        five_cs        = self.score_five_cs()
        risk_score     = self.calculate_risk_score(five_cs)
        recommendation = self.generate_recommendation(five_cs, risk_score)
        return {
            "five_cs":        five_cs,
            "risk_score":     risk_score,
            "recommendation": recommendation,
        }

    def score_five_cs(self) -> dict:
        print("[ScoringAgent] Scoring Five Cs...")

        fin_summary = json.dumps(self.financials, indent=2)[:2000]
        res_summary = json.dumps(self.research,   indent=2)[:2000]

        prompt = f"""
You are a senior credit analyst at Vivriti Capital, an Indian NBFC.
Score each of the Five Cs of Credit for: {self.company_name}

Financial data:
{fin_summary}

Research findings:
{res_summary}

Credit officer field notes:
{self.manual_notes or "No field notes provided."}

Indian NBFC scoring context:
- Capacity (30% weight): Revenue trend, EBITDA margin, DSCR, cash flow adequacy
- Character (25% weight): Promoter track record, governance, no wilful default
- Capital (20% weight): Net worth, debt-equity ratio, leverage
- Collateral (15% weight): Asset quality, security coverage, encumbrances
- Conditions (10% weight): Sector health, macro environment, RBI regulations

Scoring guidelines:
- 80-100: Excellent — strong evidence supporting this C
- 60-79:  Good — adequate with minor concerns
- 40-59:  Moderate — significant concerns, needs monitoring
- 20-39:  Poor — major deficiencies identified
- 0-19:   Critical — severe issues, near-rejection territory

NOTE: If financial data is partially missing (nulls), score conservatively
but do NOT score 0 if any data is available. Use available data + research.

Return ONLY valid JSON:
{{
    "character_score": 0,
    "character_rationale": "",
    "capacity_score": 0,
    "capacity_rationale": "",
    "capital_score": 0,
    "capital_rationale": "",
    "collateral_score": 0,
    "collateral_rationale": "",
    "conditions_score": 0,
    "conditions_rationale": ""
}}

Return ONLY the JSON. No explanation.
"""
        time.sleep(3)
        response = _gemini_with_retry(self.client, self.model, prompt)
        return self._parse_json(response.text)

    def calculate_risk_score(self, five_cs: dict) -> dict:
        weights = {
            "capacity":   0.30,
            "character":  0.25,
            "capital":    0.20,
            "collateral": 0.15,
            "conditions": 0.10,
        }
        scores = {
            "capacity":   five_cs.get("capacity_score",   50),
            "character":  five_cs.get("character_score",  50),
            "capital":    five_cs.get("capital_score",    50),
            "collateral": five_cs.get("collateral_score", 50),
            "conditions": five_cs.get("conditions_score", 50),
        }

        weighted_score = sum(scores[c] * weights[c] for c in weights)
        penalty        = self._calculate_penalties()
        final_score    = max(0, weighted_score - penalty)
        rating         = self._score_to_rating(final_score)

        return {
            "raw_scores":    scores,
            "weights":       weights,
            "weighted_score": round(weighted_score, 2),
            "penalty_applied": penalty,
            "final_score":   round(final_score, 2),
            "rating":        rating,
            "score_breakdown": {
                c: {
                    "score":        scores[c],
                    "weight":       weights[c],
                    "contribution": round(scores[c] * weights[c], 2),
                }
                for c in weights
            },
        }

    def generate_recommendation(self, five_cs: dict,
                                  risk_score: dict) -> dict:
        print("[ScoringAgent] Generating recommendation...")

        prompt = f"""
You are a senior credit officer at Vivriti Capital, an Indian NBFC.
Make a final lending recommendation for: {self.company_name}

Five Cs Assessment:
{json.dumps(five_cs, indent=2)[:1500]}

Risk Score: {risk_score['final_score']}/100
Rating: {risk_score['rating']}
Penalties Applied: {risk_score['penalty_applied']} points
Score Breakdown: {json.dumps(risk_score['score_breakdown'])}

Manual field notes: {self.manual_notes or "None"}

Requested loan: {self.financials.get('basic_info', {}).get('loan_amount', 'Not specified')}

Decision rules:
- Score >= 75 → APPROVE
- Score 50-74 → CONDITIONAL_APPROVE (with specific conditions)
- Score < 50  → REJECT (unless strong override reason)
- Rating CCC/D → REJECT automatically

Interest rate = Base 10.5% + risk premium:
- AAA/AA: +0.5% to +1.0%
- A/BBB:  +1.5% to +2.5%
- BB/B:   +3.0% to +5.0%
- CCC/D:  N/A (reject)

Loan amount: start from requested amount, reduce based on risk.
For CONDITIONAL_APPROVE: reduce by 20-50% based on risk level.

Return ONLY valid JSON:
{{
    "decision": "APPROVE/CONDITIONAL_APPROVE/REJECT",
    "decision_rationale": "",
    "recommended_amount_crores": null,
    "interest_rate_percent": null,
    "tenure_months": null,
    "key_conditions": [],
    "rejection_reason": null
}}

Return ONLY the JSON. No explanation.
"""
        time.sleep(3)
        response = _gemini_with_retry(self.client, self.model, prompt)
        result   = self._parse_json(response.text)

        # always attach score and rating
        result["final_score"] = risk_score["final_score"]
        result["rating"]      = risk_score["rating"]
        return result

    def adjust_for_manual_notes(self, new_notes: str) -> dict:
        self.manual_notes = new_notes
        return self.run()

    def _calculate_penalties(self) -> float:
        penalty      = 0.0
        research_str = json.dumps(self.research).lower()
        fin_str      = json.dumps(self.financials).lower()
        combined     = research_str + fin_str

        penalty_rules = [
            ("wilful default",              30),
            ("nclt",                        25),
            ("insolvency",                  20),
            ("fraud",                       20),
            ("cbi",                         20),
            ("npa",                         15),
            ("going concern",               15),
            ("circular trading",            10),
            ("audit qualified",             10),
            ("drt",                          8),
        ]
        for keyword, points in penalty_rules:
            if keyword in combined:
                penalty += points

        if self.manual_notes:
            notes_lower = self.manual_notes.lower()
            if any(w in notes_lower for w in
                   ["capacity", "idle", "shutdown", "closed", "40%", "20%"]):
                penalty += 10
            if any(w in notes_lower for w in
                   ["evasive", "uncooperative", "refused", "not available"]):
                penalty += 8
            if any(w in notes_lower for w in
                   ["inflated", "mismatch", "discrepancy"]):
                penalty += 12

        return penalty

    def _score_to_rating(self, score: float) -> str:
        if score >= 90: return "AAA"
        if score >= 82: return "AA"
        if score >= 75: return "A"
        if score >= 68: return "BBB"
        if score >= 60: return "BB"
        if score >= 50: return "B"
        if score >= 35: return "CCC"
        return "D"

    def _parse_json(self, text: str) -> dict:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            return json.loads(text.strip())
        except Exception:
            return {"raw_response": text[:200], "parse_error": True}