import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.ml_credit_model import MLCreditModel
from agents.scoring_agent import ScoringAgent


def load_case(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_ml_decision(case_data: dict) -> dict:
    model = MLCreditModel()
    ml = model.predict(
        financials=case_data.get("financials", {}),
        research=case_data.get("research", {}),
        manual_notes=case_data.get("manual_notes", ""),
    )
    return {
        "case_id": case_data.get("case_id"),
        "expected": case_data.get("expected_decision"),
        "predicted": ml.get("ml_decision"),
        "probability": ml.get("ml_probability_of_lending"),
        "ml_score": ml.get("ml_score"),
        "ml_rating": ml.get("ml_rating"),
    }


def run_scoring_decision(case_data: dict) -> dict:
    sa = ScoringAgent(
        company_name=case_data.get("company_name", "Unknown"),
        financials=case_data.get("financials", {}),
        research=case_data.get("research", {}),
        manual_notes=case_data.get("manual_notes", ""),
        loan_purpose=case_data.get("loan_purpose", ""),
        entity_type="corporate",
    )
    out = sa.run()
    rec = out.get("recommendation", {})
    return {
        "case_id": case_data.get("case_id"),
        "expected": case_data.get("expected_decision"),
        "predicted": rec.get("decision"),
        "score": rec.get("final_score"),
        "rating": rec.get("rating"),
        "amount": rec.get("recommended_amount_crores"),
        "rate": rec.get("interest_rate_percent"),
    }


def main():
    base = Path(__file__).resolve().parent / "scenarios"
    case_files = [
        base / "approve_case.json",
        base / "conditional_case.json",
        base / "reject_case.json",
    ]

    print("Demo scenario decision check (ML path):")
    print("-" * 72)
    for case_file in case_files:
        case_data = load_case(case_file)
        out = run_ml_decision(case_data)
        marker = "PASS" if out["expected"] == out["predicted"] else "CHECK"
        print(
            f"{marker} | {out['case_id']} | expected={out['expected']} | "
            f"predicted={out['predicted']} | score={out['ml_score']} | p={out['probability']} | rating={out['ml_rating']}"
        )

    print("\nDemo scenario decision check (ScoringAgent path):")
    print("-" * 72)
    for case_file in case_files:
        case_data = load_case(case_file)
        out = run_scoring_decision(case_data)
        marker = "PASS" if out["expected"] == out["predicted"] else "CHECK"
        print(
            f"{marker} | {out['case_id']} | expected={out['expected']} | "
            f"predicted={out['predicted']} | score={out['score']} | rating={out['rating']} | "
            f"amount={out['amount']} | rate={out['rate']}"
        )


if __name__ == "__main__":
    main()
