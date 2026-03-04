import os
from google import genai
from utils.prompt_loader import PromptLoader
from dotenv import load_dotenv
import json
import re

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class ScoringAgent:
    """
    Implements the Five Cs of Credit framework for Indian corporate lending.
    Produces an explainable risk score with loan amount and rate recommendations.
    
    Five Cs: Character, Capacity, Capital, Collateral, Conditions
    """

    def __init__(
        self,
        company_name: str,
        financials: dict,
        research: dict,
        manual_notes: str = ""
    ):
        self.company_name = company_name
        self.financials = financials
        self.research = research
        self.manual_notes = manual_notes
        self.model = "gemini-2.0-flash"

    def run(self) -> dict:
        """Run full scoring pipeline"""
        print(f"[ScoringAgent] Scoring {self.company_name}...")

        five_cs = self.score_five_cs()
        risk_score = self.calculate_risk_score(five_cs)
        recommendation = self.generate_recommendation(five_cs, risk_score)

        return {
            "five_cs": five_cs,
            "risk_score": risk_score,
            "recommendation": recommendation,
        }

    def score_five_cs(self) -> dict:
        """Score each of the Five Cs using Gemini"""
        print(f"[ScoringAgent] Scoring Five Cs...")

        prompt = PromptLoader.load("scoring", "five_cs", {
            "company_name": self.company_name,
            "financials": json.dumps(self.financials, indent=2)[:2000],
            "research": json.dumps(self.research, indent=2)[:2000],
            "manual_notes": self.manual_notes or "No manual notes provided.",
        })

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return self._parse_json(response.text)

    def calculate_risk_score(self, five_cs: dict) -> dict:
        """
        Calculate weighted risk score from Five Cs.
        Weights based on Indian NBFC lending practices:
        - Capacity: 30% (most important - can they repay?)
        - Character: 25% (promoter integrity is critical in India)
        - Capital: 20% (financial strength)
        - Collateral: 15% (security coverage)
        - Conditions: 10% (external environment)
        """
        weights = {
            "capacity": 0.30,
            "character": 0.25,
            "capital": 0.20,
            "collateral": 0.15,
            "conditions": 0.10,
        }

        scores = {
            "capacity": five_cs.get("capacity_score", 50),
            "character": five_cs.get("character_score", 50),
            "capital": five_cs.get("capital_score", 50),
            "collateral": five_cs.get("collateral_score", 50),
            "conditions": five_cs.get("conditions_score", 50),
        }

        # weighted score
        weighted_score = sum(
            scores[c] * weights[c] for c in weights
        )

        # apply red flag penalties
        penalty = self._calculate_penalties()
        final_score = max(0, weighted_score - penalty)

        # map to rating
        rating = self._score_to_rating(final_score)

        return {
            "raw_scores": scores,
            "weights": weights,
            "weighted_score": round(weighted_score, 2),
            "penalty_applied": penalty,
            "final_score": round(final_score, 2),
            "rating": rating,
            "score_breakdown": {
                c: {
                    "score": scores[c],
                    "weight": weights[c],
                    "contribution": round(scores[c] * weights[c], 2)
                }
                for c in weights
            }
        }

    def generate_recommendation(
        self,
        five_cs: dict,
        risk_score: dict
    ) -> dict:
        """Generate final lending recommendation with loan amount and rate"""
        print(f"[ScoringAgent] Generating recommendation...")

        prompt = PromptLoader.load("scoring", "risk_score", {
            "company_name": self.company_name,
            "five_cs_summary": json.dumps(five_cs, indent=2)[:1500],
            "risk_score": json.dumps(risk_score, indent=2),
            "manual_notes": self.manual_notes or "None",
            "financials": json.dumps(self.financials, indent=2)[:1000],
        })

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        result = self._parse_json(response.text)

        # add score context to result
        result["final_score"] = risk_score["final_score"]
        result["rating"] = risk_score["rating"]
        return result

    def adjust_for_manual_notes(self, new_notes: str) -> dict:
        """
        Re-score when credit officer adds new manual notes.
        This is the real-time adjustment feature.
        """
        print(f"[ScoringAgent] Adjusting score for manual notes...")
        self.manual_notes = new_notes
        return self.run()

    def _calculate_penalties(self) -> float:
        """Apply score penalties for critical red flags"""
        penalty = 0.0

        # check research findings for hard stops
        research_flat = json.dumps(self.research).lower()

        # hard penalties - Indian lending context
        if "wilful default" in research_flat:
            penalty += 30  # automatic near-rejection
        if "nclt" in research_flat or "insolvency" in research_flat:
            penalty += 25
        if "fraud" in research_flat or "cbi" in research_flat:
            penalty += 20
        if "npa" in research_flat:
            penalty += 15
        if "going concern" in research_flat:
            penalty += 15
        if "circular trading" in research_flat:
            penalty += 10
        if "audit qualified" in research_flat:
            penalty += 10
        if "drt" in research_flat:
            penalty += 8

        # check manual notes for negative signals
        if self.manual_notes:
            notes_lower = self.manual_notes.lower()
            if any(w in notes_lower for w in [
                "capacity", "idle", "shutdown", "closed"
            ]):
                penalty += 10
            if any(w in notes_lower for w in [
                "evasive", "uncooperative", "refused"
            ]):
                penalty += 8

        return penalty

    def _score_to_rating(self, score: float) -> str:
        """Convert numeric score to credit rating"""
        if score >= 90:
            return "AAA"
        elif score >= 82:
            return "AA"
        elif score >= 75:
            return "A"
        elif score >= 68:
            return "BBB"
        elif score >= 60:
            return "BB"
        elif score >= 50:
            return "B"
        elif score >= 35:
            return "CCC"
        else:
            return "D"

    def _parse_json(self, text: str) -> dict:
        """Safely parse Gemini JSON response"""
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()
            return json.loads(text)
        except Exception:
            return {"raw_response": text, "parse_error": True}