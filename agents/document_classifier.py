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
    "legal_notice": [
        "legal notice", "demand notice", "notice under section",
        "writ petition", "arbitration notice", "cease and desist",
        "show cause notice", "default notice",
    ],
    "sanction_letter": [
        "sanction letter", "loan sanction", "term loan sanction",
        "credit facility", "working capital limit", "sanctioned amount",
        "repayment schedule", "moratorium period",
    ],
    "cibil_report": [
        "cibil", "credit information report", "credit score",
        "credit bureau", "transunion", "equifax",
        "credit history", "repayment history",
    ],
    "rating_report": [
        "credit rating assigned", "crisil rated", "icra rated",
        "care ratings assigned", "rating action communique",
        "rating reaffirmed", "rating upgraded", "rating downgraded",
        "brickwork ratings", "acuite ratings",
    ],
}

# Priority order — first match wins for ambiguous docs
PRIORITY = [
    "annual_report",
    "gst_filing",
    "bank_statement",
    "itr_filing",
    "legal_notice",
    "sanction_letter",
    "cibil_report",
    "rating_report",
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