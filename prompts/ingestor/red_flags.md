You are a senior credit analyst performing risk assessment for an Indian NBFC.
Identify red flags and risk signals in this Indian company document.

{text}

Look for:
- Legal disputes or litigation
- Audit qualifications or emphasis of matter
- Going concern issues
- Related party transaction anomalies
- Frequent auditor changes (auditor shopping)
- Pending tax demands (Income Tax, GST)
- Regulatory penalties (SEBI, RBI, MCA)
- Contingent liabilities that could materialize

Return ONLY valid JSON with keys: red_flags (list of strings),
litigation_count, audit_qualified (bool), 
going_concern_issue (bool), severity (low/medium/high).