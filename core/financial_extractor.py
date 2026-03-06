import re
import os
import time
from google import genai
from core.pdf_parser import PageIndexParser
from dotenv import load_dotenv

load_dotenv()

JSON_SCHEMA = """{
    "basic_info": {
        "company_name": null, "cin": null, "address": null,
        "directors": [], "business_nature": null,
        "incorporation_year": null, "source_page": null
    },
    "financials": {
        "revenue_current": null, "revenue_previous": null,
        "ebitda": null, "pat": null, "total_assets": null,
        "net_worth": null, "total_debt": null,
        "current_ratio": null, "debt_to_equity": null,
        "source_page": null
    },
    "debt_profile": {
        "lenders": [], "secured_loans": null,
        "unsecured_loans": null, "collateral": null,
        "covenant_violations": null, "npa_mention": false,
        "source_page": null
    },
    "gst_analysis": {
        "gst_numbers": [], "total_gst_paid": null,
        "gstr_mismatch_detected": false, "mismatch_details": null,
        "circular_trading_risk": false, "gst_notices": [],
        "source_page": null
    },
    "red_flags": {
        "red_flags": [], "litigation_count": 0,
        "audit_qualified": false, "going_concern_issue": false,
        "severity": "low", "source_page": null
    }
}"""


class FinancialExtractor:
    def __init__(self, parser: PageIndexParser):
        self.parser = parser
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model  = "gemini-2.5-flash"

    def extract_all(self) -> dict:
        """
        Routes to the right extraction strategy based on document size.
        Large PDFs (>50 pages): two-pass targeted extraction
        Small PDFs (<50 pages): standard text extraction
        """
        if self.parser.is_large:
            return self._extract_large_pdf()
        return self._extract_small_pdf()

    def _extract_large_pdf(self) -> dict:
        """
        For large PDFs (annual reports, 100-600 pages).
        Uses two-pass PageIndex result — targeted pages already
        extracted by parser. Section-aware, page-cited, fast.
        """
        # section-aware query: 2 pages per key section
        section_queries = {
            "identity":   "company name CIN directors promoter incorporated",
            "financials": "revenue profit EBITDA PAT turnover balance sheet",
            "debt":       "borrowings loans debt collateral secured unsecured",
            "compliance": "GST litigation audit penalty going concern",
        }

        seen_pages      = set()
        selected_text   = []
        selected_tables = []

        for section, query in section_queries.items():
            pages = self.parser.query(query)
            for p in pages[:2]:
                pnum = p.get("page_number", p["page"])
                if pnum not in seen_pages:
                    seen_pages.add(pnum)
                    selected_text.append(
                        f"[SOURCE: Page {pnum} | "
                        f"Section: {p['section']}]\n{p['text']}"
                    )
                    selected_tables.extend(p.get("tables", []))

        text       = "\n\n".join(selected_text)
        table_text = self._tables_to_text(selected_tables)

        prompt = f"""
You are a senior credit analyst at an Indian NBFC.
Each section is tagged with SOURCE page number for audit traceability.
Extract financial data and record the page number where each key figure was found.

Document text (with page citations):
{text[:5000]}

Tables:
{table_text[:1500]}

Indian context notes:
- Figures are in INR Crores unless stated otherwise
- PAT = Profit After Tax, EBITDA = Earnings Before Interest Tax Depreciation
- Current Ratio = Current Assets / Current Liabilities (healthy if > 1.2)
- Debt to Equity = Total Debt / Net Worth (conservative if < 1.0)
- Look for GSTR-2A vs 3B mismatch as fake ITC signal
- Look for audit qualifications, going concern notes, related party anomalies

Return ONLY valid JSON matching this exact structure:
{JSON_SCHEMA}

Use null for missing values. Numbers only for financials (no units).
source_page should be the page number where the data was found.
Return ONLY the JSON. No explanation, no markdown.
"""
        time.sleep(3)
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return self._finalize(response.text)

    def _extract_small_pdf(self) -> dict:
        """
        For small PDFs (<50 pages) — query top relevant pages directly.
        """
        pages = self.parser.query(
            "revenue profit balance sheet GST directors debt litigation"
        )
        text = "\n\n".join([
            f"[SOURCE: Page {p.get('page_number', p['page'])} | "
            f"Section: {p['section']}]\n{p['text']}"
            for p in pages[:5]
        ])
        tables = []
        for p in pages[:5]:
            tables.extend(p.get("tables", []))
        table_text = self._tables_to_text(tables)

        prompt = f"""
You are a senior credit analyst at an Indian NBFC.
Extract ALL financial data from this document.
Each section is tagged with its SOURCE page number.

Document text:
{text[:4000]}

Tables:
{table_text[:1000]}

Indian context:
- Figures in INR Crores
- GSTR-2A vs 3B mismatch = fake ITC signal
- Circular trading = same party as buyer and seller
- Going concern note = high risk flag

Return ONLY valid JSON matching this exact structure:
{JSON_SCHEMA}

Use null for missing values. Numbers only for financials.
source_page = page number where data was found.
Return ONLY the JSON. No explanation.
"""
        time.sleep(3)
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return self._finalize(response.text)

    def _finalize(self, response_text: str) -> dict:
        """Parse response and ensure all keys exist"""
        result = self._parse_json_response(response_text)
        for key in ["basic_info", "financials", "debt_profile",
                    "gst_analysis", "red_flags"]:
            if key not in result:
                result[key] = {}
        return result

    def _tables_to_text(self, tables: list) -> str:
        result = []
        for table in tables:
            if table:
                for row in table:
                    if row:
                        cleaned = [str(cell) if cell else "" for cell in row]
                        result.append(" | ".join(cleaned))
        return "\n".join(result)

    def _parse_json_response(self, text: str) -> dict:
        import json
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            return json.loads(text.strip())
        except Exception:
            return {"raw_response": text[:200], "parse_error": True}