import os
import re
import json
import time
from google import genai
from google.genai.errors import ServerError, ClientError
from dotenv import load_dotenv

load_dotenv()

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

_research_cache: dict = {}


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


class ResearchAgent:
    """
    The Digital Credit Manager — satisfies hackathon Research Agent requirement.

    Targets the SPECIFIC external intelligence sources mentioned in the problem statement:
    - News reports on sector trends
    - MCA (Ministry of Corporate Affairs) filings
    - Legal disputes on the e-Courts portal
    - Promoter background
    - RBI/SEBI regulatory actions
    - CRISIL/ICRA/CARE credit ratings

    Data sourcing approach:
      This agent uses Tavily web search to gather public intelligence across all domains.
      Direct API access to MCA21, e-Courts (ecourts.gov.in), and CIBIL is not available
      in this hackathon environment because:
        - MCA21 has no public API (only paid data vendors like Tofler/Zaubacorp)
        - e-Courts requires captcha-based manual lookup
        - CIBIL Commercial reports require institutional access agreements
      Instead, we search the public web for the same signals (e.g., "NCLT order" via
      news articles, "director DIN disqualification" via MCA press releases, etc.).
      In a production deployment, integrate with:
        - MCA21 V3 API (via registered information utility)
        - NCLAT/NCLT order database (paid legal tech providers like Manupatra/SCC)
        - CIBIL Commercial Bureau API (institutional subscriber access)
    """

    def __init__(self, company_name: str, sector: str = "", promoters: str = ""):
        self.company_name = company_name
        self.sector       = sector or "Manufacturing"
        self.promoters    = promoters
        self.model        = "gemini-2.5-flash"
        self.client       = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.tavily       = TavilyClient(api_key=os.getenv("TAVILY_API_KEY")) if TAVILY_AVAILABLE else None

    # ------------------------------------------------------------------ #
    def run(self) -> dict:
        cache_key = self.company_name.lower().strip()
        if cache_key in _research_cache:
            print(f"[ResearchAgent] Cache hit for {self.company_name}")
            return _research_cache[cache_key]

        print(f"[ResearchAgent] Starting deep research: {self.company_name}")
        raw_results = self._gather_intelligence()
        synthesis   = self._synthesize(raw_results)
        _research_cache[cache_key] = synthesis
        return synthesis

    # ------------------------------------------------------------------ #
    def _gather_intelligence(self) -> dict[str, list[str]]:
        """
        Run targeted searches against the 5 intelligence domains
        specified in the hackathon problem statement.
        Returns dict of domain → list of snippets.
        """
        if not self.tavily:
            print("[ResearchAgent] Tavily not available — returning empty intelligence")
            return {}

        # Problem statement specifies these EXACT domains:
        search_domains = {
            # 1. Company news and financial health
            "company_news": [
                f"{self.company_name} latest news India 2024 2025",
                f"{self.company_name} financial results revenue profit 2025",
                f"{self.company_name} CRISIL ICRA CARE credit rating",
            ],
            # 2. Promoter background (character assessment)
            "promoter_background": [
                f"{self.company_name} promoters directors background India",
                f"{self.promoters} wilful defaulter CIBIL" if self.promoters else f"{self.company_name} promoter default",
            ],
            # 3. MCA filings — explicitly mentioned in problem statement
            "mca_filings": [
                f"{self.company_name} MCA Ministry Corporate Affairs filing India",
                f"{self.company_name} MCA21 director disqualification ROC filing",
            ],
            # 4. e-Courts / legal disputes — explicitly mentioned in problem statement
            "legal_disputes": [
                f"{self.company_name} NCLT DRT court case India litigation 2024 2025",
                f"{self.company_name} legal dispute e-courts India arbitration",
                f"{self.company_name} insolvency proceedings IBC CIRP",
            ],
            # 5. Sector headwinds and RBI regulations
            "sector_regulatory": [
                f"{self.sector} sector India RBI regulations 2025 headwinds",
                f"{self.company_name} SEBI regulatory action order 2024 2025",
                f"RBI {self.sector} lending norms circular 2025",
            ],
        }

        all_results: dict[str, list[str]] = {}

        for domain, queries in search_domains.items():
            domain_snippets = []
            for q in queries:
                try:
                    r = self.tavily.search(
                        query=q,
                        max_results=3,
                        search_depth="basic",
                    )
                    for item in r.get("results", []):
                        snippet = item.get("content", "")[:600]
                        url     = item.get("url", "")
                        if snippet:
                            domain_snippets.append(f"[Source: {url}]\n{snippet}")
                    time.sleep(1.0)  # Rate limit protection
                except Exception as e:
                    print(f"[ResearchAgent] Tavily error for '{q}': {e}")

            all_results[domain] = domain_snippets
            print(f"  [ResearchAgent] {domain}: {len(domain_snippets)} snippets")

        return all_results

    # ------------------------------------------------------------------ #
    def _synthesize(self, raw_results: dict[str, list[str]]) -> dict:
        """Synthesize all intelligence into structured JSON using Gemini."""

        # Build combined text per domain
        sections = []
        for domain, snippets in raw_results.items():
            if snippets:
                sections.append(f"\n### {domain.upper().replace('_',' ')}\n" + "\n\n".join(snippets[:4]))

        combined = "\n".join(sections)[:7000]

        prompt = f"""
You are a senior credit research analyst at Vivriti Capital, an Indian NBFC.
Synthesise the following intelligence about {self.company_name} into a structured credit risk report.

Company: {self.company_name}
Sector: {self.sector}
Promoters: {self.promoters or "Not specified"}

Intelligence gathered (from news, MCA filings, e-Courts, SEBI, RBI):
{combined}

IMPORTANT ANALYSIS RULES:
1. MCA signals: Check for director disqualification, ROC filing defaults, charge satisfaction
2. e-Courts / NCLT: Distinguish between (a) insolvency/IBC proceedings [HIGH RISK] vs
   (b) demerger/restructuring schemes [NEUTRAL] vs (c) subsidiary debt recovery [LOW RISK]
3. SEBI: Check for enforcement orders, settlement orders, insider trading, disclosure failures
4. RBI: Check for bank / NBFC licence issues, regulatory directions, penalties
5. Credit ratings: CRISIL/ICRA/CARE/Brickwork — note the exact rating and outlook
6. Promoter: Look specifically for wilful defaulter lists, SFIO investigations, criminal cases
7. Sector: Note specific RBI sectoral limits, NBFC exposure norms for this sector

Return ONLY valid JSON. No markdown. No thinking tokens. null for unknown.
{{
    "company_news": {{
        "sentiment": "Positive/Negative/Mixed/Neutral",
        "positive_signals": [],
        "risk_signals": [],
        "default_mentions": false,
        "major_events": [],
        "external_credit_rating": null,
        "summary": ""
    }},
    "promoter_background": {{
        "reputation": "Good/Moderate/Poor",
        "criminal_cases": false,
        "wilful_defaulter": false,
        "sfio_investigation": false,
        "risk_level": "Low/Medium/High",
        "summary": ""
    }},
    "mca_signals": {{
        "director_disqualified": false,
        "filing_defaults": false,
        "charge_satisfaction_pending": false,
        "roc_notices": false,
        "mca_risk": "Low/Medium/High",
        "summary": ""
    }},
    "legal_disputes": {{
        "ecourts_cases": [],
        "nclt_proceedings": false,
        "nclt_type": null,
        "drt_cases": false,
        "ibc_cirp": false,
        "arbitration_cases": [],
        "litigation_risk": "Low/Medium/High",
        "summary": ""
    }},
    "regulatory": {{
        "sebi_actions": false,
        "sebi_settlement": false,
        "rbi_issues": false,
        "rbi_penalty": false,
        "mca_defaults": false,
        "regulatory_risk": "Low/Medium/High",
        "summary": ""
    }},
    "sector_headwinds": {{
        "sector_health": "Strong/Stable/Stressed/Distressed",
        "rbi_sector_restrictions": [],
        "regulatory_risks": [],
        "headwinds": [],
        "tailwinds": [],
        "lending_risk": "Low/Medium/High",
        "summary": ""
    }},
    "overall_sentiment": {{
        "risk_rating": "A/B/C/D",
        "top_risks": [],
        "positive_factors": [],
        "early_warning_signals": [],
        "preliminary_recommendation": "Proceed/Caution/Reject",
        "recommendation_reason": ""
    }}
}}
"""
        try:
            time.sleep(3)
            response = _gemini_with_retry(self.client, self.model, prompt)
            raw      = re.sub(r'<think>.*?</think>', '', response.text, flags=re.DOTALL).strip()
            result   = self._parse_json(raw)

            # Promote external_credit_rating to top level for scoring agent
            ext_rating = result.get("company_news", {}).get("external_credit_rating")
            if ext_rating:
                result["external_credit_rating"] = ext_rating

            # Normalise litigation field name for backward compatibility
            if "legal_disputes" in result and "litigation" not in result:
                result["litigation"] = result["legal_disputes"]

            return result

        except Exception as e:
            print(f"[ResearchAgent] Synthesis error: {e}")
            return self._empty_research()

    # ------------------------------------------------------------------ #
    def _empty_research(self) -> dict:
        return {
            "company_news":      {"sentiment": "Unknown", "summary": "Research unavailable"},
            "promoter_background": {"reputation": "Unknown", "wilful_defaulter": False, "criminal_cases": False, "risk_level": "Medium"},
            "mca_signals":       {"director_disqualified": False, "filing_defaults": False, "mca_risk": "Low"},
            "legal_disputes":    {"nclt_proceedings": False, "drt_cases": False, "litigation_risk": "Low", "summary": ""},
            "litigation":        {"nclt_proceedings": False, "drt_cases": False, "litigation_risk": "Low", "summary": ""},
            "regulatory":        {"sebi_actions": False, "rbi_issues": False, "mca_defaults": False, "regulatory_risk": "Low"},
            "sector_headwinds":  {"sector_health": "Stable", "lending_risk": "Medium", "summary": ""},
            "overall_sentiment": {"risk_rating": "B", "top_risks": [], "positive_factors": [], "early_warning_signals": [], "preliminary_recommendation": "Caution"},
            "research_unavailable": True,
        }

    # ------------------------------------------------------------------ #
    def _parse_json(self, text: str) -> dict:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*',     '', text)
            return json.loads(text.strip())
        except Exception:
            return self._empty_research()