import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUT_FILE = BASE_DIR / "realtime_stream_cases.jsonl"
BANK_OUT_FILE = BASE_DIR / "realtime_bank_transactions.csv"

random.seed(42)

SCENARIOS = [
    ("APPROVE_001", "approve", 0.82),
    ("COND_APPROVE_001", "conditional", 0.58),
    ("REJECT_001", "reject", 0.21),
]


def make_stream_rows(hours=24):
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    rows = []
    for h in range(hours):
        ts = now - timedelta(hours=(hours - 1 - h))
        for case_id, label, base_prob in SCENARIOS:
            noise = random.uniform(-0.08, 0.08)
            prob = max(0.01, min(0.99, base_prob + noise))
            rows.append({
                "timestamp": ts.isoformat(),
                "case_id": case_id,
                "scenario": label,
                "ml_probability_of_lending": round(prob, 4),
                "expected_band": "APPROVE" if prob >= 0.75 else ("CONDITIONAL_APPROVE" if prob >= 0.5 else "REJECT"),
                "sector_news_risk": random.choice(["low", "medium", "high"]),
                "litigation_signal": random.choice([0, 0, 1]) if label != "approve" else 0,
                "cross_ref_alerts": random.randint(0, 4 if label == "reject" else 2),
            })
    return rows


def write_jsonl(rows):
    with OUT_FILE.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def write_bank_csv(hours=24):
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    fields = ["date", "narration", "credit", "debit", "balance", "account_number", "bank_name", "case_id"]
    with BANK_OUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        balance = 25000000
        for h in range(hours):
            ts = (now - timedelta(hours=(hours - 1 - h))).strftime("%Y-%m-%d %H:%M")
            for case_id, label, _ in SCENARIOS:
                if label == "approve":
                    credit = random.randint(2000000, 7000000)
                    debit = random.randint(1200000, 4500000)
                elif label == "conditional":
                    credit = random.randint(1000000, 5000000)
                    debit = random.randint(1000000, 5200000)
                else:
                    credit = random.randint(300000, 2500000)
                    debit = random.randint(600000, 3200000)
                balance += credit - debit
                writer.writerow({
                    "date": ts,
                    "narration": f"Realtime tx {label}",
                    "credit": credit,
                    "debit": debit,
                    "balance": max(0, balance),
                    "account_number": "9988776655",
                    "bank_name": "HDFC Bank",
                    "case_id": case_id,
                })


if __name__ == "__main__":
    rows = make_stream_rows(hours=24)
    write_jsonl(rows)
    write_bank_csv(hours=24)
    print(f"Generated {len(rows)} stream rows: {OUT_FILE}")
    print(f"Generated realtime bank CSV: {BANK_OUT_FILE}")
