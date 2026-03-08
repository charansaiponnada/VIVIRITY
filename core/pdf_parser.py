import fitz          # PyMuPDF - fast full scan
import pdfplumber    # accurate table extraction
import re
import io

# OCR fallback for scanned PDFs — evaluation criterion #1
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("[pdf_parser] pytesseract not installed — OCR fallback disabled. "
          "Install with: pip install pytesseract Pillow")

OCR_TEXT_THRESHOLD = 50  # fewer chars than this triggers OCR

class PageIndexParser:
    """
    Two-pass VectorLess RAG:

    Pass 1 (PyMuPDF)  — scans ALL pages in ~5 sec for section detection.
                        Zero table extraction — just raw text per page.
    Pass 2 (pdfplumber) — deep table extraction on ~55 targeted pages only.

    Result: speed of native parsing + accuracy of structured extraction
            + full page-level traceability for explainability.
    """

    LARGE_PDF_THRESHOLD = 50   # pages above this trigger two-pass mode
    PAGE_BUDGET       = 70   # change to 70
    PAGES_PER_SECTION = 12    # change to 12

    def __init__(self, pdf_path: str):
        self.pdf_path        = pdf_path
        self.pages           = {}
        self.sections        = {}
        self.financial_pages = []
        self.section_ranges  = {}   # section -> [start_page, end_page]

        doc = fitz.open(pdf_path)
        self.page_count = len(doc)
        doc.close()

        self.is_large = self.page_count > self.LARGE_PDF_THRESHOLD

    # ── Public API ────────────────────────────────────────────────

    def parse(self) -> dict:
        if self.is_large:
            return self._two_pass_parse()
        return self._full_parse()

    def query(self, topic: str) -> list:
        """Return up to 5 most relevant pages for a given topic query."""
        topic_lower = topic.lower()

        topic_keywords = {
            "revenue":    ["revenue", "turnover", "sales", "income from operations"],
            "profit":     ["profit", "pat", "pbt", "ebitda", "net income"],
            "debt":       ["debt", "borrowings", "loan", "liability"],
            "gst":        ["gst", "gstr", "tax", "indirect tax"],
            "directors":  ["director", "board", "management", "promoter"],
            "litigation": ["litigation", "legal", "court", "dispute", "penalty"],
            "assets":     ["assets", "fixed assets", "capital", "property"],
            "cash":       ["cash flow", "liquidity", "working capital"],
            "net worth":  ["net worth", "equity", "shareholders funds",
                           "reserves and surplus"],
            "borrowings": ["borrowings", "term loan", "working capital loan",
                           "secured", "unsecured"],
        }

        keywords = []
        for key, kws in topic_keywords.items():
            if key in topic_lower or any(k in topic_lower for k in kws):
                keywords.extend(kws)
        if not keywords:
            keywords = topic_lower.split()

        relevant = []
        for page_num, page_data in self.pages.items():
            text_lower = page_data["text"].lower()
            matches    = sum(1 for kw in keywords if kw in text_lower)
            if matches > 0:
                relevant.append({
                    "page":            page_num,
                    "section":         page_data["section"],
                    "text":            page_data["text"],
                    "tables":          page_data.get("tables", []),
                    "relevance_score": matches,
                    "page_number":     page_data.get("page_number", page_num),
                })

        relevant.sort(key=lambda x: x["relevance_score"], reverse=True)
        return relevant[:5]

    # ── Two-pass (large PDFs) ─────────────────────────────────────

    def _two_pass_parse(self) -> dict:
        """
        Pass 1: PyMuPDF scans ALL pages (~5 sec) — section detection only.
        Pass 2: pdfplumber extracts tables from targeted pages only (~20 sec).
        """
        # ── Pass 1 ───────────────────────────────────────────
        doc        = fitz.open(self.pdf_path)
        fast_index = {}

        for page_num in range(len(doc)):
            text    = doc[page_num].get_text("text") or ""
            section = self._detect_section(text)
            fast_index[page_num + 1] = {
                "section":        section,
                "has_financials": self._has_financial_data(text),
                "text_preview":   text[:200],
                "raw_text":       text,      # kept for query fallback
            }

        doc.close()

        # ── Build section map ─────────────────────────────────
        self.section_ranges = self._build_section_ranges(fast_index)

        # ── Select target pages ───────────────────────────────
        target_pages = self._get_target_pages(fast_index)

        # ── Pass 2 ───────────────────────────────────────────
        ocr_pages_used = 0
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num in target_pages:
                if page_num > len(pdf.pages):
                    continue
                page   = pdf.pages[page_num - 1]
                text   = page.extract_text() or \
                         fast_index[page_num]["raw_text"]  # fallback to Pass 1 text
                tables = page.extract_tables() or []
                ocr_used = False

                # OCR fallback for scanned pages
                if len(text.strip()) < OCR_TEXT_THRESHOLD and OCR_AVAILABLE:
                    ocr_text = self._ocr_page(page_num - 1)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text = ocr_text
                        ocr_used = True
                        ocr_pages_used += 1

                self.pages[page_num] = {
                    "text":          text,
                    "tables":        tables,
                    "section":       fast_index[page_num]["section"],
                    "has_financials": self._has_financial_data(text),
                    "page_number":   page_num,
                    "ocr_used":      ocr_used,
                }
                if self._has_financial_data(text):
                    self.financial_pages.append(page_num)

        if ocr_pages_used:
            print(f"[OCR] Used OCR on {ocr_pages_used}/{len(target_pages)} targeted pages")

        self.sections = self._build_section_index()

        return {
            "total_pages":     self.page_count,
            "targeted_pages":  len(target_pages),
            "pages":           self.pages,
            "sections":        self.sections,
            "section_ranges":  self.section_ranges,
            "financial_pages": self.financial_pages,
            "is_sampled":      True,
            "ocr_pages_used":  ocr_pages_used,
            "summary":         self._generate_summary(),
        }

    def _get_target_pages(self, fast_index: dict) -> list:
        """
        Intelligently select which pages to deep-parse with pdfplumber.

        Strategy:
        1. First 10 pages  — company identity, CIN, directors
        2. Priority financial sections — Balance Sheet, P&L, Notes etc.
        3. Remaining budget — filled with pages flagged as financial
        """
        target_pages = set()

        # 1. Company identity pages (always first 10)
        for p in range(1, min(11, self.page_count + 1)):
            target_pages.add(p)

        # 2. Priority financial sections — ordered by importance
        priority_sections = [
            "Balance Sheet",       # assets, liabilities, net worth, total debt
            "P&L Statement",       # revenue, EBITDA, PAT
            "Notes to Accounts",   # detailed breakdown — net worth, debt schedule
            "Cash Flow",           # liquidity, working capital
            "Auditors Report",     # audit qualifications, going concern
            "Directors Report",    # management discussion, risk factors
            "GST Details",         # GSTR data, ITC
            "Shareholding",        # promoter holding pattern
        ]

        for section in priority_sections:
            if section in self.section_ranges:
                start, end = self.section_ranges[section]
                for p in range(start, min(end + 1,
                                          start + self.PAGES_PER_SECTION)):
                    target_pages.add(p)

        # 3. Fill remaining budget with financial pages
        remaining = self.PAGE_BUDGET - len(target_pages)
        if remaining > 0:
            fin_pages = [
                p for p, d in fast_index.items()
                if d["has_financials"] and p not in target_pages
            ]
            for p in sorted(fin_pages)[:remaining]:
                target_pages.add(p)

        return sorted(target_pages)

    # ── Full parse (small PDFs) ───────────────────────────────────

    def _ocr_page(self, page_num_0based: int) -> str:
        """OCR a single page using PyMuPDF pixmap + pytesseract."""
        if not OCR_AVAILABLE:
            return ""
        try:
            doc = fitz.open(self.pdf_path)
            page = doc[page_num_0based]
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            doc.close()
            text = pytesseract.image_to_string(img, lang="eng")
            return text or ""
        except Exception as e:
            print(f"[OCR] Page {page_num_0based + 1} failed: {e}")
            return ""

    def _full_parse(self) -> dict:
        """Full pdfplumber parse for documents under 50 pages."""
        ocr_pages_used = 0
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text   = page.extract_text() or ""
                tables = page.extract_tables() or []
                ocr_used = False

                # OCR fallback for scanned pages
                if len(text.strip()) < OCR_TEXT_THRESHOLD and OCR_AVAILABLE:
                    ocr_text = self._ocr_page(page_num - 1)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text = ocr_text
                        ocr_used = True
                        ocr_pages_used += 1

                self.pages[page_num] = {
                    "text":          text,
                    "tables":        tables,
                    "section":       self._detect_section(text),
                    "has_financials": self._has_financial_data(text),
                    "page_number":   page_num,
                    "ocr_used":      ocr_used,
                }
                if self._has_financial_data(text):
                    self.financial_pages.append(page_num)

        if ocr_pages_used:
            print(f"[OCR] Used OCR on {ocr_pages_used}/{len(self.pages)} pages")

        self.sections = self._build_section_index()

        return {
            "total_pages":     len(self.pages),
            "pages":           self.pages,
            "sections":        self.sections,
            "financial_pages": self.financial_pages,
            "is_sampled":      False,
            "ocr_pages_used":  ocr_pages_used,
            "summary":         self._generate_summary(),
        }

    # ── Section detection ─────────────────────────────────────────

    def _detect_section(self, text: str) -> str:
        text_upper = text.upper() if text else ""
        section_markers = {
            "Balance Sheet":     ["BALANCE SHEET",
                                  "ASSETS AND LIABILITIES"],
            "P&L Statement":     ["PROFIT AND LOSS",
                                  "STATEMENT OF PROFIT",
                                  "INCOME STATEMENT"],
            "Cash Flow":         ["CASH FLOW"],
            "Directors Report":  ["DIRECTORS' REPORT",
                                  "DIRECTORS REPORT",
                                  "BOARD'S REPORT",
                                  "MANAGEMENT DISCUSSION"],
            "Auditors Report":   ["AUDITOR",
                                  "INDEPENDENT AUDITOR"],
            "Notes to Accounts": ["NOTES TO",
                                  "SIGNIFICANT ACCOUNTING",
                                  "NOTES FORMING PART"],
            "GST Details":       ["GST",
                                  "GSTR",
                                  "INDIRECT TAX",
                                  "GOODS AND SERVICE TAX"],
            "Shareholding":      ["SHAREHOLDING PATTERN",
                                  "SHARE CAPITAL"],
        }
        for section, markers in section_markers.items():
            if any(marker in text_upper for marker in markers):
                return section
        return "General"

    # ── Financial data detection ──────────────────────────────────

    def _has_financial_data(self, text: str) -> bool:
        if not text:
            return False
        patterns = [
            r'₹\s*[\d,]+',
            r'Rs\.?\s*[\d,]+',
            r'[\d,]+\s*(?:crore|lakh)',
            r'[\d]{2,}[,][\d]{2,}[,][\d]{3}',
            r'\b\d+\.\d+\s*%',           # percentage figures
            r'(?:total|net)\s+\w+\s*\d', # "Total Assets 12345"
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    # ── Index builders ────────────────────────────────────────────

    def _build_section_ranges(self, fast_index: dict) -> dict:
        """Map each detected section to its first and last page."""
        ranges  = {}
        current = None
        start   = 1

        for page_num in sorted(fast_index.keys()):
            section = fast_index[page_num]["section"]
            if section != current:
                if current and current != "General":
                    ranges[current] = [start, page_num - 1]
                current = section
                start   = page_num

        # close the last section
        if current and current != "General":
            ranges[current] = [start, max(fast_index.keys())]

        return ranges

    def _build_section_index(self) -> dict:
        section_map = {}
        for page_num, page_data in self.pages.items():
            section = page_data["section"]
            if section not in section_map:
                section_map[section] = []
            section_map[section].append(page_num)
        return section_map

    def _generate_summary(self) -> dict:
        return {
            "total_pages":           self.page_count,
            "sections_found":        list(self.sections.keys()),
            "section_ranges":        self.section_ranges,
            "financial_pages_count": len(self.financial_pages),
        }