import re
import os
import json
import time
from google import genai
from google.genai.errors import ServerError, ClientError
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


class FinancialExtractor:
    def __init__(self, parser: PageIndexParser):
        self.parser = parser
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model  = "gemini-2.5-flash"

    def extract_all(self) -> dict:
        if self.parser.is_large:
            return self._extract_large_pdf()
        return self._extract_small_pdf()

    def _extract_large_pdf(self) -> dict:
        """
        Section-aware extraction for large PDFs (>50 pages).
        Top 2 pages per section — targeted, fast, traceable.
        """
        section_queries = {
            "identity":   "company name CIN directors promoter incorporated",
            "financials": "revenue profit EBITDA PAT turnover balance sheet "
                          "net worth total assets",
            "debt":       "borrowings loans debt collateral secured unsecured "
                          "term loan",
            "compliance": "GST litigation audit penalty going concern",
            "net_worth":  "net worth equity shareholders funds reserves surplus",
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

        prompt = self._build_prompt(text, table_text)
        time.sleep(3)
        response = _gemini_with_retry(self.client, self.model, prompt)
        return self._finalize(response.text)

    def _extract_small_pdf(self) -> dict:
        """For small PDFs — query top relevant pages directly."""
        pages = self.parser.query(
            "revenue profit balance sheet GST directors debt "
            "litigation net worth borrowings"
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

        prompt = self._build_prompt(text, table_text)
        time.sleep(3)
        response = _gemini_with_retry(self.client, self.model, prompt)
        return self._finalize(response.text)

    def _build_prompt(self, text: str, table_text: str) -> str:
        return f"""
You are a senior credit analyst at an Indian NBFC.
Each section is tagged with SOURCE page number for audit traceability.

Document text:
{text[:5000]}

Tables:
{table_text[:1500]}

Indian financial context:
- All figures in INR Crores unless stated otherwise
- Net Worth = Equity Share Capital + Reserves & Surplus
- Total Debt = Long-term Borrowings + Short-term Borrowings + Current maturities
- EBITDA = PAT + Tax + Depreciation + Interest/Finance costs
- Debt to Equity = Total Debt / Net Worth
- Current Ratio = Current Assets / Current Liabilities

CRITICAL — What counts as a RED FLAG (only these):
- Audit qualification by statutory auditor
- Going concern doubt expressed by auditor
- NPA (Non-Performing Asset) classification
- Wilful defaulter tag
- Adverse NCLT/insolvency order against the company
- Active CBI/ED/fraud investigation
- DRT (Debt Recovery Tribunal) case filed against company

DO NOT flag these as red flags (they are normal disclosures):
- Related Party Transactions (mandatory under Companies Act 2013 / Ind AS 24)
- Contingent liabilities (standard disclosure)
- Pending tax disputes (routine)
- NCLT approval for restructuring/demerger (positive event)
- SEBI settlement by subsidiary for minor amounts (not direct company issue)

Return ONLY valid JSON:
{JSON_SCHEMA}

Use null for missing values. Numbers only for financials (no units, no commas).
source_page = page number where the data was found.
Return ONLY the JSON. No explanation, no markdown.
"""

    def _finalize(self, response_text: str) -> dict:
        result = self._parse_json_response(response_text)
        for key in ["basic_info", "financials", "debt_profile",
                    "gst_analysis", "red_flags"]:
            if key not in result:
                result[key] = {}
        return result

    def _tables_to_text(self, tables: list) -> str:
        rows = []
        for table in tables:
            if table:
                for row in table:
                    if row:
                        cleaned = [str(c) if c else "" for c in row]
                        rows.append(" | ".join(cleaned))
        return "\n".join(rows)

    def _parse_json_response(self, text: str) -> dict:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            return json.loads(text.strip())
        except Exception:
            return {"raw_response": text[:200], "parse_error": True}