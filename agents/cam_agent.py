"""
CAM Agent
=========
Orchestrates Credit Appraisal Memo generation.
Wraps core/cam_generator.py with agent-level logging and error handling.
"""
import os
from core.cam_generator import CAMGenerator


class CAMAgent:
    """
    CAM Agent — Pillar 3 final output of the credit appraisal pipeline.

    Responsibilities:
    - Take outputs from all upstream agents
    - Generate a professional Word document Credit Appraisal Memo
    - Return the file path for download
    """

    def __init__(
        self,
        company_name:   str,
        financials:     dict,
        research:       dict,
        five_cs:        dict,
        recommendation: dict,
        manual_notes:   str  = "",
        loan_amount:    str  = "Not specified",
        loan_purpose:   str  = "General Corporate Purpose",
        cross_ref:      dict = None,
        log_fn=None,
    ):
        self.company_name   = company_name
        self.financials     = financials
        self.research       = research
        self.five_cs        = five_cs
        self.recommendation = recommendation
        self.manual_notes   = manual_notes
        self.loan_amount    = loan_amount
        self.loan_purpose   = loan_purpose
        self.cross_ref      = cross_ref or {}
        self.log            = log_fn or print

    def run(self) -> str:
        """
        Generate CAM document.
        Returns the output file path.
        """
        self.log(f"Generating Credit Appraisal Memo for {self.company_name}...")

        # enrich manual notes with cross-ref findings for CAM narrative
        enriched_notes = self.manual_notes or ""
        if self.cross_ref:
            integrity = self.cross_ref.get("overall_integrity_score", {})
            verdict   = integrity.get("verdict", "")
            if verdict in ["SUSPECT", "HIGH_RISK"]:
                flags = integrity.get("flags", [])
                if flags:
                    enriched_notes += (
                        f"\n\n[Cross-Document Analysis Findings]\n"
                        + "\n".join(f"- {f}" for f in flags)
                    )

        try:
            cam_gen = CAMGenerator(
                company_name   = self.company_name,
                financials     = self.financials,
                research       = self.research,
                five_cs        = self.five_cs,
                recommendation = self.recommendation,
                manual_notes   = enriched_notes,
                loan_amount    = self.loan_amount,
                loan_purpose   = self.loan_purpose,
            )
            cam_path = cam_gen.generate()
            self.log(f"CAM generated: {cam_path}")
            return cam_path

        except Exception as e:
            self.log(f"CAM generation error: {str(e)}")
            raise