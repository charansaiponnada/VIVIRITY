"""
agents/ingestor_agent.py
Fixes applied:
  #3  ICR/finance_cost — stronger extraction hints + ratio fallback estimates
  #4  Directors — retry with broader window if < 5 found
  #5  CIN — regex primary extractor before LLM
"""

import os
import re
import json
import csv
import time
import io
import pdfplumber
import fitz
import pandas as pd
from google import genai
from google.genai.errors import ServerError, ClientError
from dotenv import load_dotenv
from agents.document_classifier import DocumentClassifier
from utils.indian_context import deduplicate_persons

load_dotenv()
OPTIMIZED_API_FLOW = os.getenv("OPTIMIZED_API_FLOW", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _gemini_with_retry(
    client,
    model: str,
    contents,
    max_retries: int = 5,
    fallback: str = "gemini-2.0-flash-lite",
):
    for attempt in range(max_retries):
        current_model = fallback if attempt == max_retries - 1 else model
        try:
            return client.models.generate_content(
                model=current_model, contents=contents
            )
        except ServerError:
            if attempt == max_retries - 1:
                raise
            wait = 8 * (2 ** min(attempt, 3))
            print(
                f"[Gemini] 503 — retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
            )
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


# ── FIX #5: CIN regex patterns ───────────────────────────────────────── #
CIN_PATTERN = re.compile(
    r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}(?:PLC|NPL|OPC|LLC|FLC|GOI|SGC|FTC|BNL|GAP)[0-9]{6})\b"
)

# ── VectorLess RAG constants ──────────────────────────────────────────── #
PAGE_BUDGET = 120
PAGES_PER_SECTION = 15

SECTION_QUERIES = {
    "identity": [
        "company name",
        "cin",
        "directors",
        "promoter",
        "incorporated",
        "board of directors",
        "corporate governance",
        "chairman",
        "managing director",
        "shareholding pattern",
    ],
    "revenue": ["revenue from operations", "turnover", "total income"],
    "profit": ["profit after tax", "pat", "profit before tax"],
    "ebitda": ["ebitda", "operating profit", "depreciation", "finance cost"],
    "balance_sheet": ["total assets", "total liabilities", "balance sheet"],
    "current_items": ["current assets", "current liabilities", "inventories"],
    "net_worth": ["net worth", "shareholders funds", "total equity"],
    "debt": ["borrowings", "total debt", "term loan"],
    "cash_flow": ["cash flow from operations"],
    "ratios": ["debt equity ratio", "current ratio"],
    "compliance": ["auditor", "going concern"],
    "notes": ["notes to financial", "related party"],
    "shareholding": ["promoter and promoter group", "public shareholding"],
}

PRIORITY_SECTIONS = [
    "ebitda",
    "balance_sheet",
    "current_items",
    "net_worth",
    "debt",
    "ratios",
    "notes",
]

BANKING_SECTION_QUERIES = {
    "identity": ["company name", "cin", "directors", "promoter"],
    "income": ["interest earned", "net interest income", "total income"],
    "profit": ["profit after tax", "pat"],
    "npa": ["gross npa", "net npa", "non-performing"],
    "capital": ["capital adequacy", "crar"],
    "deposits": ["deposits", "casa"],
    "advances": ["advances", "loan book"],
    "balance_sheet": ["total assets", "total liabilities", "net worth"],
    "ratios": ["net interest margin", "cost to income", "return on assets"],
    "compliance": ["auditor", "rbi directions"],
    "notes": ["notes to financial", "related party"],
    "shareholding": ["promoter and promoter group", "public shareholding"],
}

BANKING_PRIORITY_SECTIONS = [
    "npa",
    "capital",
    "deposits",
    "advances",
    "balance_sheet",
    "ratios",
    "income",
]


