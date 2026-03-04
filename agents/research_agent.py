import os
from google import genai
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


class ResearchAgent:
    """
    Digital Credit Manager - automatically researches:
    - Company news and reputation
    - Promoter background
    - Sector headwinds
    - Litigation history
    - Regulatory issues
    """

    def __init__(self, company_name: str, promoter_names: list = None, sector: str = None):
        self.company_name = company_name
        self.promoter_names = promoter_names or []
        self.sector = sector or "manufacturing"
        self.model = "gemini-2.0-flash"
        self.findings = {}

    def run_full_research(self) -> dict:
        """Run all research modules and return consolidated findings"""
        print(f"[ResearchAgent] Starting research for: {self.company_name}")

        self.findings = {
            "company_news": self.research_company_news(),
            "promoter_background": self.research_promoters(),
            "sector_headwinds": self.research_sector(),
            "litigation": self.research_litigation(),
            "regulatory": self.research_regulatory(),
            "mca_signals": self.research_mca(),
            "overall_sentiment": None,
        }

        # final sentiment synthesis
        self.findings["overall_sentiment"] = self.synthesize_findings()
        return self.findings

    def research_company_news(self) -> dict:
        """Search for recent company news"""
        print(f"[ResearchAgent] Searching company news...")
        queries = [
            f"{self.company_name} India news 2024 2025",
            f"{self.company_name} financial results revenue profit India",
            f"{self.company_name} fraud scam default India",
        ]

        all_results = []
        for query in queries:
            try:
                results = tavily.search(
                    query=query,
                    search_depth="basic",
                    max_results=3,
                    include_answer=True,
                )
                all_results.extend(results.get("results", []))
            except Exception as e:
                print(f"[ResearchAgent] Search error: {e}")

        if not all_results:
            return {"found": False, "summary": "No news found"}

        # summarize with Gemini
        news_text = "\n\n".join([
            f"Title: {r.get('title', '')}\nContent: {r.get('content', '')[:500]}"
            for r in all_results[:6]
        ])

        prompt = f"""
        You are a credit analyst. Analyze these news articles about {self.company_name}.
        
        {news_text}
        
        Provide:
        1. Overall sentiment (Positive/Negative/Neutral)
        2. Key positive signals (if any)
        3. Key risk signals (if any)
        4. Any mentions of default, fraud, or financial stress
        5. Recent major events affecting the company
        
        Return ONLY valid JSON with keys: sentiment, positive_signals (list), 
        risk_signals (list), default_mentions (bool), major_events (list), summary (string).
        """

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return self._parse_json(response.text)

    def research_promoters(self) -> dict:
        """Research promoter background and reputation"""
        print(f"[ResearchAgent] Researching promoters...")

        if not self.promoter_names:
            return {"found": False, "summary": "No promoter names provided"}

        all_results = []
        for promoter in self.promoter_names[:2]:  # limit to 2 promoters
            queries = [
                f"{promoter} India businessman director background",
                f"{promoter} fraud case court India",
                f"{promoter} {self.company_name} director",
            ]
            for query in queries:
                try:
                    results = tavily.search(
                        query=query,
                        search_depth="basic",
                        max_results=2,
                    )
                    all_results.extend(results.get("results", []))
                except Exception as e:
                    print(f"[ResearchAgent] Promoter search error: {e}")

        if not all_results:
            return {"found": False, "summary": "No promoter information found"}

        news_text = "\n\n".join([
            f"Title: {r.get('title', '')}\nContent: {r.get('content', '')[:400]}"
                for r in all_results[:6]
        ])

        prompt = f"""
        You are a credit analyst doing due diligence on company promoters.
        Promoters: {', '.join(self.promoter_names)}
        Company: {self.company_name}
        
        News/Articles found:
        {news_text}
        
        Assess:
        1. Promoter reputation (Good/Mixed/Poor)
        2. Any criminal cases or fraud allegations
        3. Other companies they are associated with
        4. Any wilful defaulter mentions
        5. Overall promoter risk level
        
        Return ONLY valid JSON with keys: reputation, criminal_cases (bool), 
        associated_companies (list), wilful_defaulter (bool), 
        risk_level (Low/Medium/High), summary (string).
        """

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return self._parse_json(response.text)

    def research_sector(self) -> dict:
        """Research sector-specific headwinds and tailwinds"""
        print(f"[ResearchAgent] Researching sector: {self.sector}")

        queries = [
            f"{self.sector} sector India outlook 2025 RBI regulations",
            f"{self.sector} industry India challenges headwinds 2025",
            f"RBI regulations {self.sector} NBFC lending India 2025",
        ]

        all_results = []
        for query in queries:
            try:
                results = tavily.search(
                    query=query,
                    search_depth="basic",
                    max_results=3,
                )
                all_results.extend(results.get("results", []))
            except Exception as e:
                print(f"[ResearchAgent] Sector search error: {e}")

        news_text = "\n\n".join([
            f"Title: {r.get('title', '')}\nContent: {r.get('content', '')[:400]}"
            for r in all_results[:6]
        ])

        prompt = f"""
        You are a credit analyst assessing sector risk for Indian lending.
        Sector: {self.sector}
        
        Recent news/reports:
        {news_text}
        
        Assess:
        1. Overall sector health (Strong/Stable/Stressed/Distressed)
        2. Key regulatory risks (RBI, SEBI, sector-specific)
        3. Macroeconomic headwinds
        4. Growth opportunities
        5. Sector risk rating for lending purposes
        
        Return ONLY valid JSON with keys: sector_health, regulatory_risks (list),
        headwinds (list), opportunities (list), 
        lending_risk (Low/Medium/High), summary (string).
        """

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return self._parse_json(response.text)

    def research_litigation(self) -> dict:
        """Search for litigation and legal disputes"""
        print(f"[ResearchAgent] Searching litigation history...")

        queries = [
            f"{self.company_name} court case lawsuit India eCourts",
            f"{self.company_name} NCLT insolvency IBC India",
            f"{self.company_name} DRT debt recovery tribunal India",
        ]

        all_results = []
        for query in queries:
            try:
                results = tavily.search(
                    query=query,
                    search_depth="basic",
                    max_results=3,
                )
                all_results.extend(results.get("results", []))
            except Exception as e:
                print(f"[ResearchAgent] Litigation search error: {e}")

        news_text = "\n\n".join([
            f"Title: {r.get('title', '')}\nContent: {r.get('content', '')[:400]}"
            for r in all_results[:6]
        ])

        prompt = f"""
        You are a credit analyst assessing legal risk for {self.company_name} in India.
        
        Search results:
        {news_text}
        
        Assess:
        1. Active litigation cases
        2. NCLT/IBC insolvency proceedings
        3. DRT (Debt Recovery Tribunal) cases
        4. Tax disputes (Income Tax, GST)
        5. Overall litigation risk
        
        Return ONLY valid JSON with keys: active_cases (list), nclt_proceedings (bool),
        drt_cases (bool), tax_disputes (bool), 
        litigation_risk (Low/Medium/High), summary (string).
        """

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return self._parse_json(response.text)

    def research_regulatory(self) -> dict:
        """Check for regulatory actions and compliance issues"""
        print(f"[ResearchAgent] Checking regulatory compliance...")

        queries = [
            f"{self.company_name} SEBI action penalty India",
            f"{self.company_name} RBI penalty non-compliance India",
            f"{self.company_name} MCA ROC notice India",
        ]

        all_results = []
        for query in queries:
            try:
                results = tavily.search(
                    query=query,
                    search_depth="basic",
                    max_results=2,
                )
                all_results.extend(results.get("results", []))
            except Exception as e:
                print(f"[ResearchAgent] Regulatory search error: {e}")

        news_text = "\n\n".join([
            f"Title: {r.get('title', '')}\nContent: {r.get('content', '')[:400]}"
            for r in all_results[:4]
        ])

        prompt = f"""
        Check regulatory compliance status for {self.company_name} in India.
        
        Search results:
        {news_text}
        
        Assess:
        1. SEBI actions or penalties
        2. RBI non-compliance issues
        3. MCA/ROC filing defaults
        4. Environmental compliance issues
        5. Overall regulatory risk
        
        Return ONLY valid JSON with keys: sebi_actions (bool), rbi_issues (bool),
        mca_defaults (bool), env_issues (bool),
        regulatory_risk (Low/Medium/High), summary (string).
        """

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return self._parse_json(response.text)

    def research_mca(self) -> dict:
        """
        Research MCA21 signals - Indian specific
        Checks for director disqualification, charge satisfaction etc.
        """
        print(f"[ResearchAgent] Checking MCA signals...")

        queries = [
            f"{self.company_name} MCA21 director disqualification India",
            f"{self.company_name} charge satisfaction hypothecation MCA",
            f"{self.company_name} annual return filing default ROC",
        ]

        all_results = []
        for query in queries:
            try:
                results = tavily.search(
                    query=query,
                    search_depth="basic",
                    max_results=2,
                )
                all_results.extend(results.get("results", []))
            except Exception as e:
                print(f"[ResearchAgent] MCA search error: {e}")

        news_text = "\n\n".join([
            f"Title: {r.get('title', '')}\nContent: {r.get('content', '')[:300]}"
            for r in all_results[:4]
        ])

        prompt = f"""
        Analyze MCA21 related signals for {self.company_name} India.
        
        Search results:
        {news_text}
        
        Check:
        1. Director disqualification status
        2. Charge creation/satisfaction status
        3. Annual return filing compliance
        4. Any striking off notices
        5. Overall MCA compliance
        
        Return ONLY valid JSON with keys: director_disqualified (bool),
        charge_issues (bool), filing_defaults (bool), 
        striking_off_risk (bool), mca_risk (Low/Medium/High), summary (string).
        """

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return self._parse_json(response.text)

    def synthesize_findings(self) -> dict:
        """Synthesize all research into overall risk assessment"""
        print(f"[ResearchAgent] Synthesizing all findings...")

        findings_summary = {}
        for key, value in self.findings.items():
            if isinstance(value, dict) and "summary" in value:
                findings_summary[key] = value["summary"]

        prompt = f"""
        You are a senior credit analyst at an Indian NBFC (like Vivriti Capital).
        
        Research findings for {self.company_name}:
        {findings_summary}
        
        Provide a consolidated risk assessment:
        1. Overall company risk rating (AAA/AA/A/BBB/BB/B/CCC/D)
        2. Top 3 risk factors
        3. Top 3 positive factors  
        4. Recommended due diligence actions
        5. Preliminary lending recommendation (Proceed/Caution/Reject)
        
        Return ONLY valid JSON with keys: risk_rating, top_risks (list of 3),
        positive_factors (list of 3), due_diligence_actions (list),
        preliminary_recommendation, recommendation_reason (string).
        """

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return self._parse_json(response.text)

    def _parse_json(self, text: str) -> dict:
        """Safely parse Gemini JSON response"""
        import json
        import re
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()
            return json.loads(text)
        except Exception:
            return {"raw_response": text, "parse_error": True}