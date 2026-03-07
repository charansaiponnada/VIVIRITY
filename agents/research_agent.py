import os
import re
import json
import time
from google import genai
from google.genai.errors import ServerError, ClientError
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def _gemini_with_retry(client, model: str, contents,
                        max_retries: int = 5,
                        fallback: str = "gemini-2.5-flash"):
    """
    Retry Gemini calls on 503 (overloaded) and 429 (rate limit).
    Exponential backoff: 8s → 16s → 32s → 64s
    Falls back to gemini-2.5-flash on the last attempt.
    """
    for attempt in range(max_retries):
        current_model = fallback if attempt == max_retries - 1 else model
        try:
            return client.models.generate_content(
                model=current_model,
                contents=contents
            )
        except ServerError as e:
            if attempt == max_retries - 1:
                raise
            wait = 8 * (2 ** attempt)
            print(f"[Gemini] 503 overloaded — retrying in {wait}s "
                  f"(attempt {attempt + 1}/{max_retries}"
                  f"{', switching to fallback' if attempt == max_retries - 2 else ''})")
            time.sleep(wait)
        except ClientError as e:
            if "429" in str(e):
                if attempt == max_retries - 1:
                    raise
                wait = 10 * (2 ** attempt)
                print(f"[Gemini] 429 rate limit — retrying in {wait}s")
                time.sleep(wait)
            else:
                raise


class ResearchAgent:
    def __init__(
        self,
        company_name: str,
        promoter_names: list = None,
        sector: str = None,
    ):
        self.company_name   = company_name
        self.promoter_names = promoter_names or []
        self.sector         = sector or "manufacturing"
        self.model          = "gemini-2.5-flash"
        self.client         = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.findings       = {}

    def run_full_research(self) -> dict:
        """
        1 Gemini call + 5 Tavily searches.
        Retry on 503/429 with exponential backoff.
        """
        print(f"[ResearchAgent] Researching: {self.company_name}")

        # ── Web searches ──────────────────────────────────────
        all_results = []
        queries = [
            f"{self.company_name} India news fraud default NPA 2024 2025",
            f"{self.company_name} court NCLT litigation India 2024 2025",
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
            f"Content: {r.get('content', '')[:400]}"
            for r in all_results[:10]
        ])

        # ── Single Gemini synthesis call ──────────────────────
        prompt = f"""
You are a senior credit analyst at Vivriti Capital, an Indian NBFC.
Company: {self.company_name}
Promoters: {', '.join(self.promoter_names) if self.promoter_names else 'Unknown'}
Sector: {self.sector}

Web research findings:
{news_text}

Indian lending context:
- Wilful defaulter = automatic reject under RBI norms
- NCLT/IBC proceedings = serious insolvency risk
- DRT case = debt recovery action, significant risk
- SEBI penalty = governance concern (assess severity)
- RBI compounding fee = regulatory non-compliance
- CBI/ED investigation = criminal proceedings, high risk
- Promoter pledge of shares > 50% = early warning signal

Analyze and return ONLY valid JSON:
{{
    "company_news": {{
        "sentiment": "Positive/Negative/Neutral/Mixed",
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
        "risk_rating": "AAA/AA/A/BBB/BB/B/CCC",
        "top_risks": [],
        "positive_factors": [],
        "preliminary_recommendation": "Proceed/Caution/Reject",
        "recommendation_reason": ""
    }}
}}

Return ONLY the JSON. No explanation, no markdown.
"""
        time.sleep(3)
        response = _gemini_with_retry(self.client, self.model, prompt)
        result   = self._parse_json(response.text)
        self.findings = result
        return result

    def _parse_json(self, text: str) -> dict:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            return json.loads(text.strip())
        except Exception:
            return {"raw_response": text[:200], "parse_error": True}