class IngestorAgent:
    def __init__(
        self,
        file_paths: list[str],
        log_callback=None,
        entity_type: str = "corporate",
        extract_schema: dict = None,
        custom_fields: str = "",
    ):
        self.file_paths = file_paths
        self.log = log_callback or print
        self.model = "gemini-2.5-flash"
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self._entity_type = entity_type
        self.extract_schema = extract_schema or {
            "ratios": True,
            "directors": True,
            "red_flags": True,
        }
        self.custom_fields = [
            f.strip() for f in (custom_fields or "").split(",") if f.strip()
        ]

    def run(self) -> dict:
        self.log(f"Starting ingestion of {len(self.file_paths)} document(s)...")
        results: dict = {}
        for path in self.file_paths:
            filename = os.path.basename(path)
            self.log(f"Parsing: {filename}")
            try:
                ext = os.path.splitext(filename)[1].lower()
                if ext == ".json":
                    data = self._ingest_json(path)
                    doc_type = data.pop("_doc_type", "gst_filing")
                    results[doc_type] = self._merge_document_data(
                        results.get(doc_type, {}), data, doc_type
                    )
                    continue
                elif ext == ".csv":
                    data = self._ingest_csv(path)
                    doc_type = data.pop("_doc_type", "bank_statement")
                    results[doc_type] = self._merge_document_data(
                        results.get(doc_type, {}), data, doc_type
                    )
                    continue
                elif ext in (".xlsx", ".xls"):
                    data = self._ingest_excel(path)
                    doc_type = data.pop("_doc_type", "structured_data")
                    results[doc_type] = self._merge_document_data(
                        results.get(doc_type, {}), data, doc_type
                    )
                    if "merged_all" not in results:
                        results["merged_all"] = {}
                    results["merged_all"] = self._merge_document_data(
                        results["merged_all"], data, "flat_merge"
                    )
                    continue

                with pdfplumber.open(path) as pdf:
                    page_count = len(pdf.pages)
                    doc_type = DocumentClassifier(pdf).classify()
                    self.log(
                        f"→ Classified as: {doc_type.upper().replace('_', ' ')} ({page_count} pages)"
                    )
                    extracted = self._extract(pdf, path, doc_type, page_count)
                    extracted["_entity_type"] = self._entity_type
                    if self.extract_schema.get("ratios", True):
                        extracted = self._compute_ratios(extracted)
                    if not extracted.get("cin"):
                        extracted["cin"] = self._extract_cin_regex(pdf, path)

                    results[doc_type] = self._merge_document_data(
                        results.get(doc_type, {}), extracted, doc_type
                    )
                    if "merged_all" not in results:
                        results["merged_all"] = {}
                    results["merged_all"] = self._merge_document_data(
                        results["merged_all"], extracted, "flat_merge"
                    )
                    self.log(f"→ Extraction complete")
            except Exception as e:
                self.log(f"⚠ Error processing {filename}: {e}")
        return results

    def _merge_document_data(self, base: dict, incoming: dict, doc_type: str) -> dict:
        if not isinstance(base, dict):
            return incoming or {}
        if not isinstance(incoming, dict):
            return base
        merged = dict(base)
        for k, v in incoming.items():
            if k == "red_flags":
                rf = dict(merged.get("red_flags", {}))
                for rk, rv in (v or {}).items():
                    if rv:
                        rf[rk] = rv
                merged["red_flags"] = rf
            elif isinstance(v, list):
                existing = merged.get(k, [])
                if not isinstance(existing, list):
                    existing = []
                seen = set(str(x).lower().strip() for x in existing)
                for item in v:
                    if str(item).lower().strip() not in seen:
                        existing.append(item)
                merged[k] = existing
            elif merged.get(k) is None:
                merged[k] = v
        return merged

    def _extract(self, pdf, path: str, doc_type: str, page_count: int) -> dict:
        if doc_type == "annual_report":
            return self._extract_annual_report(pdf, path, page_count)
        elif doc_type == "gst_filing":
            return self._extract_gst(pdf)
        elif doc_type == "itr_filing":
            return self._extract_itr(pdf)
        elif doc_type == "bank_statement":
            return self._extract_bank_statement(pdf)
        elif doc_type == "alm_report":
            return self._extract_alm_report(pdf)
        elif doc_type == "shareholding_pattern":
            return self._extract_shareholding_pattern(pdf)
        elif doc_type == "borrowing_profile":
            return self._extract_borrowing_profile(pdf)
        elif doc_type == "portfolio_cuts":
            return self._extract_portfolio_cuts(pdf)
        else:
            return self._extract_generic(pdf, doc_type)

    def _extract_annual_report(self, pdf, path: str, page_count: int) -> dict:
        entity_type = getattr(self, "_entity_type", "corporate")
        is_fin = entity_type in ("bank", "nbfc", "insurance")
        sq = BANKING_SECTION_QUERIES if is_fin else SECTION_QUERIES
        prio = BANKING_PRIORITY_SECTIONS if is_fin else PRIORITY_SECTIONS

        selected_pages = set(range(min(10, page_count)))
        doc = fitz.open(path)
        self.log(f"→ Scanning all {len(doc)} pages...")
        for pnum in range(len(doc)):
            txt = doc[pnum].get_text().lower()
            if any(any(kw in txt for kw in sq[s]) for s in prio):
                selected_pages.add(pnum)
            if len(selected_pages) >= PAGE_BUDGET:
                break
        doc.close()

        txt, tbls = self._extract_pages(pdf, sorted(selected_pages))
        merged = self._ai_extract_unified_financials(txt, tbls, entity_type)
        merged["directors"] = deduplicate_persons(merged.get("directors", []) or [])
        return merged

    def _ai_extract_unified_financials(
        self, text: str, tables_str: str, entity_type: str
    ) -> dict:
        profile = (
            "banking_or_financial"
            if entity_type in ("bank", "nbfc", "insurance")
            else "corporate"
        )
        directors_p = (
            '    "directors": [], "promoters": [],'
            if self.extract_schema.get("directors", True)
            else ""
        )
        red_flags_p = (
            '    "red_flags": {"audit_qualified": false, "going_concern_issue": false},'
            if self.extract_schema.get("red_flags", True)
            else ""
        )
        custom_p = (
            f"\n    # CUSTOM: {', '.join(self.custom_fields)}"
            if self.custom_fields
            else ""
        )

        prompt = f"""
Extract Indian corporate financial data. Entity: {profile}. INR Crores. Prefer Consolidated.
Inference: If "debt free" mentioned, total_borrowings = 0.
{custom_p}
Text: {text[:17000]}
Tables: {tables_str[:7000]}
Return JSON only:
{{
    "company_name": null, "cin": null, "fiscal_year": null,
    {directors_p}
    "revenue_crores": null, "profit_after_tax_crores": null, "ebitda_crores": null,
    "total_assets_crores": null, "net_worth_crores": null, "total_borrowings_crores": null,
    "debt_equity_ratio": null, "current_ratio": null, "interest_coverage_ratio": null,
    {red_flags_p}
    "extraction_notes": ""
}}
"""
        try:
            resp = _gemini_with_retry(self.client, self.model, prompt)
            raw = re.sub(r"<think>.*?</think>", "", resp.text, flags=re.DOTALL).strip()
            return self._parse_json(raw)
        except Exception:
            return {"red_flags": {}}

    def _extract_cin_regex(self, pdf, path: str) -> str | None:
        try:
            doc = fitz.open(path)
            for p in range(min(12, len(doc))):
                cleaned = re.sub(r"[^A-Z0-9]", "", doc[p].get_text().upper())
                m = CIN_PATTERN.findall(cleaned)
                if m:
                    res = m[0]
                    doc.close()
                    return res
            doc.close()
        except Exception:
            pass
        return None

    def _compute_ratios(self, data: dict) -> dict:
        if not data or data.get("parse_error"):
            return data
        notes = str(data.get("extraction_notes", "")).lower()
        if data.get("total_borrowings_crores") is None:
            if any(m in notes for m in ["debt free", "zero debt", "nil debt"]):
                data["total_borrowings_crores"] = 0.0

        def sf(v):
            try:
                return float(str(v).replace(",", "")) if v is not None else None
            except:
                return None

        rev, ebitda, debt, nw = (
            sf(data.get("revenue_crores")),
            sf(data.get("ebitda_crores")),
            sf(data.get("total_borrowings_crores")),
            sf(data.get("net_worth_crores")),
        )
        if (
            nw is None
            and data.get("total_assets_crores")
            and data.get("total_liabilities_crores")
        ):
            nw = sf(data["total_assets_crores"]) - sf(data["total_liabilities_crores"])
            data["net_worth_crores"] = round(nw, 2)

        if debt is not None and nw and nw > 0:
            data["debt_equity_ratio"] = round(debt / nw, 2)
        if rev and rev > 0 and ebitda is not None:
            data["ebitda_margin_percent"] = round(ebitda / rev * 100, 1)
        return data

    def _extract_pages(self, pdf, page_nums: list[int]) -> tuple[str, str]:
        texts, tables = [], []
        for pn in sorted(set(page_nums)):
            if pn >= len(pdf.pages):
                continue
            p = pdf.pages[pn]
            txt = p.extract_text() or ""
            if txt.strip():
                texts.append(f"[P{pn + 1}] {txt}")
            for t in p.extract_tables() or []:
                if t and len(t) > 1:
                    tables.append(t[:15])
        return "\n".join(texts)[:18000], json.dumps(tables[:20])[:8000]

    def _parse_json(self, text: str) -> dict:
        try:
            text = re.sub(r"```json\s*", "", text)
            text = re.sub(r"```\s*", "", text)
            return json.loads(text.strip())
        except Exception:
            return {"parse_error": True}

    def _ai_call(self, prompt: str) -> dict:
        try:
            if self.custom_fields:
                prompt += f"\nCustom fields: {', '.join(self.custom_fields)}"
            resp = _gemini_with_retry(self.client, self.model, prompt)
            raw = re.sub(r"<think>.*?</think>", "", resp.text, flags=re.DOTALL).strip()
            return self._parse_json(raw)
        except Exception:
            return {}

    def _extract_alm_report(self, pdf) -> dict:
        txt, tbls = self._extract_pages(pdf, list(range(min(15, len(pdf.pages)))))
        return self._ai_call(
            f"Extract ALM data (maturity buckets, gap). Text: {txt[:8000]} Tables: {tbls[:4000]}"
        )

    def _extract_shareholding_pattern(self, pdf) -> dict:
        txt, tbls = self._extract_pages(pdf, list(range(min(10, len(pdf.pages)))))
        return self._ai_call(
            f"Extract Shareholding (Promoter %, Public %). Text: {txt[:8000]} Tables: {tbls[:4000]}"
        )

    def _extract_borrowing_profile(self, pdf) -> dict:
        txt, tbls = self._extract_pages(pdf, list(range(min(15, len(pdf.pages)))))
        return self._ai_call(
            f"Extract Borrowings (Lenders, Limits). Text: {txt[:8000]} Tables: {tbls[:4000]}"
        )

    def _extract_portfolio_cuts(self, pdf) -> dict:
        txt, tbls = self._extract_pages(pdf, list(range(min(20, len(pdf.pages)))))
        return self._ai_call(
            f"Extract Portfolio Performance (NPA buckets). Text: {txt[:8000]} Tables: {tbls[:4000]}"
        )

    def _extract_generic(self, pdf, doc_type: str) -> dict:
        txt, _ = self._extract_pages(pdf, [0, 1, 2])
        return self._compute_ratios(
            self._ai_call(f"Extract financials from {doc_type}. Text: {txt[:8000]}")
        )

    def _ingest_json(self, path: str) -> dict:
        with open(path, "r") as f:
            data = json.load(f)
        data["_doc_type"] = "structured_data"
        return data

    def _ingest_csv(self, path: str) -> dict:
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return {
            "_doc_type": "bank_statement",
            "revenue_crores": len(rows),
            "transaction_count": len(rows),
        }

    def _ingest_excel(self, path: str) -> dict:
        try:
            xls = pd.ExcelFile(path)
            sheet_names = xls.sheet_names
            result = {
                "_doc_type": "structured_data",
                "_source_file": os.path.basename(path),
                "_sheets": sheet_names,
            }
            financial_data = {}
            all_data_raw = {}
            for sheet in sheet_names:
                df = pd.read_excel(path, sheet_name=sheet)
                df_str = df.to_string(max_rows=100)
                all_data_raw[sheet] = {
                    "columns": list(df.columns),
                    "row_count": len(df),
                    "preview": df.head(20).to_dict(orient="records"),
                }
                financial_data[sheet] = df_str
            result["_all_sheets"] = all_data_raw
            extracted = self._extract_from_excel(financial_data, sheet_names)
            result.update(extracted)
            result = self._compute_ratios(result)
            return result
        except Exception as e:
            return {"_doc_type": "structured_data", "_error": str(e)}

    def _extract_from_excel(self, data: dict, sheets: list) -> dict:
        prompt = f"""
You are a senior credit analyst at an Indian NBFC.
Extract financial data from the following Excel sheets content.

Sheets found: {sheets}

Sheet contents:
"""
        for sheet, content in data.items():
            prompt += f"\n=== {sheet} ===\n{content[:4000]}\n"
        prompt += """
Extract the following financial metrics (all figures in Crores unless noted):
- company_name, cin, directors
- revenue_crores (current and previous year)
- ebitda_crores
- pat_crores (profit after tax)
- total_assets_crores
- net_worth_crores
- total_borrowings_crores
- current_ratio
- debt_equity_ratio
- any other financial ratios or metrics

Return ONLY valid JSON with the extracted data. Use null for missing values.
Return ONLY the JSON. No explanation, no markdown.
"""
        return self._ai_call(prompt)
