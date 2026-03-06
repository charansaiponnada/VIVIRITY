import re
import os
import time
from google import genai
from core.pdf_parser import PageIndexParser
from dotenv import load_dotenv

load_dotenv()


class FinancialExtractor:
    def __init__(self, parser: PageIndexParser):
        self.parser = parser
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-2.5-flash"

    def extract_all(self) -> dict:
        """Single Gemini call for everything - saves quota"""
        pages = self.parser.query(
            "revenue profit balance sheet GST directors debt litigation"
        )
        text = "\n".join([p["text"] for p in pages[:5]])
        tables = []
        for p in pages[:5]:
            tables.extend(p.get("tables", []))
        table_text = self._tables_to_text(tables)

        prompt = f"""
You are a senior credit analyst at an Indian NBFC.
Analyze this company document and extract ALL of the following in one response.

Document text:
{text[:4000]}

Tables:
{table_text[:1000]}

Extract and return ONLY valid JSON with these exact keys:
{{
    "basic_info": {{
        "company_name": null,
        "cin": null,
        "address": null,
        "directors": [],
        "business_nature": null,
        "incorporation_year": null
    }},
    "financials": {{
        "revenue_current": null,
        "revenue_previous": null,
        "ebitda": null,
        "pat": null,
        "total_assets": null,
        "net_worth": null,
        "total_debt": null,
        "current_ratio": null,
        "debt_to_equity": null
    }},
    "debt_profile": {{
        "lenders": [],
        "secured_loans": null,
        "unsecured_loans": null,
        "collateral": null,
        "covenant_violations": null,
        "npa_mention": false
    }},
    "gst_analysis": {{
        "gst_numbers": [],
        "total_gst_paid": null,
        "gstr_mismatch_detected": false,
        "mismatch_details": null,
        "circular_trading_risk": false,
        "gst_notices": []
    }},
    "red_flags": {{
        "red_flags": [],
        "litigation_count": 0,
        "audit_qualified": false,
        "going_concern_issue": false,
        "severity": "low"
    }}
}}

Use null for missing values. Return ONLY the JSON, no explanation.
        """

        time.sleep(4)
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        result = self._parse_json_response(response.text)

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
            text = text.strip()
            return json.loads(text)
        except Exception:
            return {"raw_response": text, "parse_error": True}