import os
import json
from datetime import datetime
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from google import genai
from utils.prompt_loader import PromptLoader
from dotenv import load_dotenv
import re

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class CAMGenerator:
    """
    Generates a professional Credit Appraisal Memo (CAM)
    in Word format - exactly like a real Indian bank/NBFC memo.
    """

    def __init__(
        self,
        company_name: str,
        financials: dict,
        research: dict,
        five_cs: dict,
        recommendation: dict,
        manual_notes: str = "",
        loan_amount: str = "Not specified",
        loan_purpose: str = "Working Capital / Term Loan",
    ):
        self.company_name = company_name
        self.financials = financials
        self.research = research
        self.five_cs = five_cs
        self.recommendation = recommendation
        self.manual_notes = manual_notes
        self.loan_amount = loan_amount
        self.loan_purpose = loan_purpose
        self.model = "gemini-2.0-flash"
        self.doc = Document()

    def generate(self, output_path: str = None) -> str:
        """Generate the full CAM document and save to file"""
        print(f"[CAMGenerator] Generating CAM for {self.company_name}...")

        # get AI-written content
        cam_content = self._generate_cam_content()

        # build the Word document
        self._setup_document_styles()
        self._add_header()
        self._add_executive_summary(cam_content)
        self._add_company_background(cam_content)
        self._add_financial_analysis()
        self._add_five_cs_table()
        self._add_risk_assessment(cam_content)
        self._add_early_warning_signals()
        self._add_recommendation_section()
        self._add_footer()

        # save
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = re.sub(r'[^\w\s-]', '', self.company_name).strip()
            output_path = f"outputs/CAM_{safe_name}_{timestamp}.docx"

        os.makedirs("outputs", exist_ok=True)
        self.doc.save(output_path)
        print(f"[CAMGenerator] CAM saved to: {output_path}")
        return output_path

    def _generate_cam_content(self) -> dict:
        """Use Gemini to generate professional CAM text content"""
        prompt = PromptLoader.load("cam", "cam_template", {
            "company_name": self.company_name,
            "date": datetime.now().strftime("%d %B %Y"),
            "loan_amount": self.loan_amount,
            "loan_purpose": self.loan_purpose,
            "financials": json.dumps(self.financials, indent=2)[:1500],
            "research": json.dumps(self.research, indent=2)[:1500],
            "five_cs": json.dumps(self.five_cs, indent=2)[:1500],
            "manual_notes": self.manual_notes or "No manual notes provided.",
        })

        # instruct Gemini to return JSON sections
        prompt += """

Return ONLY valid JSON with these keys:
executive_summary (string),
company_background (string),
financial_analysis (string),
risk_assessment (string),
early_warning_signals (list of strings),
recommendation_narrative (string).
"""
        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return self._parse_json(response.text)

    def _setup_document_styles(self):
        """Set up document margins and default styles"""
        from docx.shared import Cm
        section = self.doc.sections[0]
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    def _add_header(self):
        """Add professional bank header"""
        # company header bar
        header_para = self.doc.add_paragraph()
        header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = header_para.add_run("VIVRITI CAPITAL LIMITED")
        run.bold = True
        run.font.size = Pt(16)
        run.font.color.rgb = RGBColor(0x00, 0x52, 0x8C)

        sub_header = self.doc.add_paragraph()
        sub_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run2 = sub_header.add_run("Credit Appraisal Memorandum (CAM)")
        run2.bold = True
        run2.font.size = Pt(13)

        # divider line
        self._add_horizontal_line()

        # CAM details table
        table = self.doc.add_table(rows=2, cols=4)
        table.style = "Table Grid"

        details = [
            ["Company Name", self.company_name,
             "Date", datetime.now().strftime("%d-%b-%Y")],
            ["Loan Amount", self.loan_amount,
             "Purpose", self.loan_purpose],
        ]

        for i, row_data in enumerate(details):
            row = table.rows[i]
            for j, cell_text in enumerate(row_data):
                cell = row.cells[j]
                cell.text = cell_text
                if j % 2 == 0:  # label cells
                    cell.paragraphs[0].runs[0].bold = True
                    self._shade_cell(cell, "E8F0FE")

        self.doc.add_paragraph()

    def _add_executive_summary(self, cam_content: dict):
        """Add executive summary section"""
        self._add_section_heading("1. EXECUTIVE SUMMARY")

        summary = cam_content.get(
            "executive_summary",
            "Executive summary not available."
        )
        self.doc.add_paragraph(summary)

        # recommendation badge
        decision = self.recommendation.get("decision", "PENDING")
        color_map = {
            "APPROVE": "00B050",
            "CONDITIONAL_APPROVE": "FF8C00",
            "REJECT": "FF0000",
        }
        color = color_map.get(decision, "808080")

        rec_para = self.doc.add_paragraph()
        rec_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = rec_para.add_run(f"  RECOMMENDATION: {decision}  ")
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        self._shade_paragraph_background(rec_para, color)

        self.doc.add_paragraph()

    def _add_company_background(self, cam_content: dict):
        """Add company background section"""
        self._add_section_heading("2. COMPANY BACKGROUND")

        background = cam_content.get(
            "company_background",
            "Company background not available."
        )
        self.doc.add_paragraph(background)

        # basic info table if available
        basic = self.financials.get("basic_info", {})
        if basic and not basic.get("parse_error"):
            self.doc.add_paragraph()
            table = self.doc.add_table(rows=1, cols=2)
            table.style = "Table Grid"

            # header
            header_row = table.rows[0]
            header_row.cells[0].text = "Parameter"
            header_row.cells[1].text = "Details"
            for cell in header_row.cells:
                cell.paragraphs[0].runs[0].bold = True
                self._shade_cell(cell, "1F3864")
                cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(
                    0xFF, 0xFF, 0xFF
                )

            fields = [
                ("Company Name", basic.get("company_name", "N/A")),
                ("CIN", basic.get("cin", "N/A")),
                ("Registered Address", basic.get("address", "N/A")),
                ("Nature of Business", basic.get("business_nature", "N/A")),
                ("Year of Incorporation", str(basic.get("incorporation_year", "N/A"))),
                ("Directors/Promoters", ", ".join(basic.get("directors", []) or [])),
            ]

            for label, value in fields:
                row = table.add_row()
                row.cells[0].text = label
                row.cells[0].paragraphs[0].runs[0].bold = True
                self._shade_cell(row.cells[0], "E8F0FE")
                row.cells[1].text = str(value) if value else "N/A"

        self.doc.add_paragraph()

    def _add_financial_analysis(self):
        """Add financial analysis with key ratios table"""
        self._add_section_heading("3. FINANCIAL ANALYSIS")

        fin = self.financials.get("financials", {})

        if fin and not fin.get("parse_error"):
            # key financials table
            table = self.doc.add_table(rows=1, cols=3)
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER

            # header row
            headers = ["Financial Metric", "Current Year (₹ Cr)", "Assessment"]
            header_row = table.rows[0]
            for i, h in enumerate(headers):
                header_row.cells[i].text = h
                header_row.cells[i].paragraphs[0].runs[0].bold = True
                self._shade_cell(header_row.cells[i], "1F3864")
                header_row.cells[i].paragraphs[0].runs[0].font.color.rgb = (
                    RGBColor(0xFF, 0xFF, 0xFF)
                )

            # financial rows
            metrics = [
                ("Total Revenue/Turnover",
                 fin.get("revenue_current"),
                 self._assess_metric("revenue", fin.get("revenue_current"))),
                ("EBITDA",
                 fin.get("ebitda"),
                 self._assess_metric("ebitda", fin.get("ebitda"))),
                ("PAT (Profit After Tax)",
                 fin.get("pat"),
                 self._assess_metric("pat", fin.get("pat"))),
                ("Total Assets",
                 fin.get("total_assets"),
                 "—"),
                ("Net Worth / Equity",
                 fin.get("net_worth"),
                 self._assess_metric("net_worth", fin.get("net_worth"))),
                ("Total Debt / Borrowings",
                 fin.get("total_debt"),
                 "—"),
                ("Current Ratio",
                 fin.get("current_ratio"),
                 self._assess_metric("current_ratio", fin.get("current_ratio"))),
                ("Debt to Equity",
                 fin.get("debt_to_equity"),
                 self._assess_metric("debt_equity", fin.get("debt_to_equity"))),
            ]

            for label, value, assessment in metrics:
                row = table.add_row()
                row.cells[0].text = label
                row.cells[0].paragraphs[0].runs[0].bold = True
                self._shade_cell(row.cells[0], "E8F0FE")
                row.cells[1].text = str(value) if value is not None else "N/A"
                row.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                row.cells[2].text = assessment

        self.doc.add_paragraph()

    def _add_five_cs_table(self):
        """Add Five Cs scoring table - the most impressive visual"""
        self._add_section_heading("4. FIVE Cs CREDIT ASSESSMENT")

        table = self.doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"

        headers = ["Credit Factor", "Score (0-100)", "Weight", "Rationale"]
        header_row = table.rows[0]
        for i, h in enumerate(headers):
            header_row.cells[i].text = h
            header_row.cells[i].paragraphs[0].runs[0].bold = True
            self._shade_cell(header_row.cells[i], "1F3864")
            header_row.cells[i].paragraphs[0].runs[0].font.color.rgb = (
                RGBColor(0xFF, 0xFF, 0xFF)
            )

        five_cs_data = [
            ("Character", "character_score", "character_rationale", "25%"),
            ("Capacity", "capacity_score", "capacity_rationale", "30%"),
            ("Capital", "capital_score", "capital_rationale", "20%"),
            ("Collateral", "collateral_score", "collateral_rationale", "15%"),
            ("Conditions", "conditions_score", "conditions_rationale", "10%"),
        ]

        for label, score_key, rationale_key, weight in five_cs_data:
            row = table.add_row()
            score = self.five_cs.get(score_key, "N/A")
            rationale = self.five_cs.get(rationale_key, "N/A")

            row.cells[0].text = label
            row.cells[0].paragraphs[0].runs[0].bold = True
            self._shade_cell(row.cells[0], "E8F0FE")
            row.cells[1].text = str(score)
            row.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

            # color code the score
            if isinstance(score, (int, float)):
                if score >= 70:
                    self._shade_cell(row.cells[1], "C6EFCE")
                elif score >= 50:
                    self._shade_cell(row.cells[1], "FFEB9C")
                else:
                    self._shade_cell(row.cells[1], "FFC7CE")

            row.cells[2].text = weight
            row.cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            row.cells[3].text = str(rationale)

        # overall score row
        overall_row = table.add_row()
        overall_score = self.recommendation.get("final_score", "N/A")
        rating = self.recommendation.get("rating", "N/A")

        overall_row.cells[0].text = "OVERALL SCORE"
        overall_row.cells[0].paragraphs[0].runs[0].bold = True
        self._shade_cell(overall_row.cells[0], "1F3864")
        overall_row.cells[0].paragraphs[0].runs[0].font.color.rgb = (
            RGBColor(0xFF, 0xFF, 0xFF)
        )
        overall_row.cells[1].text = f"{overall_score}/100"
        overall_row.cells[1].paragraphs[0].runs[0].bold = True
        overall_row.cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        overall_row.cells[2].text = f"Rating: {rating}"
        overall_row.cells[2].paragraphs[0].runs[0].bold = True
        self._shade_cell(overall_row.cells[1], "BDD7EE")
        self._shade_cell(overall_row.cells[2], "BDD7EE")

        self.doc.add_paragraph()

    def _add_risk_assessment(self, cam_content: dict):
        """Add risk assessment narrative"""
        self._add_section_heading("5. RISK ASSESSMENT")

        risk_text = cam_content.get(
            "risk_assessment",
            "Risk assessment not available."
        )
        self.doc.add_paragraph(risk_text)
        self.doc.add_paragraph()

    def _add_early_warning_signals(self):
        """Add early warning signals section"""
        self._add_section_heading("6. EARLY WARNING SIGNALS")

        # from red flags
        red_flags = self.financials.get("red_flags", {})
        flags_list = red_flags.get("red_flags", [])

        # from research
        research_risks = []
        for key in ["company_news", "litigation", "regulatory"]:
            section = self.research.get(key, {})
            if isinstance(section, dict):
                risks = section.get("risk_signals", [])
                if risks:
                    research_risks.extend(risks)

        all_signals = list(set(flags_list + research_risks))

        if all_signals:
            table = self.doc.add_table(rows=1, cols=3)
            table.style = "Table Grid"

            headers = ["#", "Warning Signal", "Severity"]
            header_row = table.rows[0]
            for i, h in enumerate(headers):
                header_row.cells[i].text = h
                header_row.cells[i].paragraphs[0].runs[0].bold = True
                self._shade_cell(header_row.cells[i], "FF0000")
                header_row.cells[i].paragraphs[0].runs[0].font.color.rgb = (
                    RGBColor(0xFF, 0xFF, 0xFF)
                )

            severity = red_flags.get("severity", "medium")
            for i, signal in enumerate(all_signals[:10], 1):
                row = table.add_row()
                row.cells[0].text = str(i)
                row.cells[1].text = str(signal)
                row.cells[2].text = severity.upper()
                if severity == "high":
                    self._shade_cell(row.cells[2], "FFC7CE")
                elif severity == "medium":
                    self._shade_cell(row.cells[2], "FFEB9C")
        else:
            self.doc.add_paragraph(
                "No significant early warning signals identified."
            )

        # manual notes
        if self.manual_notes:
            self.doc.add_paragraph()
            notes_heading = self.doc.add_paragraph()
            run = notes_heading.add_run("Credit Officer Field Notes:")
            run.bold = True
            run.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
            self.doc.add_paragraph(self.manual_notes)

        self.doc.add_paragraph()

    def _add_recommendation_section(self):
        """Add final recommendation - the most important section"""
        self._add_section_heading("7. RECOMMENDATION & DECISION")

        decision = self.recommendation.get("decision", "PENDING")
        amount = self.recommendation.get("recommended_amount_crores")
        rate = self.recommendation.get("interest_rate_percent")
        tenure = self.recommendation.get("tenure_months")
        rationale = self.recommendation.get("decision_rationale", "")
        conditions = self.recommendation.get("key_conditions", [])
        rejection_reason = self.recommendation.get("rejection_reason")

        # decision summary table
        table = self.doc.add_table(rows=1, cols=2)
        table.style = "Table Grid"

        decision_data = [
            ("CREDIT DECISION", decision),
            ("Recommended Amount",
             f"₹ {amount} Crores" if amount else "N/A"),
            ("Interest Rate",
             f"{rate}% p.a." if rate else "N/A"),
            ("Tenure",
             f"{tenure} months" if tenure else "N/A"),
            ("Risk Premium",
             f"{self.recommendation.get('risk_premium_percent', 'N/A')}%"),
            ("Credit Rating",
             self.recommendation.get("rating", "N/A")),
        ]

        header_row = table.rows[0]
        header_row.cells[0].text = "Parameter"
        header_row.cells[1].text = "Value"
        for cell in header_row.cells:
            cell.paragraphs[0].runs[0].bold = True
            self._shade_cell(cell, "1F3864")
            cell.paragraphs[0].runs[0].font.color.rgb = (
                RGBColor(0xFF, 0xFF, 0xFF)
            )

        color_map = {
            "APPROVE": "C6EFCE",
            "CONDITIONAL_APPROVE": "FFEB9C",
            "REJECT": "FFC7CE",
        }
        decision_color = color_map.get(decision, "FFFFFF")

        for label, value in decision_data:
            row = table.add_row()
            row.cells[0].text = label
            row.cells[0].paragraphs[0].runs[0].bold = True
            self._shade_cell(row.cells[0], "E8F0FE")
            row.cells[1].text = str(value) if value else "N/A"
            if label == "CREDIT DECISION":
                self._shade_cell(row.cells[1], decision_color)
                row.cells[1].paragraphs[0].runs[0].bold = True

        self.doc.add_paragraph()

        # rationale
        rationale_heading = self.doc.add_paragraph()
        run = rationale_heading.add_run("Decision Rationale:")
        run.bold = True
        run.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
        self.doc.add_paragraph(rationale or "No rationale provided.")

        # rejection reason
        if rejection_reason:
            self.doc.add_paragraph()
            rej_heading = self.doc.add_paragraph()
            run = rej_heading.add_run("Reason for Rejection:")
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
            self.doc.add_paragraph(rejection_reason)

        # conditions precedent
        if conditions:
            self.doc.add_paragraph()
            cond_heading = self.doc.add_paragraph()
            run = cond_heading.add_run("Conditions Precedent:")
            run.bold = True
            run.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
            for i, condition in enumerate(conditions, 1):
                self.doc.add_paragraph(
                    f"{i}. {condition}",
                    style="List Number"
                )

        self.doc.add_paragraph()

    def _add_footer(self):
        """Add document footer"""
        self._add_horizontal_line()
        footer_para = self.doc.add_paragraph()
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer_para.add_run(
            f"Generated by Intelli-Credit AI Engine  |  "
            f"DOMINIX  |  {datetime.now().strftime('%d-%b-%Y %H:%M')}  |  "
            f"CONFIDENTIAL - For Internal Use Only"
        )
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    # ── Helper Methods ──────────────────────────────────────

    def _add_section_heading(self, text: str):
        """Add a styled section heading"""
        para = self.doc.add_paragraph()
        run = para.add_run(text)
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
        para.paragraph_format.space_before = Pt(12)
        para.paragraph_format.space_after = Pt(6)

    def _add_horizontal_line(self):
        """Add a horizontal divider line"""
        para = self.doc.add_paragraph()
        pPr = para._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        bottom = OxmlElement('w:bottom')
        bottom.set(qn('w:val'), 'single')
        bottom.set(qn('w:sz'), '6')
        bottom.set(qn('w:space'), '1')
        bottom.set(qn('w:color'), '1F3864')
        pBdr.append(bottom)
        pPr.append(pBdr)

    def _shade_cell(self, cell, hex_color: str):
        """Apply background color to a table cell"""
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), hex_color)
        tcPr.append(shd)

    def _shade_paragraph_background(self, para, hex_color: str):
        """Shade paragraph background (for recommendation badge)"""
        pPr = para._p.get_or_add_pPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), hex_color)
        pPr.append(shd)

    def _assess_metric(self, metric: str, value) -> str:
        """Simple assessment of financial metrics"""
        if value is None:
            return "N/A"
        try:
            v = float(value)
        except Exception:
            return "N/A"

        assessments = {
            "current_ratio": (
                "Strong" if v >= 2 else
                "Adequate" if v >= 1.2 else "Weak"
            ),
            "debt_equity": (
                "Conservative" if v <= 1 else
                "Moderate" if v <= 2.5 else "High Leverage"
            ),
            "pat": (
                "Profitable" if v > 0 else "Loss Making"
            ),
            "net_worth": (
                "Strong" if v > 100 else
                "Adequate" if v > 20 else "Thin"
            ),
            "ebitda": (
                "Strong" if v > 50 else
                "Adequate" if v > 10 else "Weak"
            ),
            "revenue": (
                "Large" if v > 500 else
                "Mid-size" if v > 100 else "Small"
            ),
        }
        return assessments.get(metric, "—")

    def _parse_json(self, text: str) -> dict:
        """Safely parse Gemini JSON response"""
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()
            return json.loads(text)
        except Exception:
            return {
                "executive_summary": text[:500],
                "company_background": "See full analysis above.",
                "financial_analysis": "Refer to financial tables.",
                "risk_assessment": "Refer to Five Cs assessment.",
                "early_warning_signals": [],
                "recommendation_narrative": text[-500:],
            }