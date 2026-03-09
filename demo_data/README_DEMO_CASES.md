# Demo Cases For Hackathon Validation

This folder contains data to test the three key decision outcomes:
- `APPROVE`
- `CONDITIONAL_APPROVE`
- `REJECT`

## Scenario Files
- `scenarios/approve_case.json`
- `scenarios/conditional_case.json`
- `scenarios/reject_case.json`

Each scenario includes:
- Inputs: company, sector, promoters, loan request, manual notes.
- Financial snapshot (annual-report-like extracted values).
- Structured supporting sources: GST, ITR, bank summary.
- Research intelligence snapshot.
- Expected decision label.

## Realtime Synthetic Data
Run:

```bash
python demo_data/generate_realtime_stream.py
```

This creates:
- `demo_data/realtime_stream_cases.jsonl` (24-hour rolling signals)
- `demo_data/realtime_bank_transactions.csv` (hourly transaction stream)

Use these files to demo live dashboards, trend monitoring, and changing risk signals.

## Decision Validation
Run:

```bash
python demo_data/run_case_decisions.py
```

This checks all three scenarios with the ML recommendation path and prints whether
expected vs predicted decision bands match.

## Quick Demo Narrative
1. Start with `approve_case.json` to show healthy profile and clean cross-reference.
2. Move to `conditional_case.json` to show moderate risk and conditional lending.
3. Finish with `reject_case.json` to show high litigation/fraud/regulatory penalties and rejection rationale.
