class CrossReferenceAgent:
    """
    The most important agent for winning.
    Cross-references data across multiple document types
    to find inconsistencies — circular trading, revenue
    inflation, fake ITC claims.
    
    This is what a real credit manager does manually
    that takes weeks. We do it in seconds.
    """
    
    def __init__(self, documents_by_type: dict, client, model: str):
        self.documents = documents_by_type
        self.client = client
        self.model = model
    
    def run(self) -> dict:
        findings = {}
        
        # GST vs Bank Statement reconciliation
        if "gst_filing" in self.documents and \
           "bank_statement" in self.documents:
            findings["gst_bank_reconciliation"] = \
                self.reconcile_gst_vs_bank()
        
        # Annual Report vs GST revenue check
        if "annual_report" in self.documents and \
           "gst_filing" in self.documents:
            findings["revenue_verification"] = \
                self.verify_reported_revenue()
        
        # Sanction letter vs current debt check
        if "sanction_letter" in self.documents and \
           "annual_report" in self.documents:
            findings["debt_verification"] = \
                self.verify_debt_disclosure()
        
        findings["overall_integrity_score"] = \
            self.calculate_integrity_score(findings)
        
        return findings
    
    def reconcile_gst_vs_bank(self) -> dict:
        gst_text = self.documents["gst_filing"][:2000]
        bank_text = self.documents["bank_statement"][:2000]
        
        prompt = f"""
        You are a forensic credit analyst at an Indian NBFC.
        
        GST Filing Data:
        {gst_text}
        
        Bank Statement Data:
        {bank_text}
        
        Perform reconciliation:
        1. Extract total revenue/turnover from GST (GSTR-1 outward supplies)
        2. Extract total bank credits for the same period
        3. Calculate variance: Bank Credits vs GST Revenue
        4. Flag if variance > 10% as potential revenue inflation
        5. Check for circular transactions (same party appearing as both
           buyer and seller)
        6. Identify peak transaction dates that look unusual
        
        Indian context: GSTR-1 shows what company CLAIMS to sell.
        Bank statement shows what actually got CREDITED.
        Mismatch = revenue inflation red flag.
        
        Return ONLY valid JSON:
        {{
            "gst_reported_revenue": null,
            "bank_credited_revenue": null,
            "variance_percent": null,
            "variance_amount": null,
            "inflation_detected": false,
            "circular_transactions": [],
            "unusual_patterns": [],
            "integrity_flag": "CLEAN/SUSPECT/HIGH_RISK",
            "summary": ""
        }}
        """
        
        response = self.client.models.generate_content(
            model=self.model, contents=prompt
        )
        return self._parse_json(response.text)
    
    def verify_reported_revenue(self) -> dict:
        ar_text = self.documents["annual_report"][:2000]
        gst_text = self.documents["gst_filing"][:2000]
        
        prompt = f"""
        You are a forensic credit analyst.
        
        Annual Report Revenue Data:
        {ar_text}
        
        GST Filing Data:
        {gst_text}
        
        Cross-verify:
        1. Revenue reported in Annual Report vs GST outward supplies
        2. Any significant unexplained difference
        3. Exports claimed vs actual (GST zero-rated supplies)
        4. Inter-company transactions that inflate revenue
        
        Return ONLY valid JSON:
        {{
            "ar_reported_revenue": null,
            "gst_revenue": null,
            "difference_crores": null,
            "difference_percent": null,
            "explanation": "",
            "red_flag": false,
            "severity": "LOW/MEDIUM/HIGH"
        }}
        """
        
        response = self.client.models.generate_content(
            model=self.model, contents=prompt
        )
        return self._parse_json(response.text)
    
    def calculate_integrity_score(self, findings: dict) -> dict:
        """Overall data integrity score 0-100"""
        score = 100
        flags = []
        
        recon = findings.get("gst_bank_reconciliation", {})
        if recon.get("inflation_detected"):
            score -= 30
            flags.append("Revenue inflation detected in GST-Bank reconciliation")
        if recon.get("integrity_flag") == "HIGH_RISK":
            score -= 20
            flags.append("High risk integrity flag from bank reconciliation")
        
        rev = findings.get("revenue_verification", {})
        if rev.get("red_flag"):
            severity = rev.get("severity", "LOW")
            deduction = {"LOW": 5, "MEDIUM": 15, "HIGH": 25}.get(severity, 5)
            score -= deduction
            flags.append(f"Revenue verification mismatch — {severity} severity")
        
        return {
            "score": max(0, score),
            "flags": flags,
            "verdict": (
                "CLEAN" if score >= 80 else
                "SUSPECT" if score >= 60 else
                "HIGH_RISK"
            )
        }
    
    def _parse_json(self, text: str) -> dict:
        import json, re
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            return json.loads(text.strip())
        except Exception:
            return {"parse_error": True, "raw": text[:200]}