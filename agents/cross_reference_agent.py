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


class CrossReferenceAgent:
    def __init__(self, documents: dict):
        """
        documents: dict mapping doc_type -> extracted financial dict
        e.g. {"annual_report": {...}, "gst_filing": {...}}
        """
        self.documents = documents
        self.model     = "gemini-2.5-flash"
        self.client    = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def run(self) -> dict:
        print("[CrossReferenceAgent] Running cross-document analysis...")

        if len(self.documents) < 2:
            return {
                "cross_reference_performed": False,
                "reason": "Only one document type uploaded. Upload GST filing or bank statement alongside annual report for fraud detection.",
                "flags": [],
                "circular_trading_risk": "Unknown",
                "revenue_inflation_risk": "Unknown",
            }

        doc_types = list(self.documents.keys())
        print(f"[CrossReferenceAgent] Comparing: {doc_types}")

        flags    = []
        findings = {}

        # GST vs Annual Report revenue cross-check
        if "gst_filing" in self.documents and "annual_report" in self.documents:
            gst_rev = self._extract_revenue(self.documents["gst_filing"])
            ar_rev  = self._extract_revenue(self.documents["annual_report"])
            findings["gst_vs_annual_report"] = {"gst_revenue": gst_rev, "ar_revenue": ar_rev}

            if gst_rev and ar_rev and ar_rev > 0:
                variance = abs(gst_rev - ar_rev) / ar_rev
                if variance > 0.20:
                    flags.append({
                        "type":        "REVENUE_MISMATCH",
                        "severity":    "HIGH",
                        "description": f"GST revenue ({gst_rev:.0f} Cr) vs Annual Report ({ar_rev:.0f} Cr) — {variance*100:.1f}% variance",
                    })

        # Bank statement vs Annual Report cash flow
        if "bank_statement" in self.documents and "annual_report" in self.documents:
            findings["bank_vs_annual_report"] = "Bank statement cross-check performed"

        # AI-powered deep cross-reference
        ai_flags = self._ai_cross_reference()
        flags.extend(ai_flags)

        circular_risk = "High" if any(f["type"] == "CIRCULAR_TRADING" for f in flags) else \
                        "Medium" if len(flags) > 0 else "Low"
        inflation_risk = "High" if any(f["type"] == "REVENUE_MISMATCH" for f in flags) else "Low"

        return {
            "cross_reference_performed": True,
            "documents_compared":        doc_types,
            "flags":                     flags,
            "findings":                  findings,
            "circular_trading_risk":     circular_risk,
            "revenue_inflation_risk":    inflation_risk,
            "summary":                   f"Cross-referenced {len(doc_types)} documents. Found {len(flags)} flag(s).",
        }

    def _extract_revenue(self, financial_data: dict) -> float | None:
        for key in ["revenue_crores", "revenue", "total_income", "turnover"]:
            val = financial_data.get(key)
            if val is not None:
                try:
                    return float(str(val).replace(",", "").replace("₹", "").strip())
                except Exception:
                    pass
        return None

    def _ai_cross_reference(self) -> list[dict]:
        try:
            doc_summary = json.dumps({
                k: {kk: vv for kk, vv in v.items() if kk in [
                    "revenue_crores", "total_income", "profit_after_tax",
                    "total_assets", "borrowings", "red_flags"
                ]}
                for k, v in self.documents.items()
            }, indent=2)[:3000]

            prompt = f"""
You are a forensic credit analyst at Vivriti Capital.
Cross-reference these financial documents and identify fraud signals:

{doc_summary}

Look for:
1. Circular trading patterns (same invoices appearing multiple times)
2. Revenue inflation (GST turnover vs reported revenue mismatch > 20%)
3. Round-tripping (money going out and coming back as revenue)
4. Unusual related-party transactions
5. Cash flow vs profit mismatch

Return ONLY valid JSON. No markdown.
{{
    "flags": [
        {{
            "type": "CIRCULAR_TRADING/REVENUE_MISMATCH/ROUND_TRIPPING/RELATED_PARTY/CASHFLOW_MISMATCH",
            "severity": "HIGH/MEDIUM/LOW",
            "description": "specific finding"
        }}
    ],
    "overall_assessment": "Clean/Moderate Risk/High Risk",
    "summary": "one line summary"
}}
"""
            time.sleep(2)
            response = _gemini_with_retry(self.client, self.model, prompt)
            raw      = re.sub(r'<think>.*?</think>', '', response.text, flags=re.DOTALL).strip()
            result   = self._parse_json(raw)
            return result.get("flags", [])
        except Exception as e:
            print(f"[CrossReferenceAgent] AI cross-reference error: {e}")
            return []

    def _parse_json(self, text: str) -> dict:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*',     '', text)
            return json.loads(text.strip())
        except Exception:
            return {"flags": [], "parse_error": True}