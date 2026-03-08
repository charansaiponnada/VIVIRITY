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
import time
import pdfplumber
from google import genai
from google.genai.errors import ServerError, ClientError
from dotenv import load_dotenv
from agents.document_classifier import DocumentClassifier

load_dotenv()


def _gemini_with_retry(client, model: str, contents,
                        max_retries: int = 5,
                        fallback: str = "gemini-2.0-flash-lite"):
    for attempt in range(max_retries):
        current_model = fallback if attempt == max_retries - 1 else model
        try:
            return client.models.generate_content(model=current_model, contents=contents)
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


# ── FIX #5: CIN regex patterns ───────────────────────────────────────── #
# Format: L/U + 5 digits + 2 alpha + 4 digits + PLC/NPL/OPC + 6 digits
CIN_PATTERN = re.compile(
    r'\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}(?:PLC|NPL|OPC|LLC|FLC|GOI|SGC|FTC|BNL|GAP)[0-9]{6})\b'
)

# ── VectorLess RAG constants ──────────────────────────────────────────── #
PAGE_BUDGET       = 120
PAGES_PER_SECTION = 15

SECTION_QUERIES = {
    "identity":      ["company name","cin","directors","promoter","incorporated","board of directors","corporate governance","chairman","managing director","shareholding pattern","promoter and promoter group","key managerial personnel"],
    "revenue":       ["revenue from operations","turnover","income from operations","total income","net revenue","total revenue"],
    "profit":        ["profit after tax","pat","profit before tax","net profit","profit for the year","earnings per share"],
    "ebitda":        ["ebitda","operating profit","earnings before","depreciation and amortization","finance cost","interest expense","finance charges","borrowing costs"],
    "balance_sheet": ["total assets","total liabilities","fixed assets","property plant","capital work in progress","non-current assets","tangible assets"],
    "current_items": ["current assets","current liabilities","inventories","trade receivables","trade payables","short-term borrowings","current maturities"],
    "net_worth":     ["net worth","equity share capital","reserves and surplus","shareholders funds","total equity","other equity"],
    "debt":          ["long-term borrowings","short-term borrowings","total debt","secured loans","unsecured loans","term loan","debentures","bonds","ncds"],
    "cash_flow":     ["cash flow from operations","operating activities","net cash","cash and cash equivalents","free cash flow","cash generated"],
    "ratios":        ["debt equity ratio","interest coverage","current ratio","return on equity","roce","roe","dscr","working capital","key ratios","financial ratios"],
    "compliance":    ["auditor","audit report","going concern","qualification","emphasis of matter","key audit matter","caro","fraud"],
    "notes":         ["notes to financial","note no","schedule","significant accounting","related party","contingent liabilities"],
    "shareholding":  ["promoter and promoter group","public shareholding","pattern of shareholding","% of total","shares held","tata sons","institutional"],
}

PRIORITY_SECTIONS = ["ebitda","balance_sheet","current_items","net_worth","debt","cash_flow","ratios","notes","shareholding"]


