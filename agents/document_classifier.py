import re

DOCUMENT_TYPES = {
    "annual_report": [
        "annual report", "integrated annual report",
        "management discussion and analysis", "corporate governance report",
        "standalone financial statements", "consolidated financial statements",
        "notes to financial statements", "board of directors report",
        "directors report", "auditors report", "balance sheet",
        "profit and loss", "statement of profit",
    ],
    "gst_filing": [
        "gstr", "gst return", "goods and services tax return",
        "gstr-1", "gstr-3b", "gstr-2a", "gstr-9",
        "outward supplies", "inward supplies",
    ],
    "bank_statement": [
        "account statement", "bank statement", "current account",
        "savings account", "transaction history", "opening balance",
        "closing balance", "debit", "credit", "ifsc",
    ],
    "itr_filing": [
        "income tax return", "itr", "assessment year", "acknowledgement number",
        "form itr-6", "form itr-3", "profit and gains from business",
        "total taxable income", "tax paid", "tax payable", "advance tax",
        "tcs", "tds",
    ],
    "alm_report": [
        "asset liability management", "alm report", "structural liquidity",
        "interest rate sensitivity", "maturity buckets", "liquidity gap",
        "gap analysis", "dynamic liquidity", "alm statement",
    ],
    "shareholding_pattern": [
        "shareholding pattern", "distribution of shareholding",
        "promoter and promoter group", "public shareholding",
        "equity shares held", "beneficial owners", "clause 35",
    ],
    "borrowing_profile": [
        "borrowing profile", "list of lenders", "sanctioned limit",
        "outstanding balance", "interest rate", "repayment schedule",
        "secured loans", "unsecured loans", "debt profile",
    ],
    "portfolio_cuts": [
        "portfolio cuts", "performance data", "npa buckets",
        "collection efficiency", "disbursement trends", "vintage analysis",
        "par 90", "delinquency profile", "segment performance",
    ],
}

# Priority order — first match wins for ambiguous docs
PRIORITY = [
    "annual_report",
    "gst_filing",
    "bank_statement",
    "itr_filing",
    "alm_report",
    "shareholding_pattern",
    "borrowing_profile",
    "portfolio_cuts",
]


class DocumentClassifier:
    def __init__(self, parser):
        self.parser = parser

    def classify(self) -> str:
        """Classify a parsed PDF by scanning its text content."""
        text = self._get_text()
        text_lower = text.lower()

        scores: dict[str, int] = {doc_type: 0 for doc_type in DOCUMENT_TYPES}

        for doc_type, keywords in DOCUMENT_TYPES.items():
            for kw in keywords:
                if kw in text_lower:
                    scores[doc_type] += 1

        # Pick highest score, respecting priority for ties
        best_type  = "annual_report"
        best_score = 0

        for doc_type in PRIORITY:
            if scores[doc_type] > best_score:
                best_score = scores[doc_type]
                best_type  = doc_type

        # Fallback: large PDF almost certainly an annual report
        try:
            page_count = self.parser.page_count
        except AttributeError:
            page_count = len(getattr(self.parser, "pages", [])) or 0

        if best_score == 0 and page_count > 50:
            best_type = "annual_report"

        return best_type

    def _get_text(self) -> str:
        """Extract text sample from the parsed PDF for classification."""
        try:
            # Try pages attribute (pdfplumber)
            pages = getattr(self.parser, "pages", None)
            if pages:
                sample_pages = list(pages)[:10]
                texts = []
                for p in sample_pages:
                    try:
                        t = p.extract_text() or ""
                        texts.append(t)
                    except Exception:
                        pass
                return " ".join(texts)
        except Exception:
            pass

        # Fallback: PyMuPDF
        try:
            import fitz
            doc   = fitz.open(self.parser.path) if hasattr(self.parser, "path") else None
            if doc:
                text = ""
                for i in range(min(10, len(doc))):
                    text += doc[i].get_text()
                return text
        except Exception:
            pass

        return ""