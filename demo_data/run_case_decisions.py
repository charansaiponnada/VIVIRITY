import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.ml_credit_model import MLCreditModel


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


if __name__ == "__main__":
    main()
