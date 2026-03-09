import os
import re
import json
import time
from google import genai
from google.genai.errors import ServerError, ClientError
from dotenv import load_dotenv

load_dotenv()
OPTIMIZED_API_FLOW = os.getenv("OPTIMIZED_API_FLOW", "true").strip().lower() in {"1", "true", "yes", "on"}


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
            bank = self.documents["bank_statement"]
            ar   = self.documents["annual_report"]

            bank_credits = None
            for key in ["total_credits_crores", "revenue_crores"]:
                val = bank.get(key)
                if val is not None:
                    try:
                        bank_credits = float(str(val).replace(",", "").replace("₹", "").strip())
                        break
                    except Exception:
                        pass

            ar_rev = self._extract_revenue(ar)

            findings["bank_vs_annual_report"] = {
                "bank_credits": bank_credits,
                "ar_revenue": ar_rev,
            }

            if bank_credits and ar_rev and ar_rev > 0:
                ratio = bank_credits / ar_rev
                if ratio < 0.50:
                    flags.append({
                        "type":        "CASH_FLOW_CONCERN",
                        "severity":    "MEDIUM",
                        "description": f"Bank credits ({bank_credits:.0f} Cr) are only {ratio*100:.0f}% of reported revenue ({ar_rev:.0f} Cr) — possible off-books transactions",
                    })
                elif ratio > 1.50:
                    flags.append({
                        "type":        "CIRCULAR_TRADING",
                        "severity":    "HIGH",
                        "description": f"Bank credits ({bank_credits:.0f} Cr) are {ratio*100:.0f}% of reported revenue ({ar_rev:.0f} Cr) — circular trading suspect",
                    })

            # Bounce check
            bounce_count = bank.get("bounce_count", 0) or 0
            if bounce_count > 5:
                flags.append({
                    "type":        "BOUNCE_CONCERN",
                    "severity":    "MEDIUM" if bounce_count <= 10 else "HIGH",
                    "description": f"{bounce_count} bounced transactions detected in bank statement",
                })

        # ITR vs Annual Report turnover cross-check
        if "itr_filing" in self.documents and "annual_report" in self.documents:
            itr_rev = self._extract_revenue(self.documents["itr_filing"])
            ar_rev = self._extract_revenue(self.documents["annual_report"])
            findings["itr_vs_annual_report"] = {"itr_revenue": itr_rev, "ar_revenue": ar_rev}

            if itr_rev and ar_rev and ar_rev > 0:
                variance = abs(itr_rev - ar_rev) / ar_rev
                if variance > 0.20:
                    flags.append({
                        "type": "REVENUE_MISMATCH",
                        "severity": "HIGH" if variance > 0.30 else "MEDIUM",
                        "description": f"ITR income ({itr_rev:.0f} Cr) vs Annual Report revenue ({ar_rev:.0f} Cr) — {variance*100:.1f}% variance",
                    })

        # ITR vs Bank statement consistency check
        if "itr_filing" in self.documents and "bank_statement" in self.documents:
            itr_rev = self._extract_revenue(self.documents["itr_filing"])
            bank_rev = self._extract_revenue(self.documents["bank_statement"])
            findings["itr_vs_bank_statement"] = {"itr_revenue": itr_rev, "bank_credits": bank_rev}

            if itr_rev and bank_rev and itr_rev > 0:
                variance = abs(itr_rev - bank_rev) / itr_rev
                if variance > 0.25:
                    flags.append({
                        "type": "CASHFLOW_MISMATCH",
                        "severity": "MEDIUM",
                        "description": f"ITR income ({itr_rev:.0f} Cr) vs bank credits ({bank_rev:.0f} Cr) — {variance*100:.1f}% variance",
                    })

        # GST: GSTR-2A vs GSTR-3B ITC mismatch detection
        if "gst_filing" in self.documents:
            gst = self.documents["gst_filing"]
            gstr2a_itc = gst.get("gstr2a_itc_crores")
            gstr3b_itc = gst.get("gstr3b_itc_claimed_crores")

            if gstr2a_itc is not None and gstr3b_itc is not None:
                try:
                    gstr2a_itc = float(gstr2a_itc)
                    gstr3b_itc = float(gstr3b_itc)
                    if gstr2a_itc > 0:
                        itc_mismatch = abs(gstr3b_itc - gstr2a_itc) / gstr2a_itc
                        if itc_mismatch > 0.10:
                            severity = "HIGH" if itc_mismatch > 0.25 else "MEDIUM"
                            flags.append({
                                "type":        "FAKE_ITC_RISK",
                                "severity":    severity,
                                "description": f"GSTR-2A ITC ({gstr2a_itc:.1f} Cr) vs GSTR-3B ITC claimed ({gstr3b_itc:.1f} Cr) — {itc_mismatch*100:.1f}% mismatch. Possible fake Input Tax Credit.",
                            })
                            findings["gstr2a_vs_gstr3b"] = {
                                "gstr2a_itc": gstr2a_itc,
                                "gstr3b_itc_claimed": gstr3b_itc,
                                "mismatch_percent": round(itc_mismatch * 100, 1),
                            }
                except (ValueError, TypeError):
                    pass

            # GSTR-1 vs GSTR-3B turnover mismatch
            gstr1_turnover = gst.get("gstr1_turnover_crores")
            gstr3b_turnover = gst.get("gstr3b_turnover_crores")
            if gstr1_turnover is not None and gstr3b_turnover is not None:
                try:
                    gstr1_turnover = float(gstr1_turnover)
                    gstr3b_turnover = float(gstr3b_turnover)
                    if gstr3b_turnover > 0:
                        turnover_mismatch = abs(gstr1_turnover - gstr3b_turnover) / gstr3b_turnover
                        if turnover_mismatch > 0.15:
                            flags.append({
                                "type":        "REVENUE_MISMATCH",
                                "severity":    "HIGH" if turnover_mismatch > 0.25 else "MEDIUM",
                                "description": f"GSTR-1 turnover ({gstr1_turnover:.0f} Cr) vs GSTR-3B turnover ({gstr3b_turnover:.0f} Cr) — {turnover_mismatch*100:.1f}% variance. Revenue inflation signal.",
                            })
                except (ValueError, TypeError):
                    pass

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
        if OPTIMIZED_API_FLOW:
            return []
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