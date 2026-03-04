import pdfplumber
import fitz  # PyMuPDF
import re
from pathlib import Path


class PageIndexParser:
    """
    VectorLess RAG approach - uses PDF natural structure
    (pages, sections, tables) as index instead of embeddings.
    No chunking, no vector DB, no embedding costs.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pages = {}
        self.sections = {}
        self.tables = {}
        self.financial_pages = []

    def parse(self) -> dict:
        """Main parse method - returns structured document index"""
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []

                self.pages[page_num] = {
                    "text": text,
                    "tables": tables,
                    "section": self._detect_section(text),
                    "has_financials": self._has_financial_data(text),
                }

                if self._has_financial_data(text):
                    self.financial_pages.append(page_num)

        self.sections = self._build_section_index()

        return {
            "total_pages": len(self.pages),
            "pages": self.pages,
            "sections": self.sections,
            "financial_pages": self.financial_pages,
            "summary": self._generate_summary(),
        }

    def query(self, topic: str) -> list[dict]:
        """
        VectorLess RAG query - finds relevant pages by
        structural matching, not cosine similarity
        """
        topic_lower = topic.lower()
        relevant_pages = []

        # keyword map for financial topics
        topic_keywords = {
            "revenue": ["revenue", "turnover", "sales", "income from operations"],
            "profit": ["profit", "PAT", "PBT", "EBITDA", "net income"],
            "debt": ["debt", "borrowings", "loan", "liability", "NPA"],
            "gst": ["GST", "GSTR", "tax", "indirect tax"],
            "directors": ["director", "board", "management", "promoter"],
            "litigation": ["litigation", "legal", "court", "dispute", "penalty"],
            "assets": ["assets", "fixed assets", "capital", "property"],
            "cash": ["cash flow", "liquidity", "working capital"],
        }

        keywords = []
        for key, kws in topic_keywords.items():
            if key in topic_lower or any(k in topic_lower for k in kws):
                keywords.extend(kws)

        if not keywords:
            keywords = topic_lower.split()

        for page_num, page_data in self.pages.items():
            text_lower = page_data["text"].lower()
            matches = sum(1 for kw in keywords if kw.lower() in text_lower)
            if matches > 0:
                relevant_pages.append({
                    "page": page_num,
                    "section": page_data["section"],
                    "text": page_data["text"],
                    "tables": page_data["tables"],
                    "relevance_score": matches,
                })

        # sort by relevance - most relevant first
        relevant_pages.sort(key=lambda x: x["relevance_score"], reverse=True)
        return relevant_pages[:5]  # top 5 most relevant pages

    def _detect_section(self, text: str) -> str:
        """Detect which financial section this page belongs to"""
        text_upper = text.upper() if text else ""

        section_markers = {
            "Balance Sheet": ["BALANCE SHEET", "ASSETS AND LIABILITIES"],
            "P&L Statement": ["PROFIT AND LOSS", "STATEMENT OF PROFIT", "INCOME STATEMENT"],
            "Cash Flow": ["CASH FLOW", "CASH AND CASH EQUIVALENTS"],
            "Directors Report": ["DIRECTORS' REPORT", "BOARD'S REPORT"],
            "Auditors Report": ["AUDITOR", "INDEPENDENT AUDITOR"],
            "Notes to Accounts": ["NOTES TO", "SIGNIFICANT ACCOUNTING"],
            "GST Details": ["GST", "GSTR", "INDIRECT TAX"],
            "Shareholding": ["SHAREHOLDING PATTERN", "SHARE CAPITAL"],
        }

        for section, markers in section_markers.items():
            if any(marker in text_upper for marker in markers):
                return section

        return "General"

    def _has_financial_data(self, text: str) -> bool:
        """Check if page contains financial figures"""
        if not text:
            return False
        # look for currency patterns like ₹, crore, lakh, Rs.
        patterns = [
            r'₹\s*[\d,]+',
            r'Rs\.?\s*[\d,]+',
            r'[\d,]+\s*(?:crore|lakh|lakhs|crores)',
            r'[\d]{2,}[,][\d]{2,}[,][\d]{3}',  # Indian number format
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _build_section_index(self) -> dict:
        """Build a map of section name → page numbers"""
        section_map = {}
        for page_num, page_data in self.pages.items():
            section = page_data["section"]
            if section not in section_map:
                section_map[section] = []
            section_map[section].append(page_num)
        return section_map

    def _generate_summary(self) -> dict:
        """Quick document summary"""
        return {
            "total_pages": len(self.pages),
            "sections_found": list(self.sections.keys()),
            "financial_pages_count": len(self.financial_pages),
            "financial_pages": self.financial_pages[:10],
        }


def extract_text_pymupdf(pdf_path: str) -> dict:
    """
    Fallback parser using PyMuPDF for scanned/image PDFs
    Better for low quality scanned Indian documents
    """
    doc = fitz.open(pdf_path)
    pages = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        # if text is too short, page might be scanned image
        if len(text.strip()) < 50:
            # extract with OCR hint
            text = page.get_text("blocks")
            text = " ".join([b[4] for b in text if isinstance(b[4], str)])

        pages[page_num + 1] = text

    doc.close()
    return pages