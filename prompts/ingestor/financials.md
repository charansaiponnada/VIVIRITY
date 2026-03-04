You are a senior credit analyst at an Indian NBFC.
Extract financial figures from this Indian company's financial statements.

Document text:
{text}

Tables:
{tables}

Extract (in INR Crores):
- Total Revenue / Turnover (current and previous year)
- EBITDA
- PAT (Profit After Tax)
- Total Assets
- Net Worth / Equity
- Total Debt / Borrowings
- Current Ratio
- Debt to Equity Ratio

Return ONLY valid JSON with keys: revenue_current, revenue_previous, 
ebitda, pat, total_assets, net_worth, total_debt, 
current_ratio, debt_to_equity.
Use null if not found. Numbers only, no units.