class IngestorAgent:
    def __init__(self, file_paths: list[str], log_callback=None):
        self.file_paths = file_paths
        self.log        = log_callback or print
        self.model      = "gemini-2.5-flash"
        self.client     = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # ------------------------------------------------------------------ #
    def run(self) -> dict:
        self.log(f"Starting ingestion of {len(self.file_paths)} document(s)...")
        results: dict = {}

        for path in self.file_paths:
            filename = os.path.basename(path)
            self.log(f"Parsing: {filename}")

            try:
                with pdfplumber.open(path) as pdf:
                    page_count = len(pdf.pages)
                    classifier = DocumentClassifier(pdf)
                    doc_type   = classifier.classify()
                    self.log(f"→ Classified as: {doc_type.upper().replace('_',' ')} ({page_count} pages, targeted up to {min(PAGE_BUDGET, page_count)} pages)")

                    extracted = self._extract(pdf, path, doc_type, page_count)
                    extracted = self._compute_ratios(extracted)

                    # FIX #5: CIN regex pass on first 3 pages if still missing
                    if not extracted.get("cin"):
                        extracted["cin"] = self._extract_cin_regex(pdf, path)

                    results[doc_type] = extracted
                    self.log(f"→ Extraction complete")

            except Exception as e:
                self.log(f"⚠ Error processing {filename}: {e}")

        doc_types = ", ".join(results.keys()) if results else "none"
        self.log(f"Ingestion complete. Documents: {doc_types}. Financial pages extracted.")
        return results

    # ------------------------------------------------------------------ #
    def _extract(self, pdf, path: str, doc_type: str, page_count: int) -> dict:
        if doc_type == "annual_report":
            return self._extract_annual_report(pdf, path, page_count)
        elif doc_type == "gst_filing":
            return self._extract_gst(pdf)
        elif doc_type == "bank_statement":
            return self._extract_bank_statement(pdf)
        else:
            return self._extract_generic(pdf, doc_type)

    # ------------------------------------------------------------------ #
    def _extract_annual_report(self, pdf, path: str, page_count: int) -> dict:
        import fitz

        # Phase 1: Fast scan ALL pages
        section_ranges: dict[str, list[int]] = {s: [] for s in SECTION_QUERIES}
        doc = fitz.open(path)
        self.log(f"→ Pass 1: Scanning all {len(doc)} pages...")

        for page_num in range(len(doc)):
            page_text = doc[page_num].get_text().lower()
            for section, keywords in SECTION_QUERIES.items():
                if any(kw in page_text for kw in keywords):
                    section_ranges[section].append(page_num)
        doc.close()

        # Select pages — priority first
        selected_pages: set[int] = set()
        for section in PRIORITY_SECTIONS:
            for p in section_ranges.get(section, [])[:PAGES_PER_SECTION]:
                selected_pages.add(p)
        for section, pages in section_ranges.items():
            if section not in PRIORITY_SECTIONS:
                for p in pages[:8]:
                    selected_pages.add(p)
            if len(selected_pages) >= PAGE_BUDGET:
                break
        for i in range(min(8, page_count)):
            selected_pages.add(i)

        targeted = sorted(selected_pages)
        self.log(f"→ Pass 2: Deep extracting {len(targeted)} pages...")

        # Split pages into income vs balance groups
        income_pages, balance_pages = [], []
        income_secs  = {"revenue","profit","ebitda","cash_flow","identity","compliance"}
        balance_secs = {"balance_sheet","current_items","net_worth","debt","ratios","notes"}

        for pn in targeted:
            in_i = any(pn in section_ranges.get(s,[]) for s in income_secs)
            in_b = any(pn in section_ranges.get(s,[]) for s in balance_secs)
            if in_b: balance_pages.append(pn)
            if in_i or not in_b: income_pages.append(pn)

        income_text,  income_tables  = self._extract_pages(pdf, income_pages[:65])
        balance_text, balance_tables = self._extract_pages(pdf, balance_pages[:65])

        self.log(f"→ Extracting income statement data (Gemini call 1/2)...")
        income_data = self._ai_extract_income(income_text, income_tables)
        time.sleep(4)

        self.log(f"→ Extracting balance sheet data (Gemini call 2/2)...")
        balance_data = self._ai_extract_balance(balance_text, balance_tables)
        time.sleep(4)

        # Merge
        merged = {**income_data}
        for key, val in balance_data.items():
            if key == "red_flags":
                merged_rf = dict(merged.get("red_flags", {}))
                for k, v in (val or {}).items():
                    if v: merged_rf[k] = v
                merged["red_flags"] = merged_rf
            elif merged.get(key) is None and val is not None:
                merged[key] = val

        # Merge directors
        d1 = income_data.get("directors", []) or []
        d2 = balance_data.get("directors", []) or []
        seen, merged_dirs = set(), []
        for d in d1 + d2:
            k = (d.get("name", str(d)) if isinstance(d, dict) else str(d)).lower().strip()
            if k not in seen and k:
                seen.add(k)
                merged_dirs.append(d)
        merged["directors"] = merged_dirs

        # Merge promoters
        p1 = income_data.get("promoters", []) or []
        p2 = balance_data.get("promoters", []) or []
        seen_p, merged_prom = set(), []
        for p in p1 + p2:
            k = (p.get("name", str(p)) if isinstance(p, dict) else str(p)).lower().strip()
            if k not in seen_p and k:
                seen_p.add(k)
                merged_prom.append(p)
        if merged_prom:
            merged["promoters"] = merged_prom

        # FIX #4: If < 5 directors, retry with governance-focused context
        if len(merged_dirs) < 5:
            self.log(f"→ Only {len(merged_dirs)} directors found — retrying with governance pages...")
            # Indian annual reports: Corporate Governance section is typically pages 60-140
            # Scan unconditionally — don't rely on section_ranges which may miss image-heavy pages
            cg_start = min(55, page_count - 1)
            cg_end   = min(145, page_count)
            gov_pages = list(range(cg_start, cg_end))
            # Also include any identity-tagged pages
            gov_pages = sorted(set(gov_pages + section_ranges.get("identity", [])[:15]))
            if gov_pages:
                gov_text, gov_tables = self._extract_pages(pdf, gov_pages[:45])
                more_directors = self._extract_directors_targeted(gov_text, gov_tables)
                for d in more_directors:
                    k = (d.get("name", str(d)) if isinstance(d, dict) else str(d)).lower().strip()
                    if k not in seen and k:
                        seen.add(k)
                        merged_dirs.append(d)
                merged["directors"] = merged_dirs
                self.log(f"→ Directors after retry: {len(merged_dirs)}")

        # FIX #3 PART 2: If critical fields still NULL, run targeted notes extraction
        missing_critical = (
            merged.get("finance_cost_crores") is None or
            merged.get("total_borrowings_crores") is None or
            merged.get("depreciation_crores") is None
        )
        if missing_critical and page_count > 100:
            self.log(f"→ Critical fields missing — scanning financial notes (pages 150-350)...")
            # Notes to accounts: typically pages 150-400 for large companies
            notes_range = list(range(150, min(380, page_count)))
            # Filter to pages actually tagged as notes/ebitda/debt sections
            notes_pages = []
            for pn in notes_range:
                if any(pn in section_ranges.get(s, []) for s in ["notes","ebitda","debt","cash_flow"]):
                    notes_pages.append(pn)
            # If sparse, take every 3rd page in the range
            if len(notes_pages) < 15:
                notes_pages = notes_range[::3][:25]

            if notes_pages:
                notes_text, notes_tables = self._extract_pages(pdf, notes_pages[:30])
                notes_data = self._ai_extract_notes(notes_text, notes_tables)
                time.sleep(3)
                # Only fill in fields that are still NULL
                for key in ["finance_cost_crores","depreciation_crores","total_borrowings_crores",
                            "long_term_borrowings_crores","short_term_borrowings_crores",
                            "operating_cash_flow_crores","capex_crores","total_assets_crores",
                            "current_assets_crores","current_liabilities_crores"]:
                    if merged.get(key) is None and notes_data.get(key) is not None:
                        merged[key] = notes_data[key]
                        print(f"  [NotesExtraction] Filled {key} = {notes_data[key]}")

        merged["extraction_method"] = "VectorLess RAG — Split two-call + notes extraction"
        return merged

    # ------------------------------------------------------------------ #
    def _ai_extract_notes(self, text: str, tables_str: str) -> dict:
        """
        FIX #3: Third targeted extraction pass for financial notes.
        Specifically hunts for finance cost, depreciation, and borrowings
        which appear in Notes 15-35 of the annual report (pages 200-400).
        """
        prompt = f"""
You are extracting ONLY these specific financial line items from Indian annual report notes.
These are usually in Notes 28-35 (Finance Costs, Depreciation) and Notes 15-20 (Borrowings).

LOOK SPECIFICALLY FOR:
1. "Finance costs" / "Interest expense" / "Borrowing costs" — this is a P&L line item
2. "Depreciation and amortisation expense" — P&L line item
3. "Long-term borrowings" / "Short-term borrowings" / "Current maturities of long-term debt"
4. "Cash flows from operating activities" / "Net cash from operations"
5. "Capital expenditure" / "Purchase of property, plant and equipment"
6. "Total assets" (from Balance Sheet summary)
7. "Current assets" and "Current liabilities" totals

Numbers are in CRORES. If in lakhs divide by 100.
Only extract numbers you are CERTAIN about from the text/tables. Return null if not found.

Text:
{text[:15000]}

Tables:
{tables_str[:6000]}

Return ONLY valid JSON. No markdown. No thinking tokens.
{{
    "finance_cost_crores": null,
    "depreciation_crores": null,
    "total_borrowings_crores": null,
    "long_term_borrowings_crores": null,
    "short_term_borrowings_crores": null,
    "operating_cash_flow_crores": null,
    "capex_crores": null,
    "total_assets_crores": null,
    "current_assets_crores": null,
    "current_liabilities_crores": null
}}
"""
        try:
            response = _gemini_with_retry(self.client, self.model, prompt)
            raw = re.sub(r'<think>.*?</think>', '', response.text, flags=re.DOTALL).strip()
            result = self._parse_json(raw)
            return result if not result.get("parse_error") else {}
        except Exception as e:
            print(f"[Ingestor] Notes extraction error: {e}")
            return {}

    # ------------------------------------------------------------------ #
    def _extract_pages(self, pdf, page_nums: list[int]) -> tuple[str, str]:
        texts, tables = [], []
        for pn in sorted(set(page_nums)):
            if pn >= len(pdf.pages):
                continue
            page = pdf.pages[pn]
            text = page.extract_text() or ""
            if text.strip():
                texts.append(f"[Page {pn+1}]\n{text}")
            for t in (page.extract_tables() or []):
                if t and len(t) > 1:
                    tables.append({"page": pn+1, "data": t[:20]})
        return "\n\n".join(texts)[:18000], json.dumps(tables[:25], indent=1)[:8000]

    # ------------------------------------------------------------------ #
    def _ai_extract_income(self, text: str, tables_str: str) -> dict:
        prompt = f"""
You are a senior financial analyst extracting data from an Indian corporate annual report.
Focus on INCOME STATEMENT, P&L, and CASH FLOW data.

CRITICAL RULES:
- Numbers are in CRORES (₹ Cr). If in lakhs, divide by 100.
- Prefer CONSOLIDATED over standalone figures.
- Revenue from Operations = primary revenue.
- EBITDA = PBT + Finance Cost + Depreciation (compute if not explicitly stated).
- FINANCE COST / INTEREST EXPENSE is critical — look for: "finance costs", "interest expense",
  "borrowing costs", "finance charges", "interest on borrowings", "interest paid".
  It is usually between ₹100 Cr and ₹50,000 Cr for large companies.
- DEPRECIATION: look for "depreciation", "amortisation", "D&A", "depreciation and amortization".
- DIRECTORS: Extract EVERY person named as Chairman, Director, MD, CEO, CFO, Independent Director,
  Non-Executive Director, Whole-Time Director, Nominee Director. Look in sections titled
  "Board of Directors", "Directors", "Corporate Governance", "Management Team", "Key Managerial Personnel".
  There should be at least 5-12 directors for a listed Indian company. Do NOT miss any.
- Do NOT approximate. Extract exact figures from tables.

Text:
{text}

Tables:
{tables_str}

Return ONLY valid JSON. No markdown. No thinking tokens. null for missing values.
{{
    "company_name": null,
    "cin": null,
    "directors": [],
    "promoters": [],
    "fiscal_year": null,
    "revenue_crores": null,
    "revenue_growth_percent": null,
    "profit_after_tax_crores": null,
    "profit_before_tax_crores": null,
    "ebitda_crores": null,
    "ebitda_margin_percent": null,
    "depreciation_crores": null,
    "finance_cost_crores": null,
    "operating_cash_flow_crores": null,
    "capex_crores": null,
    "free_cash_flow_crores": null,
    "external_credit_rating": null,
    "red_flags": {{
        "audit_qualified": false,
        "going_concern_issue": false,
        "npa_mention": false,
        "related_party_concerns": false
    }},
    "key_ratios_source_pages": [],
    "extraction_notes": ""
}}
"""
        try:
            response = _gemini_with_retry(self.client, self.model, prompt)
            raw = re.sub(r'<think>.*?</think>', '', response.text, flags=re.DOTALL).strip()
            result = self._parse_json(raw)
            return result if not result.get("parse_error") else {"red_flags": {}}
        except Exception as e:
            print(f"[Ingestor] Income extraction error: {e}")
            return {"red_flags": {}}

    # ------------------------------------------------------------------ #
    def _ai_extract_balance(self, text: str, tables_str: str) -> dict:
        prompt = f"""
You are a senior financial analyst extracting data from an Indian corporate annual report.
Focus on BALANCE SHEET, NET WORTH, DEBT, and RATIOS.

CRITICAL RULES:
- Numbers are in CRORES (₹ Cr). If in lakhs, divide by 100.
- Prefer CONSOLIDATED figures.
- Net Worth = Share Capital + Reserves and Surplus (also called "Total Equity").
- ⚠️ TOTAL BORROWINGS ≠ TOTAL LIABILITIES. These are DIFFERENT numbers.
  Total Borrowings = ONLY Long-term Borrowings + Short-term Borrowings (i.e. debt instruments, bank loans, NCDs, debentures).
  Total Liabilities includes ALL liabilities (trade payables, provisions, deferred tax etc.) and will be 2-5x larger than borrowings.
  For a typical Indian manufacturing company, Total Borrowings is usually 20-50% of Net Worth, NOT equal to Total Assets.
- FINANCE COST is also on the balance sheet side as "interest accrued" or in the P&L notes.
- Extract EXACT numbers from tables. Do NOT conflate different line items.
- Extract ALL directors named.
- PROMOTERS / SHAREHOLDING: Look for "Promoter and Promoter Group" in the shareholding pattern table.
  Extract promoter entity names and their % holding.

Text:
{text}

Tables:
{tables_str}

Return ONLY valid JSON. No markdown. No thinking tokens. null for missing.
{{
    "directors": [],
    "promoters": [],
    "total_assets_crores": null,
    "total_liabilities_crores": null,
    "current_assets_crores": null,
    "current_liabilities_crores": null,
    "net_worth_crores": null,
    "share_capital_crores": null,
    "reserves_crores": null,
    "total_borrowings_crores": null,
    "long_term_borrowings_crores": null,
    "short_term_borrowings_crores": null,
    "cash_and_equivalents_crores": null,
    "trade_receivables_crores": null,
    "inventories_crores": null,
    "finance_cost_crores": null,
    "depreciation_crores": null,
    "debt_equity_ratio": null,
    "current_ratio": null,
    "interest_coverage_ratio": null,
    "return_on_equity_percent": null,
    "return_on_assets_percent": null,
    "return_on_capital_employed_percent": null,
    "gst_turnover_crores": null,
    "red_flags": {{
        "audit_qualified": false,
        "going_concern_issue": false,
        "npa_mention": false,
        "related_party_concerns": false
    }},
    "extraction_notes": ""
}}
"""
        try:
            response = _gemini_with_retry(self.client, self.model, prompt)
            raw = re.sub(r'<think>.*?</think>', '', response.text, flags=re.DOTALL).strip()
            result = self._parse_json(raw)
            return result if not result.get("parse_error") else {"red_flags": {}}
        except Exception as e:
            print(f"[Ingestor] Balance extraction error: {e}")
            return {"red_flags": {}}

    # ------------------------------------------------------------------ #
    def _extract_directors_targeted(self, text: str, tables_str: str) -> list:
        """
        FIX #4: Targeted director extraction when initial pass finds < 5.
        Uses a narrow prompt focused only on board composition.
        """
        prompt = f"""
Extract the complete Board of Directors from this Indian corporate annual report section.
Look for: "Board of Directors", "Directors", "Corporate Governance", "Management Discussion".
Extract EVERY name listed as Chairman, Director, Managing Director, Independent Director, etc.

Text:
{text[:10000]}

Tables:
{tables_str[:3000]}

Return ONLY a JSON array of director objects. No markdown.
[
  {{"name": "Full Name", "designation": "Designation / Role"}},
  ...
]
"""
        try:
            response = _gemini_with_retry(self.client, self.model, prompt)
            raw = re.sub(r'<think>.*?</think>', '', response.text, flags=re.DOTALL).strip()
            raw = re.sub(r'```json\s*', '', raw)
            raw = re.sub(r'```\s*', '', raw)
            result = json.loads(raw.strip())
            if isinstance(result, list):
                return result
        except Exception as e:
            print(f"[Ingestor] Director retry error: {e}")
        return []

    # ------------------------------------------------------------------ #
    def _extract_cin_regex(self, pdf, path: str) -> str | None:
        """
        FIX #5: Two-pass regex CIN extractor.
        Pass A: pdfplumber (already open, no extra cost)
        Pass B: fitz/PyMuPDF (different text extraction layer)
        Pass C: Broader pattern matching in case of formatting differences
        CIN format: L/U + 5 digits + 2 alpha state code + 4 digits + PLC/NPL/OPC + 6 digits
        Example: L28920MH1945PLC004520 (Tata Motors)
        """
        # Pass A: pdfplumber — first 8 pages
        try:
            for page_num in range(min(8, len(pdf.pages))):
                text = pdf.pages[page_num].extract_text() or ""
                matches = CIN_PATTERN.findall(text)
                if matches:
                    cin = matches[0]
                    print(f"  [CIN Regex/pdfplumber] Found on page {page_num+1}: {cin}")
                    return cin
        except Exception as e:
            print(f"  [CIN Regex/pdfplumber] Error: {e}")

        # Pass B: fitz — different text layer, sometimes captures what pdfplumber misses
        import fitz
        try:
            doc = fitz.open(path)
            for page_num in range(min(10, len(doc))):
                text = doc[page_num].get_text()
                # Also try with spaces removed (some PDFs have "L 2 8 9 2 0 M H...")
                text_nospace = re.sub(r'\s+', '', text)
                for t in [text, text_nospace]:
                    matches = CIN_PATTERN.findall(t)
                    if matches:
                        cin = matches[0]
                        print(f"  [CIN Regex/fitz] Found on page {page_num+1}: {cin}")
                        doc.close()
                        return cin
            doc.close()
        except Exception as e:
            print(f"  [CIN Regex/fitz] Error: {e}")

        # Pass C: Broader pattern — look for "CIN" label followed by any 21-char alphanumeric
        broader = re.compile(r'CIN\s*[:\-]?\s*([A-Z0-9]{21})', re.IGNORECASE)
        try:
            for page_num in range(min(10, len(pdf.pages))):
                text = pdf.pages[page_num].extract_text() or ""
                m = broader.search(text)
                if m:
                    candidate = m.group(1)
                    print(f"  [CIN Regex/broad] Found candidate: {candidate}")
                    return candidate
        except Exception as e:
            print(f"  [CIN Regex/broad] Error: {e}")

        # Pass D: pdfplumber table cells — CIN often lives in a styled header table
        try:
            for page_num in range(min(10, len(pdf.pages))):
                tables = pdf.pages[page_num].extract_tables() or []
                for table in tables:
                    for row in (table or []):
                        for cell in (row or []):
                            cell_text = str(cell or "").strip()
                            matches = CIN_PATTERN.findall(cell_text)
                            if matches:
                                cin = matches[0]
                                print(f"  [CIN Regex/table-cell] Found on page {page_num+1}: {cin}")
                                return cin
                            # Also try broader match in cell
                            m = broader.search(cell_text)
                            if m:
                                candidate = m.group(1)
                                print(f"  [CIN Regex/table-cell broad] Found: {candidate}")
                                return candidate
        except Exception as e:
            print(f"  [CIN Regex/table-cell] Error: {e}")

        print("  [CIN Regex] Not found in first 10 pages — will remain NULL")
        return None

    # ------------------------------------------------------------------ #
    def _compute_ratios(self, data: dict) -> dict:
        """
        FIX #3: Compute all derivable ratios.
        For finance_cost: if still NULL after extraction, estimate from
        outstanding debt × assumed interest rate (fallback only).
        """
        if not data or data.get("parse_error"):
            return data

        def sf(val):
            try: return float(val) if val is not None else None
            except Exception: return None

        rev    = sf(data.get("revenue_crores"))
        pat    = sf(data.get("profit_after_tax_crores"))
        pbt    = sf(data.get("profit_before_tax_crores"))
        ebitda = sf(data.get("ebitda_crores"))
        dep    = sf(data.get("depreciation_crores"))
        fin    = sf(data.get("finance_cost_crores"))
        assets = sf(data.get("total_assets_crores"))
        nw     = sf(data.get("net_worth_crores"))
        debt   = sf(data.get("total_borrowings_crores"))
        ca     = sf(data.get("current_assets_crores"))
        cl     = sf(data.get("current_liabilities_crores"))
        lt_d   = sf(data.get("long_term_borrowings_crores"))
        st_d   = sf(data.get("short_term_borrowings_crores"))
        ocf    = sf(data.get("operating_cash_flow_crores"))
        cash   = sf(data.get("cash_and_equivalents_crores"))

        computed = []

        # Total Debt from components
        if debt is None and lt_d is not None and st_d is not None:
            debt = lt_d + st_d
            data["total_borrowings_crores"] = round(debt, 2)
            computed.append(f"Debt={debt:.0f}Cr")

        # FIX #3 — Finance cost fallback: estimate from debt × 8.5% weighted avg rate
        if fin is None and debt is not None and debt > 0:
            ASSUMED_RATE = 0.085  # 8.5% weighted average cost of debt (Indian large corp)
            fin_estimated = debt * ASSUMED_RATE
            data["finance_cost_crores"]       = round(fin_estimated, 2)
            data["finance_cost_estimated"]    = True
            data["finance_cost_note"]         = f"Estimated: Total debt {debt:.0f}Cr × {ASSUMED_RATE*100:.1f}% assumed rate"
            fin = fin_estimated
            computed.append(f"FinCost≈{fin:.0f}Cr (estimated)")
            print(f"  [RatioEngine] Finance cost estimated from debt: {fin:.0f} Cr")

        # EBITDA = PBT + Finance Cost + Depreciation
        if ebitda is None and pbt is not None and fin is not None and dep is not None:
            ebitda = pbt + fin + dep
            data["ebitda_crores"] = round(ebitda, 2)
            data["ebitda_computed_from"] = "PBT + FinanceCost + Depreciation"
            computed.append(f"EBITDA={ebitda:.0f}Cr")

        # EBITDA approximate from PAT if dep also missing
        if ebitda is None and pat is not None and fin is not None:
            dep_est = (pat * 1.35) * 0.15  # rough estimate
            ebitda = (pat * 1.35) + fin + dep_est
            data["ebitda_crores"] = round(ebitda, 2)
            data["ebitda_computed_from"] = "PAT×1.35 + FinCost + est.Dep (approximated)"
            computed.append(f"EBITDA≈{ebitda:.0f}Cr")

        # EBITDA Margin
        if data.get("ebitda_margin_percent") is None and ebitda and rev and rev > 0:
            data["ebitda_margin_percent"] = round((ebitda / rev) * 100, 2)
            computed.append(f"EBITDA_margin={data['ebitda_margin_percent']:.1f}%")

        # Debt/Equity
        if data.get("debt_equity_ratio") is None and debt is not None and nw and nw > 0:
            data["debt_equity_ratio"] = round(debt / nw, 2)
            computed.append(f"D/E={data['debt_equity_ratio']:.2f}x")

        # Current Ratio
        if data.get("current_ratio") is None and ca is not None and cl and cl > 0:
            data["current_ratio"] = round(ca / cl, 2)
            computed.append(f"CR={data['current_ratio']:.2f}x")

        # ICR = EBITDA / Finance Cost
        if data.get("interest_coverage_ratio") is None and ebitda and fin and fin > 0:
            data["interest_coverage_ratio"] = round(ebitda / fin, 2)
            computed.append(f"ICR={data['interest_coverage_ratio']:.2f}x")

        # DSCR ≈ OCF / (Finance Cost + ST Debt)
        if ocf and fin and fin > 0:
            denom = fin + (st_d or 0)
            if denom > 0:
                data["dscr_approximate"] = round(ocf / denom, 2)
                computed.append(f"DSCR≈{data['dscr_approximate']:.2f}x")

        # ROE
        if data.get("return_on_equity_percent") is None and pat is not None and nw and nw > 0:
            data["return_on_equity_percent"] = round((pat / nw) * 100, 2)
            computed.append(f"ROE={data['return_on_equity_percent']:.1f}%")

        # ROA
        if data.get("return_on_assets_percent") is None and pat is not None and assets and assets > 0:
            data["return_on_assets_percent"] = round((pat / assets) * 100, 2)

        # Net Debt and Net D/E
        if debt is not None and cash is not None:
            data["net_debt_crores"] = round(debt - cash, 2)
            if nw and nw > 0:
                data["net_debt_equity_ratio"] = round(data["net_debt_crores"] / nw, 2)
                computed.append(f"NetD/E={data['net_debt_equity_ratio']:.2f}x")

        if computed:
            print(f"  [RatioEngine] Computed: {', '.join(computed)}")
            data["ratios_computed"] = computed

        # ── SANITY VALIDATION GUARDS ──────────────────────────────────── #
        # Guard 1: Total Borrowings cannot exceed Total Assets
        # If it does, the LLM confused Total Liabilities with Borrowings
        _debt  = data.get("total_borrowings_crores")
        _nw    = data.get("net_worth_crores")
        _assets = data.get("total_assets_crores")
        if _debt is not None and _assets is not None and _debt > _assets * 0.85:
            print(f"  [SanityCheck] FAIL: total_borrowings {_debt:.0f} > 85% of assets {_assets:.0f} — likely confusion with total_liabilities. Nulling.")
            data["total_borrowings_crores"]       = None
            data["total_borrowings_suspect"]      = True
            data["total_borrowings_original"]     = _debt
            # Also null the computed D/E since it was based on wrong debt
            if data.get("debt_equity_ratio") is not None and _nw and _debt / _nw > 3.0:
                data["debt_equity_ratio"] = None
                print(f"  [SanityCheck] D/E nulled — was based on suspect borrowings figure")
            # Attempt recompute from LT + ST borrowings if those exist
            lt = data.get("long_term_borrowings_crores")
            st = data.get("short_term_borrowings_crores")
            if lt is not None and st is not None and (lt + st) < _assets * 0.85:
                data["total_borrowings_crores"] = round(lt + st, 2)
                print(f"  [SanityCheck] total_borrowings recomputed from LT+ST: {data['total_borrowings_crores']:.0f} Cr")
                if _nw and _nw > 0:
                    data["debt_equity_ratio"] = round(data["total_borrowings_crores"] / _nw, 2)
                    print(f"  [SanityCheck] D/E recomputed: {data['debt_equity_ratio']:.2f}x")
            elif lt is not None and lt < _assets * 0.85:
                data["total_borrowings_crores"] = lt
                print(f"  [SanityCheck] total_borrowings set to LT borrowings only: {lt:.0f} Cr")

        # Guard 2: current_assets == current_liabilities exactly → extraction error
        _ca = data.get("current_assets_crores")
        _cl = data.get("current_liabilities_crores")
        if _ca is not None and _cl is not None and _ca == _cl:
            print(f"  [SanityCheck] FAIL: current_assets == current_liabilities ({_ca:.0f}) exactly — LLM duplication. Nulling both.")
            data["current_assets_crores"]    = None
            data["current_liabilities_crores"] = None
            data["current_ratio"]            = None
            data["current_ratio_suspect"]    = True

        # Guard 3: current_ratio must be between 0.1 and 10 to be realistic
        _cr = data.get("current_ratio")
        if _cr is not None and not (0.1 <= _cr <= 10.0):
            print(f"  [SanityCheck] current_ratio {_cr} out of range — nulling")
            data["current_ratio"] = None

        # Guard 4: debt_equity_ratio > 20 is almost certainly wrong for a non-NBFC
        _de = data.get("debt_equity_ratio")
        if _de is not None and _de > 20:
            print(f"  [SanityCheck] D/E {_de:.1f} unrealistically high — nulling")
            data["debt_equity_ratio"] = None

        # Guard 5: Finance cost < 0.15% of revenue is almost certainly a sub-item, not total
        # (₹405 Cr on ₹4,39,695 Cr revenue = 0.09% — clearly a sub-item, not total finance cost)
        _fin  = data.get("finance_cost_crores")
        _rev2 = data.get("revenue_crores")
        if _fin is not None and _rev2 is not None and _rev2 > 5000:
            fin_pct = _fin / _rev2 * 100
            if fin_pct < 0.15:  # Less than 0.15% of revenue = suspect
                print(f"  [SanityCheck] FAIL: finance_cost {_fin:.0f} Cr is only {fin_pct:.3f}% of revenue — likely a sub-item. Nulling.")
                data["finance_cost_crores"]        = None
                data["finance_cost_suspect"]       = True
                data["finance_cost_original"]      = _fin
                # Also null ICR since it was computed from wrong finance_cost
                if data.get("interest_coverage_ratio") is not None:
                    icr_val = data["interest_coverage_ratio"]
                    if icr_val > 50:  # ICR > 50x is unrealistic for a leveraged corporate
                        data["interest_coverage_ratio"] = None
                        print(f"  [SanityCheck] ICR {icr_val:.1f}x nulled — was based on suspect finance_cost")

        return data

    # ------------------------------------------------------------------ #
    def _extract_gst(self, pdf) -> dict:
        text = ""
        for page in pdf.pages[:20]:
            text += page.extract_text() or ""
        result = self._ai_extract_income(text[:8000], "")
        return self._compute_ratios(result)

    def _extract_bank_statement(self, pdf) -> dict:
        text, tables = "", []
        for page in pdf.pages[:30]:
            text += page.extract_text() or ""
            for t in (page.extract_tables() or []):
                tables.append(t)
        result = self._ai_extract_income(text[:8000], json.dumps(tables[:10])[:3000])
        return self._compute_ratios(result)

    def _extract_generic(self, pdf, doc_type: str) -> dict:
        text = ""
        for page in pdf.pages[:15]:
            text += page.extract_text() or ""
        result = self._ai_extract_income(text[:8000], "")
        return self._compute_ratios(result)

    # ------------------------------------------------------------------ #
    def _parse_json(self, text: str) -> dict:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*',     '', text)
            return json.loads(text.strip())
        except Exception:
            return {"raw_response": text[:300], "parse_error": True, "red_flags": {}}