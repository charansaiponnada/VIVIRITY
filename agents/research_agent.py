import os
import time
import re
import json
from google import genai
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


class ResearchAgent:
    def __init__(
        self,
        company_name: str,
        promoter_names: list = None,
        sector: str = None
    ):
        self.company_name = company_name
        self.promoter_names = promoter_names or []
        self.sector = sector or "manufacturing"
        self.model = "gemini-2.5-flash"
        self.findings = {}

    def run_full_research(self) -> dict:
        """Optimized - 1 Gemini call instead of 7"""
        print(f"[ResearchAgent] Researching: {self.company_name}")

        # batch all web searches first
        all_results = []
        queries = [
            f"{self.company_name} India news fraud default NPA 2024 2025",
            f"{self.company_name} court case NCLT litigation India",
            f"{self.company_name} SEBI RBI MCA penalty India",
            f"{self.sector} sector India outlook RBI regulations 2025",
        ]

        if self.promoter_names:
            queries.append(
                f"{' '.join(self.promoter_names[:2])} "
                f"director fraud wilful default India"
            )

        for query in queries:
            try:
                time.sleep(1)
                results = tavily.search(
                    query=query,
                    search_depth="basic",
                    max_results=2,
                )
                all_results.extend(results.get("results", []))
            except Exception as e:
                print(f"[ResearchAgent] Search error: {e}")

        news_text = "\n\n".join([
            f"Title: {r.get('title', '')}\n"
            f"Content: {r.get('content', '')[:300]}"
            for r in all_results[:8]
        ])

        # single Gemini call for all research
        time.sleep(4)
        prompt = f"""
You are a senior credit analyst at Vivriti Capital, an Indian NBFC.
Company: {self.company_name}
Promoters: {', '.join(self.promoter_names) if self.promoter_names else 'Unknown'}
Sector: {self.sector}

Web research findings:
{news_text}

Analyze and return ONLY valid JSON with these exact keys:
{{
    "company_news": {{
        "sentiment": "Positive/Negative/Neutral",
        "positive_signals": [],
        "risk_signals": [],
        "default_mentions": false,
        "major_events": [],
        "summary": ""
    }},
    "promoter_background": {{
        "reputation": "Good/Mixed/Poor",
        "criminal_cases": false,
        "wilful_defaulter": false,
        "risk_level": "Low/Medium/High",
        "summary": ""
    }},
    "sector_headwinds": {{
        "sector_health": "Strong/Stable/Stressed/Distressed",
        "regulatory_risks": [],
        "headwinds": [],
        "lending_risk": "Low/Medium/High",
        "summary": ""
    }},
    "litigation": {{
        "active_cases": [],
        "nclt_proceedings": false,
        "drt_cases": false,
        "litigation_risk": "Low/Medium/High",
        "summary": ""
    }},
    "regulatory": {{
        "sebi_actions": false,
        "rbi_issues": false,
        "mca_defaults": false,
        "regulatory_risk": "Low/Medium/High",
        "summary": ""
    }},
    "mca_signals": {{
        "director_disqualified": false,
        "filing_defaults": false,
        "mca_risk": "Low/Medium/High",
        "summary": ""
    }},
    "overall_sentiment": {{
        "risk_rating": "A/BBB/BB/B/CCC",
        "top_risks": [],
        "positive_factors": [],
        "preliminary_recommendation": "Proceed/Caution/Reject",
        "recommendation_reason": ""
    }}
}}

Return ONLY the JSON. No explanation.
        """

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        result = self._parse_json(response.text)
        self.findings = result
        return result

    def _parse_json(self, text: str) -> dict:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()
            return json.loads(text)
        except Exception:
            return {"raw_response": text, "parse_error": True}