class DocumentClassifier:
    """
    Classifies uploaded PDFs by type before routing to
    the right specialized agent.
    """
    
    DOCUMENT_TYPES = {
        "annual_report": [
            "annual report", "directors report", 
            "balance sheet", "profit and loss",
            "auditor", "AGM"
        ],
        "gst_filing": [
            "GSTR", "GST", "outward supply", 
            "inward supply", "ITC", "GSTIN"
        ],
        "bank_statement": [
            "account statement", "debit", "credit",
            "opening balance", "closing balance",
            "transaction date", "NEFT", "RTGS"
        ],
        "legal_notice": [
            "legal notice", "court", "plaintiff",
            "defendant", "summons", "decree"
        ],
        "sanction_letter": [
            "sanction", "sanctioned limit",
            "interest rate", "repayment",
            "terms and conditions", "facility"
        ],
        "rating_report": [
            "credit rating", "CRISIL", "ICRA",
            "CARE", "rating assigned", "outlook"
        ],
        "cibil_report": [
        "CIBIL", "credit bureau", "credit score", 
        "commercial report", "credit information",
        "TransUnion", "Equifax", "CRIF"
        ],
    }
    
    def classify(self, parser) -> str:
        """Classify document based on first 5 pages"""
        sample_text = ""
        for page_num in range(1, min(6, len(parser.pages) + 1)):
            sample_text += parser.pages.get(page_num, {}).get("text", "")
        
        sample_lower = sample_text.lower()
        scores = {}
        
        for doc_type, keywords in self.DOCUMENT_TYPES.items():
            scores[doc_type] = sum(
                1 for kw in keywords 
                if kw.lower() in sample_lower
            )
        
        best_type = max(scores, key=scores.get)
        return best_type if scores[best_type] > 0 else "unknown"