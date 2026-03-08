import os
import json
from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def _set_cell_bg(cell, hex_color: str):
    """Set table cell background colour."""
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    tcPr.append(shd)


def _bold_cell(cell, text: str, font_size: int = 10, color: str = None):
    cell.text = ""
    run = cell.paragraphs[0].add_run(text)
    run.bold = True
    run.font.size = Pt(font_size)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


class CAMGenerator:
    VIVRITI_BLUE  = "1B3A6B"
    VIVRITI_GOLD  = "C9A84C"
    LIGHT_BLUE    = "E8F0FA"
    LIGHT_GREY    = "F5F5F5"
    RED_ALERT     = "C0392B"
    GREEN_OK      = "1E8449"
    ORANGE_WARN   = "D68910"

    def __init__(self, output_dir: str = "outputs"):
        os.makedirs(output_dir, exist_ok=True)
        self.output_dir = output_dir

    # ================================================================== #
    def generate(
        self,
        company_name:   str,
        financials:     dict,
        research:       dict,
        scoring:        dict,
        cross_ref:      dict,
        manual_notes:   str  = "",
        loan_amount:    str  = "",
        loan_purpose:   str  = "",
    ) -> str:
        print(f"[CAMGenerator] Generating Credit Appraisal Memo for {company_name}...")

        doc = Document()
        self._set_page_margins(doc)
        self._set_default_font(doc)

        self._add_header(doc, company_name, scoring)
        self._add_executive_summary(doc, company_name, scoring, financials, loan_amount, loan_purpose)
        self._add_company_background(doc, financials, company_name)
        self._add_financial_analysis(doc, financials)
        self._add_five_cs(doc, scoring)
        self._add_research_intelligence(doc, research, scoring)
        self._add_cross_reference(doc, cross_ref)
        if manual_notes:
            self._add_field_notes(doc, manual_notes)
        self._add_recommendation(doc, scoring)
        self._add_footer(doc)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in company_name if c.isalnum() or c in " _-")[:40]
        filename  = f"CAM_{safe_name}_{timestamp}.docx"
        filepath  = os.path.join(self.output_dir, filename)
        doc.save(filepath)
        print(f"[CAMGenerator] CAM generated: {filepath}")
        return filepath

    # ================================================================== #
    def _set_page_margins(self, doc):
        from docx.oxml import OxmlElement
        for section in doc.sections:
            section.top_margin    = Cm(1.8)
            section.bottom_margin = Cm(1.8)
            section.left_margin   = Cm(2.0)
            section.right_margin  = Cm(2.0)

    def _set_default_font(self, doc):
        doc.styles["Normal"].font.name = "Calibri"
        doc.styles["Normal"].font.size = Pt(10)

    # ================================================================== #
    def _add_header(self, doc, company_name: str, scoring: dict):
        rec    = scoring.get("recommendation", {})
        rating = rec.get("rating", scoring.get("risk_score", {}).get("rating", "N/A"))
        decision = rec.get("decision", "N/A")

        # Header table: logo area + title + decision badge
        table = doc.add_table(rows=1, cols=3)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.columns[0].width = Inches(1.5)
        table.columns[1].width = Inches(3.5)
        table.columns[2].width = Inches(2.0)

        left_cell   = table.cell(0, 0)
        mid_cell    = table.cell(0, 1)
        right_cell  = table.cell(0, 2)

        _set_cell_bg(left_cell,  self.VIVRITI_BLUE)
        _set_cell_bg(mid_cell,   self.VIVRITI_BLUE)
        _set_cell_bg(right_cell, self.VIVRITI_BLUE)

        # Left: Company
        lp = left_cell.paragraphs[0]
        lp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = lp.add_run("VIVRITI CAPITAL")
        r.bold = True; r.font.size = Pt(9); r.font.color.rgb = RGBColor.from_string(self.VIVRITI_GOLD)

        # Mid: Title
        mp = mid_cell.paragraphs[0]
        mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = mp.add_run("CREDIT APPRAISAL MEMORANDUM\n")
        r1.bold = True; r1.font.size = Pt(14); r1.font.color.rgb = RGBColor(255,255,255)
        r2 = mp.add_run(company_name)
        r2.bold = True; r2.font.size = Pt(11); r2.font.color.rgb = RGBColor.from_string(self.VIVRITI_GOLD)

        # Right: Decision badge
        decision_color = self.GREEN_OK if decision == "APPROVE" else \
                         self.ORANGE_WARN if decision == "CONDITIONAL_APPROVE" else self.RED_ALERT
        rp = right_cell.paragraphs[0]
        rp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r3 = rp.add_run(f"{decision}\n")
        r3.bold = True; r3.font.size = Pt(13); r3.font.color.rgb = RGBColor.from_string(decision_color)
        r4 = rp.add_run(f"Rating: {rating}")
        r4.bold = True; r4.font.size = Pt(11); r4.font.color.rgb = RGBColor(255,255,255)

        doc.add_paragraph()

    # ================================================================== #
    def _add_executive_summary(self, doc, company_name, scoring, financials, loan_amount, loan_purpose):
        self._section_heading(doc, "EXECUTIVE SUMMARY")

        rec         = scoring.get("recommendation", {})
        risk_score  = scoring.get("risk_score",     {})
        # Use blended score from recommendation (post-ML-blend), fall back to risk_score
        final_score = rec.get("final_score", risk_score.get("final_score", 0))
        rating      = rec.get("rating",  risk_score.get("rating",   "N/A"))
        decision    = rec.get("decision", "N/A")
        amount      = rec.get("recommended_amount_crores", loan_amount or "N/A")
        rate        = rec.get("interest_rate_percent", "N/A")
        tenure      = rec.get("tenure_months", "N/A")

        # Score card table
        table = doc.add_table(rows=2, cols=5)
        table.style = "Table Grid"
        headers = ["Credit Score", "Rating", "Decision", "Recommended Amount", "Interest Rate"]
        values  = [
            f"{final_score}/100",
            str(rating),
            str(decision),
            f"₹{amount} Cr" if amount not in ["N/A", None, ""] else "N/A",
            f"{rate}%" if rate not in ["N/A", None, ""] else "N/A",
        ]

        for i, (h, v) in enumerate(zip(headers, values)):
            hc = table.cell(0, i); vc = table.cell(1, i)
            _set_cell_bg(hc, self.VIVRITI_BLUE)
            _bold_cell(hc, h, font_size=9, color="FFFFFF")
            hc.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            vc.text = v
            vc.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            vc.paragraphs[0].runs[0].bold = True
            _set_cell_bg(vc, self.LIGHT_BLUE)

        doc.add_paragraph()

        # Decision rationale
        rationale = rec.get("decision_rationale") or rec.get("rejection_reason") or "See Five Cs analysis below."
        p = doc.add_paragraph()
        p.add_run("Decision Rationale: ").bold = True
        p.add_run(str(rationale))

        # Key conditions
        conditions = rec.get("key_conditions", [])
        if conditions:
            p2 = doc.add_paragraph()
            p2.add_run("Key Conditions: ").bold = True
            p2.add_run("; ".join(str(c) for c in conditions))

        doc.add_paragraph()
        p3 = doc.add_paragraph()
        p3.add_run(f"Date of Appraisal: ").bold = True
        p3.add_run(datetime.now().strftime("%d %B %Y"))
        if loan_purpose:
            p3.add_run(f"   |   Loan Purpose: ").bold = True
            p3.add_run(str(loan_purpose))

    # ================================================================== #
    def _add_company_background(self, doc, financials: dict, company_name: str):
        self._section_heading(doc, "COMPANY BACKGROUND")
        basic = financials if isinstance(financials, dict) else {}

        # Handle directors as list of dicts OR list of strings
        directors_raw = basic.get("directors", []) or []
        directors_str = ", ".join([
            d.get("name", str(d)) if isinstance(d, dict) else str(d)
            for d in directors_raw
        ]) or "Not extracted"

        promoters_raw = basic.get("promoters", []) or []
        promoters_str = ", ".join([
            p.get("name", str(p)) if isinstance(p, dict) else str(p)
            for p in promoters_raw
        ]) or "Not extracted"

        rows = [
            ("Company Name",     basic.get("company_name", company_name) or company_name),
            ("CIN",              basic.get("cin",          "Not extracted")),
            ("Directors",        directors_str),
            ("Promoters",        promoters_str),
            ("Extraction Notes", basic.get("extraction_notes", "—")),
        ]

        table = doc.add_table(rows=len(rows), cols=2)
        table.style = "Table Grid"
        table.columns[0].width = Inches(2.0)
        table.columns[1].width = Inches(5.0)

        for i, (label, value) in enumerate(rows):
            lc = table.cell(i, 0); vc = table.cell(i, 1)
            _set_cell_bg(lc, self.LIGHT_BLUE)
            lc.text = label; lc.paragraphs[0].runs[0].bold = True
            vc.text = str(value) if value else "—"

        doc.add_paragraph()

    # ================================================================== #
    def _add_financial_analysis(self, doc, financials: dict):
        self._section_heading(doc, "FINANCIAL ANALYSIS")

        f = financials if isinstance(financials, dict) else {}

        def fmt(val, suffix="Cr"):
            if val is None or val == "":
                return "N/A"
            try:
                return f"₹{float(val):,.0f} {suffix}"
            except Exception:
                return str(val)

        def fmt_pct(val):
            if val is None: return "N/A"
            try: return f"{float(val):.1f}%"
            except Exception: return str(val)

        def fmt_ratio(val):
            if val is None: return "N/A"
            try: return f"{float(val):.2f}x"
            except Exception: return str(val)

        rows = [
            ("Revenue",            fmt(f.get("revenue_crores"))),
            ("Revenue Growth",     fmt_pct(f.get("revenue_growth_percent"))),
            ("Profit After Tax",   fmt(f.get("profit_after_tax_crores"))),
            ("EBITDA",             fmt(f.get("ebitda_crores"))),
            ("EBITDA Margin",      fmt_pct(f.get("ebitda_margin_percent"))),
            ("Total Assets",       fmt(f.get("total_assets_crores"))),
            ("Net Worth",          fmt(f.get("net_worth_crores"))),
            ("Total Borrowings",   fmt(f.get("total_borrowings_crores"))),
            ("Debt / Equity",      fmt_ratio(f.get("debt_equity_ratio"))),
            ("Current Ratio",      fmt_ratio(f.get("current_ratio"))),
            ("Interest Coverage",  fmt_ratio(f.get("interest_coverage_ratio"))),
            ("Return on Equity",   fmt_pct(f.get("return_on_equity_percent"))),
        ]

        table = doc.add_table(rows=len(rows) + 1, cols=2)
        table.style = "Table Grid"

        # Header
        _set_cell_bg(table.cell(0, 0), self.VIVRITI_BLUE)
        _set_cell_bg(table.cell(0, 1), self.VIVRITI_BLUE)
        _bold_cell(table.cell(0, 0), "Metric",      color="FFFFFF")
        _bold_cell(table.cell(0, 1), "Value (FY Latest)", color="FFFFFF")

        for i, (label, value) in enumerate(rows, start=1):
            lc = table.cell(i, 0); vc = table.cell(i, 1)
            if i % 2 == 0: _set_cell_bg(lc, self.LIGHT_GREY); _set_cell_bg(vc, self.LIGHT_GREY)
            lc.text = label; vc.text = str(value)

        # Red flags
        red_flags = f.get("red_flags", {})
        if any(red_flags.values()):
            doc.add_paragraph()
            p = doc.add_paragraph()
            p.add_run("⚠ Red Flags Detected: ").bold = True
            flags_found = [k.replace("_", " ").title() for k, v in red_flags.items() if v]
            p.add_run(", ".join(flags_found))
            p.runs[-1].font.color.rgb = RGBColor.from_string(self.RED_ALERT)

        doc.add_paragraph()

    # ================================================================== #
    def _add_five_cs(self, doc, scoring: dict):
        self._section_heading(doc, "FIVE Cs OF CREDIT ASSESSMENT")

        five_cs    = scoring.get("five_cs",    {})
        risk_score = scoring.get("risk_score", {})

        cs_items = [
            ("Character",  "character",  "25%", "👤"),
            ("Capacity",   "capacity",   "30%", "💰"),
            ("Capital",    "capital",    "20%", "🏛️"),
            ("Collateral", "collateral", "15%", "🔒"),
            ("Conditions", "conditions", "10%", "🌍"),
        ]

        table = doc.add_table(rows=len(cs_items) + 1, cols=4)
        table.style = "Table Grid"

        # Header row
        for i, h in enumerate(["C", "Score", "Weight", "Rationale"]):
            hc = table.cell(0, i)
            _set_cell_bg(hc, self.VIVRITI_BLUE)
            _bold_cell(hc, h, color="FFFFFF")

        for row_idx, (name, key, weight, icon) in enumerate(cs_items, start=1):
            score     = five_cs.get(f"{key}_score",     "N/A")
            rationale = five_cs.get(f"{key}_rationale", "N/A")

            nc = table.cell(row_idx, 0); sc = table.cell(row_idx, 1)
            wc = table.cell(row_idx, 2); rc = table.cell(row_idx, 3)

            if row_idx % 2 == 0:
                for c in [nc, sc, wc, rc]:
                    _set_cell_bg(c, self.LIGHT_BLUE)

            nc.text = f"{icon} {name}"; nc.paragraphs[0].runs[0].bold = True
            sc.text = str(score)
            wc.text = weight
            rc.text = str(rationale)

        doc.add_paragraph()

        # Score breakdown
        p = doc.add_paragraph()
        p.add_run("Weighted Score: ").bold = True
        p.add_run(f"{risk_score.get('weighted_score', 'N/A')}/100")
        p.add_run("   |   ")
        p.add_run("Penalty Applied: ").bold = True
        p.add_run(f"{risk_score.get('penalty_applied', 0)} points")
        p.add_run("   |   ")
        p.add_run("Final Score: ").bold = True
        p.add_run(f"{risk_score.get('final_score', 'N/A')}/100")

        doc.add_paragraph()

    # ================================================================== #
    def _add_research_intelligence(self, doc, research: dict, scoring: dict = None):
        self._section_heading(doc, "SECONDARY RESEARCH INTELLIGENCE")

        sections = [
            ("Company News",      "company_news",       "summary"),
            ("Promoter Background","promoter_background","summary"),
            ("Sector Headwinds",  "sector_headwinds",   "summary"),
            ("Litigation",        "litigation",          "summary"),
            ("Regulatory",        "regulatory",          "summary"),
            ("MCA Signals",       "mca_signals",         "summary"),
        ]

        for label, key, summary_field in sections:
            section_data = research.get(key, {})
            if not section_data:
                continue

            p = doc.add_paragraph()
            p.add_run(f"{label}: ").bold = True
            p.add_run(str(section_data.get(summary_field, "No data available.")))
            doc.add_paragraph()

        # Overall sentiment — use computed research_rating from recommendation if available
        overall = research.get("overall_sentiment", {})
        rec_research = (scoring or {}).get("recommendation", {}).get("research_rating", {})
        if overall:
            p = doc.add_paragraph()
            p.add_run("Overall Research Rating: ").bold = True
            # Prefer the structured rubric grade (A/B/C/D) over Gemini's raw sentiment
            rr_grade = rec_research.get("grade") or overall.get("risk_rating", "N/A")
            rr_label = rec_research.get("label") or overall.get("preliminary_recommendation", "N/A")
            p.add_run(f"{rr_grade} — {rr_label}")

            top_risks = overall.get("top_risks", [])
            if top_risks:
                p2 = doc.add_paragraph()
                p2.add_run("Top Risks Identified: ").bold = True
                p2.add_run("; ".join(str(r) for r in top_risks))

        doc.add_paragraph()

    # ================================================================== #
    def _add_cross_reference(self, doc, cross_ref: dict):
        self._section_heading(doc, "CROSS-DOCUMENT FRAUD INTELLIGENCE")

        if not cross_ref.get("cross_reference_performed"):
            doc.add_paragraph(cross_ref.get("reason", "Cross-reference not performed."))
            doc.add_paragraph()
            return

        p = doc.add_paragraph()
        p.add_run("Documents Compared: ").bold = True
        p.add_run(", ".join(cross_ref.get("documents_compared", [])))

        p2 = doc.add_paragraph()
        p2.add_run("Circular Trading Risk: ").bold = True
        p2.add_run(cross_ref.get("circular_trading_risk", "N/A"))

        p3 = doc.add_paragraph()
        p3.add_run("Revenue Inflation Risk: ").bold = True
        p3.add_run(cross_ref.get("revenue_inflation_risk", "N/A"))

        flags = cross_ref.get("flags", [])
        if flags:
            doc.add_paragraph()
            p4 = doc.add_paragraph()
            p4.add_run("⚠ Flags Detected:").bold = True
            for flag in flags:
                fp = doc.add_paragraph(style="List Bullet")
                fp.add_run(f"[{flag.get('severity','?')}] {flag.get('type','?')}: ").bold = True
                fp.add_run(flag.get("description", ""))

        doc.add_paragraph()

    # ================================================================== #
    def _add_field_notes(self, doc, manual_notes: str):
        self._section_heading(doc, "CREDIT OFFICER FIELD OBSERVATIONS")
        p = doc.add_paragraph(manual_notes)
        p.runs[0].italic = True
        doc.add_paragraph()

    # ================================================================== #
    def _add_recommendation(self, doc, scoring: dict):
        self._section_heading(doc, "FINAL RECOMMENDATION")

        rec      = scoring.get("recommendation", {})
        decision = rec.get("decision", "N/A")

        # Decision box
        table = doc.add_table(rows=1, cols=1)
        cell  = table.cell(0, 0)
        color = self.GREEN_OK if decision == "APPROVE" else \
                self.ORANGE_WARN if decision == "CONDITIONAL_APPROVE" else self.RED_ALERT
        _set_cell_bg(cell, color)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"RECOMMENDATION: {decision}")
        r.bold = True; r.font.size = Pt(14); r.font.color.rgb = RGBColor(255,255,255)

        doc.add_paragraph()

        rows = [
            ("Decision",           str(decision)),
            ("Credit Rating",      str(rec.get("rating", "N/A"))),
            ("Credit Score",       f"{rec.get('final_score', 'N/A')}/100"),
            ("Recommended Amount", f"₹{rec.get('recommended_amount_crores','N/A')} Cr"),
            ("Interest Rate",      f"{rec.get('interest_rate_percent','N/A')}%"),
            ("Tenure",             f"{rec.get('tenure_months','N/A')} months"),
        ]

        table2 = doc.add_table(rows=len(rows), cols=2)
        table2.style = "Table Grid"
        for i, (label, value) in enumerate(rows):
            lc = table2.cell(i, 0); vc = table2.cell(i, 1)
            _set_cell_bg(lc, self.LIGHT_BLUE)
            lc.text = label; lc.paragraphs[0].runs[0].bold = True
            vc.text = value

        doc.add_paragraph()

        # Rationale
        rationale = rec.get("decision_rationale") or rec.get("rejection_reason") or ""
        if rationale:
            p2 = doc.add_paragraph()
            p2.add_run("Rationale: ").bold = True
            p2.add_run(str(rationale))

        conditions = rec.get("key_conditions", [])
        if conditions:
            doc.add_paragraph()
            doc.add_paragraph().add_run("Conditions Precedent:").bold = True
            for c in conditions:
                cp = doc.add_paragraph(style="List Bullet")
                cp.add_run(str(c))

        doc.add_paragraph()
        disc = doc.add_paragraph(
            "Disclaimer: This Credit Appraisal Memo has been prepared using AI-assisted analysis "
            "by Intelli-Credit (DOMINIX). All recommendations are subject to review and approval "
            "by authorized credit officers as per Vivriti Capital's credit policy."
        )
        disc.runs[0].italic = True
        disc.runs[0].font.size = Pt(8)

    # ================================================================== #
    def _add_footer(self, doc):
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(
            f"Intelli-Credit by DOMINIX  ·  Vivriti Capital Hackathon 2026  ·  "
            f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}"
        )
        r.font.size  = Pt(8)
        r.font.color.rgb = RGBColor.from_string(self.VIVRITI_BLUE)

    # ================================================================== #
    def _section_heading(self, doc, text: str):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(text)
        run.bold = True
        run.font.size  = Pt(12)
        run.font.color.rgb = RGBColor.from_string(self.VIVRITI_BLUE)
        # Underline via border — simpler: just underline
        run.underline = True
        doc.add_paragraph()