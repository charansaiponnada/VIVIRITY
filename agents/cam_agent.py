from core.cam_generator import CAMGenerator


class CAMAgent:
    def __init__(
        self,
        company_name: str,
        financials:   dict,
        research:     dict,
        scoring:      dict,
        cross_ref:    dict,
        manual_notes: str = "",
        loan_amount:  str = "",
        loan_purpose: str = "",
        output_dir:   str = "outputs",
    ):
        self.company_name = company_name
        self.financials   = financials
        self.research     = research
        self.scoring      = scoring
        self.cross_ref    = cross_ref
        self.manual_notes = manual_notes
        self.loan_amount  = loan_amount
        self.loan_purpose = loan_purpose
        self.output_dir   = output_dir
        self.pdf_path: str | None = None

    def run(self) -> str:
        generator = CAMGenerator(output_dir=self.output_dir)
        docx_path = generator.generate(
            company_name  = self.company_name,
            financials    = self.financials,
            research      = self.research,
            scoring       = self.scoring,
            cross_ref     = self.cross_ref,
            manual_notes  = self.manual_notes,
            loan_amount   = self.loan_amount,
            loan_purpose  = self.loan_purpose,
        )
        self.pdf_path = generator.last_pdf_path
        return docx_path