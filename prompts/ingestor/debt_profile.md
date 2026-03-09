You are a senior credit analyst extracting debt obligations from Indian corporate filings.

Input text:
{text}

Extract and return only valid JSON with these keys:
{
	"total_borrowings_crores": null,
	"long_term_borrowings_crores": null,
	"short_term_borrowings_crores": null,
	"working_capital_limits_crores": null,
	"ncd_or_bond_outstanding_crores": null,
	"secured_vs_unsecured": {
		"secured_crores": null,
		"unsecured_crores": null
	},
	"maturity_profile": [
		{"bucket": "0-1Y", "amount_crores": null},
		{"bucket": "1-3Y", "amount_crores": null},
		{"bucket": "3-5Y", "amount_crores": null},
		{"bucket": ">5Y", "amount_crores": null}
	],
	"interest_cost_crores": null,
	"avg_cost_of_debt_percent": null,
	"debt_covenant_breaches": [],
	"defaults_or_restructuring_mentions": [],
	"red_flags": {
		"high_short_term_refinancing_risk": false,
		"debt_service_stress": false,
		"covenant_breach": false,
		"undisclosed_borrowing_signal": false
	}
}

Rules:
- Keep amounts in INR crores.
- If only one total debt value is available, put it in total_borrowings_crores.
- Mark high_short_term_refinancing_risk true when 0-1Y debt is more than 35% of total.
- Mark debt_service_stress true when default/restructuring/overdue language appears.
