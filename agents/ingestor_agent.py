"""
Ingestor Agent
==============
Orchestrates document parsing and financial extraction.
Called by app.py as the first agent in the pipeline.
"""
import os
import time
from core.pdf_parser import PageIndexParser
from core.financial_extractor import FinancialExtractor
from agents.document_classifier import DocumentClassifier


class IngestorAgent:
    """
    Ingestor Agent — Pillar 1 of the credit appraisal pipeline.

    Responsibilities:
    - Accept multiple PDF files of different types
    - Classify each document (Annual Report / GST / Bank Statement / Legal / etc.)
    - Route to appropriate extractor
    - Merge results across documents into unified financial profile
    - Flag any document-level red flags found during parsing
    """

    def __init__(self, pdf_paths: list, log_fn=None):
        """
        pdf_paths: list of (filename, filepath) tuples
        log_fn:    optional callable for live logging to UI
        """
        self.pdf_paths  = pdf_paths
        self.log        = log_fn or print
        self.classifier = DocumentClassifier()

        # outputs
        self.documents_by_type = {}   # doc_type -> full text
        self.parsers_by_type   = {}   # doc_type -> PageIndexParser
        self.doc_types_found   = []

    def run(self) -> dict:
        """
        Run full ingestion pipeline.
        Returns unified financial profile across all documents.
        """
        self.log(f"Starting ingestion of {len(self.pdf_paths)} document(s)...")

        unified = {
            "basic_info":   {},
            "financials":   {},
            "debt_profile": {},
            "gst_analysis": {},
            "red_flags":    {"red_flags": [], "severity": "low"},
        }

        for fname, fpath in self.pdf_paths:
            self.log(f"Parsing: {fname}")

            try:
                parser   = PageIndexParser(fpath)
                parsed   = parser.parse()
                doc_type = self.classifier.classify(parser)

                self.log(
                    f"  → Classified as: {doc_type.replace('_', ' ').upper()} "
                    f"({parser.page_count} pages, "
                    f"targeted {parsed.get('targeted_pages', parser.page_count)} pages)"
                )

                # store for cross-reference agent
                full_text = "\n".join([
                    p["text"] for p in parser.pages.values()
                    if p.get("text")
                ])
                self.documents_by_type[doc_type] = full_text
                self.parsers_by_type[doc_type]   = parser
                self.doc_types_found.append(doc_type)

                # extract financials from annual report or unknown
                if doc_type in ["annual_report", "unknown", "rating_report"]:
                    self.log(f"  → Running financial extraction...")
                    extractor = FinancialExtractor(parser)
                    extracted = extractor.extract_all()

                    # merge — don't overwrite existing values with None
                    for key in unified:
                        if extracted.get(key) and not extracted[key].get("parse_error"):
                            if key == "red_flags":
                                # merge red flag lists
                                new_flags = extracted[key].get("red_flags", [])
                                existing  = unified["red_flags"]["red_flags"]
                                unified["red_flags"]["red_flags"] = existing + new_flags
                                # take higher severity
                                sev_order = {"low": 0, "medium": 1, "high": 2}
                                new_sev = extracted[key].get("severity", "low")
                                if sev_order.get(new_sev, 0) > \
                                   sev_order.get(unified["red_flags"]["severity"], 0):
                                    unified["red_flags"]["severity"] = new_sev
                            else:
                                # update only missing fields
                                for field, val in extracted[key].items():
                                    if val is not None and \
                                       unified[key].get(field) is None:
                                        unified[key][field] = val

                    self.log(f"  → Extraction complete")

                elif doc_type == "gst_filing":
                    # basic GST data from text scan
                    self.log(f"  → Scanning GST document for mismatch signals...")
                    unified = self._scan_gst_signals(parser, unified)

                elif doc_type == "legal_notice":
                    self.log(f"  → Scanning legal notice for red flags...")
                    unified = self._scan_legal_signals(parser, unified)

                elif doc_type == "sanction_letter":
                    self.log(f"  → Scanning sanction letter for existing debt...")
                    unified = self._scan_sanction_signals(parser, unified)

            except Exception as e:
                self.log(f"  ⚠ Error processing {fname}: {str(e)}")

        self.log(
            f"Ingestion complete. "
            f"Documents: {', '.join(set(self.doc_types_found))}. "
            f"Financial pages extracted."
        )

        return {
            "financials":         unified,
            "documents_by_type":  self.documents_by_type,
            "parsers_by_type":    self.parsers_by_type,
            "doc_types_found":    list(set(self.doc_types_found)),
        }

    # ── Document-type specific scanners ──────────────────────────

    def _scan_gst_signals(self, parser: PageIndexParser, unified: dict) -> dict:
        """Quick text scan of GST document for mismatch signals."""
        gst_pages = parser.query("GSTR outward supply inward ITC mismatch")
        combined  = " ".join([p["text"] for p in gst_pages[:3]])
        combined_lower = combined.lower()

        gst = unified.get("gst_analysis", {})

        if "mismatch" in combined_lower or "discrepancy" in combined_lower:
            gst["gstr_mismatch_detected"] = True
            gst["mismatch_details"] = (
                "Mismatch signals detected in GST document text"
            )

        if "circular" in combined_lower:
            gst["circular_trading_risk"] = True

        # extract GSTIN numbers
        gstins = re.findall(
            r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b',
            combined
        )
        if gstins:
            gst["gst_numbers"] = list(set(gstins))

        unified["gst_analysis"] = gst
        return unified

    def _scan_legal_signals(self, parser: PageIndexParser,
                             unified: dict) -> dict:
        """Scan legal notice for red flag keywords."""
        pages    = parser.query("court notice litigation penalty order")
        combined = " ".join([p["text"] for p in pages[:3]]).lower()

        red_flags = unified["red_flags"]["red_flags"]

        if "nclt" in combined or "insolvency" in combined:
            red_flags.append("NCLT/Insolvency proceedings mentioned in legal notice")
            unified["red_flags"]["severity"] = "high"

        if "wilful default" in combined:
            red_flags.append("Wilful defaulter mentioned in legal notice")
            unified["red_flags"]["severity"] = "high"

        if "drt" in combined:
            red_flags.append("DRT (Debt Recovery Tribunal) case mentioned")
            unified["red_flags"]["severity"] = "medium"

        if "fraud" in combined or "criminal" in combined:
            red_flags.append("Fraud/criminal proceedings mentioned in legal notice")
            unified["red_flags"]["severity"] = "high"

        unified["red_flags"]["red_flags"] = red_flags
        return unified

    def _scan_sanction_signals(self, parser: PageIndexParser,
                                unified: dict) -> dict:
        """Extract existing loan details from sanction letter."""
        pages    = parser.query("sanctioned limit interest rate repayment tenure")
        combined = " ".join([p["text"] for p in pages[:3]])

        # flag as existing debt
        debt = unified.get("debt_profile", {})
        if "sanction" in combined.lower():
            lenders = debt.get("lenders", [])
            # try to extract lender name from first page
            first_text = parser.pages.get(1, {}).get("text", "")
            if "bank" in first_text.lower() or "finance" in first_text.lower():
                lenders.append("Existing lender (from sanction letter)")
            debt["lenders"] = lenders

        unified["debt_profile"] = debt
        return unified