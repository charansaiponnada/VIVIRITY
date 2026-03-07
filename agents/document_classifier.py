import re


class DocumentClassifier:

    DOCUMENT_TYPES = {
        "annual_report": [
            "annual report", "directors report", "board report",
            "balance sheet", "profit and loss", "statement of profit",
            "auditor", "annual general meeting",
            "integrated annual report",
            "management discussion and analysis",
            "corporate governance report",
            "standalone financial",
            "consolidated financial",
            "notes to financial statements",
        ],
        "gst_filing": [
            "gstr", "outward supply", "inward supply",
            "input tax credit", "gstin", "gst return",
        ],
        "bank_statement": [
            "account statement", "opening balance", "closing balance",
            "transaction date", "neft", "rtgs", "imps",
            "debit", "credit", "bank statement",
        ],
        "legal_notice": [
            "legal notice", "court", "plaintiff",
            "defendant", "summons", "decree", "writ petition",
        ],
        "sanction_letter": [
            "sanction", "sanctioned limit", "facility letter",
            "terms and conditions", "repayment schedule",
        ],
        "cibil_report": [
            "cibil", "credit bureau", "credit score",
            "commercial report", "transunion", "equifax", "crif",
        ],
        "rating_report": [
            "credit rating", "crisil", "icra", "care ratings",
            "rating assigned", "rating action", "rating outlook",
        ],
    }

    # priority order — first match wins
    PRIORITY = [
        "annual_report",
        "gst_filing",
        "bank_statement",
        "legal_notice",
        "sanction_letter",
        "cibil_report",
        "rating_report",
    ]

    def classify(self, parser) -> str:
        """
        Classify document by scanning first 8 pages only.
        Uses priority ordering so annual_report beats rating_report.
        """
        # ── get page count from parser, not classifier ──────
        page_count = parser.page_count  # parser has this attribute

        sample_text = ""
        for page_num in range(1, min(9, page_count + 1)):
            page_data = parser.pages.get(page_num, {})
            sample_text += page_data.get("text", "")

        # fallback: if pages not yet populated (parse() not called),
        # use PyMuPDF directly for a quick text grab
        if not sample_text.strip():
            try:
                import fitz
                doc = fitz.open(parser.pdf_path)
                for i in range(min(8, len(doc))):
                    sample_text += doc[i].get_text("text") or ""
                doc.close()
            except Exception:
                pass

        sample_lower = sample_text.lower()

        scores = {}
        for doc_type, keywords in self.DOCUMENT_TYPES.items():
            scores[doc_type] = sum(
                1 for kw in keywords if kw in sample_lower
            )

        # priority order — first type with score > 0 wins
        for doc_type in self.PRIORITY:
            if scores.get(doc_type, 0) > 0:
                return doc_type

        return "annual_report"  # default fallback for unknown large PDFs