"""
core/databricks_layer.py
------------------------
Databricks-compatible data ingestion and lakehouse layer.

The hackathon problem statement says:
  "The solution must ingest multi-source data (Databricks)"

This module provides:
1. A DatabricksDataLayer class that simulates Databricks Delta Lake operations
2. Schema definitions matching Databricks Unity Catalog conventions
3. Data validation and quality checks (like Databricks Auto Loader)
4. A local file-based fallback when Databricks is not available

In production (real Databricks environment), replace the local storage
methods with actual Delta Lake / Spark DataFrame operations using:
  from pyspark.sql import SparkSession
  spark = SparkSession.builder.appName("IntelliCredit").getOrCreate()

For the hackathon demo, this runs locally using JSON files that mirror
the exact schema you would use in a Databricks Delta table.
"""

import os
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path


# ── Delta Lake schema definitions (Databricks Unity Catalog format) ─── #
# These mirror real Databricks table schemas for each document type

SCHEMAS = {
    "annual_report": {
        "table_name":   "intellicredit.bronze.annual_reports",
        "description":  "Raw annual report extractions — Bronze layer",
        "fields": {
            "record_id":                "STRING NOT NULL",
            "company_name":             "STRING",
            "cin":                      "STRING",
            "fiscal_year":              "STRING",
            "revenue_crores":           "DOUBLE",
            "profit_after_tax_crores":  "DOUBLE",
            "ebitda_crores":            "DOUBLE",
            "ebitda_margin_percent":    "DOUBLE",
            "total_assets_crores":      "DOUBLE",
            "net_worth_crores":         "DOUBLE",
            "total_borrowings_crores":  "DOUBLE",
            "debt_equity_ratio":        "DOUBLE",
            "current_ratio":            "DOUBLE",
            "interest_coverage_ratio":  "DOUBLE",
            "dscr_approximate":         "DOUBLE",
            "external_credit_rating":   "STRING",
            "audit_qualified":          "BOOLEAN",
            "going_concern_issue":      "BOOLEAN",
            "extraction_timestamp":     "TIMESTAMP",
            "source_file":              "STRING",
            "data_quality_score":       "DOUBLE",
        }
    },
    "gst_filing": {
        "table_name":   "intellicredit.bronze.gst_filings",
        "description":  "GST return data — Bronze layer",
        "fields": {
            "record_id":            "STRING NOT NULL",
            "company_name":         "STRING",
            "gstin":                "STRING",
            "filing_period":        "STRING",
            "gst_turnover_crores":  "DOUBLE",
            "gstr3b_liability":     "DOUBLE",
            "gstr2a_itc":           "DOUBLE",
            "filing_timestamp":     "TIMESTAMP",
        }
    },
    "bank_statement": {
        "table_name":   "intellicredit.bronze.bank_statements",
        "description":  "Bank transaction data — Bronze layer",
        "fields": {
            "record_id":            "STRING NOT NULL",
            "company_name":         "STRING",
            "account_number":       "STRING",
            "period":               "STRING",
            "total_credits_crores": "DOUBLE",
            "total_debits_crores":  "DOUBLE",
            "average_balance":      "DOUBLE",
            "bounce_count":         "INTEGER",
            "emi_obligations":      "DOUBLE",
            "filing_timestamp":     "TIMESTAMP",
        }
    },
    "ml_scoring": {
        "table_name":   "intellicredit.gold.ml_scores",
        "description":  "ML model scores — Gold layer (serving)",
        "fields": {
            "record_id":                    "STRING NOT NULL",
            "company_name":                 "STRING",
            "ml_probability_of_lending":    "DOUBLE",
            "ml_score":                     "DOUBLE",
            "ml_rating":                    "STRING",
            "ml_decision":                  "STRING",
            "five_cs_score":                "DOUBLE",
            "final_score":                  "DOUBLE",
            "final_rating":                 "STRING",
            "final_decision":               "STRING",
            "interest_rate_percent":        "DOUBLE",
            "recommended_amount_crores":    "DOUBLE",
            "scoring_timestamp":            "TIMESTAMP",
        }
    },
    "cibil_report": {
        "table_name":   "intellicredit.bronze.cibil_reports",
        "description":  "CIBIL/Credit Bureau data — Bronze layer",
        "fields": {
            "record_id":                "STRING NOT NULL",
            "company_name":             "STRING",
            "credit_score":             "INTEGER",
            "max_dpd":                  "INTEGER",
            "total_outstanding_crores": "DOUBLE",
            "suit_filed":               "BOOLEAN",
            "wilful_defaulter":         "BOOLEAN",
            "overdue_amount_crores":    "DOUBLE",
            "total_credit_facilities":  "INTEGER",
            "active_facilities":        "INTEGER",
            "filing_timestamp":         "TIMESTAMP",
        }
    }
}


class DatabricksDataLayer:
    """
    Databricks-compatible data layer for Intelli-Credit.

    Architecture mirrors a real Databricks Lakehouse:
    ┌─────────────┐    ┌────────────────┐    ┌──────────────┐
    │  BRONZE     │ →  │  SILVER        │ →  │  GOLD        │
    │  Raw ingest │    │  Validated     │    │  ML-ready    │
    │  PDFs/GST   │    │  + quality     │    │  features    │
    └─────────────┘    └────────────────┘    └──────────────┘

    In production, replace local JSON storage with:
      spark.write.format("delta").saveAsTable("intellicredit.bronze.annual_reports")
    """

    def __init__(self, storage_path: str = "databricks_lakehouse"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

        # Create layer directories
        for layer in ["bronze", "silver", "gold", "audit_log"]:
            (self.storage_path / layer).mkdir(exist_ok=True)

        self.session_id = hashlib.md5(
            str(datetime.now().timestamp()).encode()
        ).hexdigest()[:8]

    # ================================================================== #
    # BRONZE LAYER — Raw data ingestion (mirrors Databricks Auto Loader)
    # ================================================================== #

    def write_bronze(self, doc_type: str, company_name: str,
                     data: dict, source_file: str = "") -> str:
        """
        Write raw extracted data to Bronze layer.
        Mirrors: spark.readStream.format("cloudFiles").load(path)
        """
        record_id = self._generate_record_id(company_name, doc_type)

        schema = SCHEMAS.get(doc_type, {})
        record = {
            "record_id":            record_id,
            "company_name":         company_name,
            "source_file":          os.path.basename(source_file),
            "extraction_timestamp": datetime.now().isoformat(),
            "databricks_table":     schema.get("table_name", f"intellicredit.bronze.{doc_type}"),
            "layer":                "bronze",
            "data_quality_score":   self._compute_data_quality(data, doc_type),
            **data
        }

        filepath = self.storage_path / "bronze" / f"{doc_type}_{record_id}.json"
        with open(filepath, "w") as f:
            json.dump(record, f, indent=2, default=str)

        self._audit_log("WRITE_BRONZE", doc_type, record_id, company_name)
        print(f"  [Databricks Bronze] Written: {schema.get('table_name','bronze')} | record_id={record_id}")
        return record_id

    def read_bronze(self, doc_type: str, company_name: str = None) -> list[dict]:
        """
        Read from Bronze layer.
        Mirrors: spark.read.format("delta").table("intellicredit.bronze.annual_reports")
        """
        results = []
        bronze_path = self.storage_path / "bronze"
        for f in bronze_path.glob(f"{doc_type}_*.json"):
            with open(f) as fh:
                record = json.load(fh)
            if company_name is None or record.get("company_name") == company_name:
                results.append(record)
        return results

    # ================================================================== #
    # SILVER LAYER — Validated + quality-checked data
    # ================================================================== #

    def promote_to_silver(self, record_id: str, doc_type: str,
                          validated_data: dict) -> dict:
        """
        Promote Bronze record to Silver after validation.
        Mirrors: DLT (Delta Live Tables) pipeline with quality constraints.
        """
        bronze_records = self.read_bronze(doc_type)
        bronze = next((r for r in bronze_records if r["record_id"] == record_id), {})

        quality_checks = self._run_quality_checks(validated_data, doc_type)

        silver_record = {
            **bronze,
            **validated_data,
            "record_id":         record_id,
            "layer":             "silver",
            "silver_timestamp":  datetime.now().isoformat(),
            "quality_checks":    quality_checks,
            "quality_passed":    all(q["passed"] for q in quality_checks),
            "databricks_table":  f"intellicredit.silver.{doc_type}",
        }

        filepath = self.storage_path / "silver" / f"{doc_type}_{record_id}.json"
        with open(filepath, "w") as f:
            json.dump(silver_record, f, indent=2, default=str)

        self._audit_log("PROMOTE_SILVER", doc_type, record_id,
                        bronze.get("company_name",""),
                        f"quality_passed={silver_record['quality_passed']}")
        print(f"  [Databricks Silver] Promoted: intellicredit.silver.{doc_type} | quality_passed={silver_record['quality_passed']}")
        return silver_record

    # ================================================================== #
    # GOLD LAYER — ML features and final scores (serving layer)
    # ================================================================== #

    def write_gold_scores(self, company_name: str, scoring_results: dict,
                          ml_results: dict) -> str:
        """
        Write final ML scores to Gold layer (serving layer).
        This is what a downstream credit system would query.
        Mirrors: spark.write.format("delta").mode("overwrite").saveAsTable("intellicredit.gold.ml_scores")
        """
        record_id = self._generate_record_id(company_name, "ml_scoring")

        rec  = scoring_results.get("recommendation", {})
        rs   = scoring_results.get("risk_score",     {})

        gold_record = {
            "record_id":                    record_id,
            "company_name":                 company_name,
            "layer":                        "gold",
            "databricks_table":             "intellicredit.gold.ml_scores",
            "scoring_timestamp":            datetime.now().isoformat(),

            # ML model output
            "ml_probability_of_lending":    ml_results.get("ml_probability_of_lending"),
            "ml_score":                     ml_results.get("ml_score"),
            "ml_rating":                    ml_results.get("ml_rating"),
            "ml_decision":                  ml_results.get("ml_decision"),
            "ml_top_positive_drivers":      ml_results.get("top_positive_drivers", []),
            "ml_top_negative_drivers":      ml_results.get("top_negative_drivers", []),

            # Five Cs heuristic output
            "five_cs_weighted_score":       rs.get("weighted_score"),
            "five_cs_final_score":          rs.get("final_score"),
            "five_cs_rating":               rs.get("rating"),
            "penalty_applied":              rs.get("penalty_applied"),

            # Final blended decision
            "final_decision":               rec.get("decision"),
            "final_rating":                 rec.get("rating"),
            "interest_rate_percent":        rec.get("interest_rate_percent"),
            "recommended_amount_crores":    rec.get("recommended_amount_crores"),
            "tenure_months":                rec.get("tenure_months"),
            "decision_rationale":           rec.get("decision_rationale"),
        }

        filepath = self.storage_path / "gold" / f"ml_scores_{record_id}.json"
        with open(filepath, "w") as f:
            json.dump(gold_record, f, indent=2, default=str)

        self._audit_log("WRITE_GOLD", "ml_scoring", record_id, company_name)
        print(f"  [Databricks Gold] Written: intellicredit.gold.ml_scores | decision={rec.get('decision')}")
        return record_id

    def get_gold_scores(self, company_name: str) -> dict | None:
        """Query Gold layer for a company's latest score."""
        gold_path = self.storage_path / "gold"
        records = []
        for f in gold_path.glob("ml_scores_*.json"):
            with open(f) as fh:
                r = json.load(fh)
            if r.get("company_name") == company_name:
                records.append(r)
        if not records:
            return None
        return sorted(records, key=lambda x: x.get("scoring_timestamp",""))[-1]

    # ================================================================== #
    # DATA QUALITY ENGINE (mirrors Databricks DLT expectations)
    # ================================================================== #

    def _compute_data_quality(self, data: dict, doc_type: str) -> float:
        """Compute data completeness score 0–1."""
        if doc_type != "annual_report":
            return 1.0

        key_fields = [
            "revenue_crores", "profit_after_tax_crores", "ebitda_crores",
            "total_assets_crores", "net_worth_crores", "total_borrowings_crores",
            "debt_equity_ratio", "current_ratio", "interest_coverage_ratio",
        ]
        present = sum(1 for f in key_fields if data.get(f) is not None)
        return round(present / len(key_fields), 2)

    def _run_quality_checks(self, data: dict, doc_type: str) -> list[dict]:
        """
        Run DLT-style quality expectations.
        Mirrors: @dlt.expect("revenue_positive", "revenue_crores > 0")
        """
        checks = []

        if doc_type == "annual_report":
            rev = data.get("revenue_crores")
            checks.append({
                "name":    "revenue_positive",
                "rule":    "revenue_crores > 0",
                "passed":  rev is not None and float(rev or 0) > 0,
                "value":   rev,
            })

            pat = data.get("profit_after_tax_crores")
            checks.append({
                "name":    "pat_exists",
                "rule":    "profit_after_tax_crores IS NOT NULL",
                "passed":  pat is not None,
                "value":   pat,
            })

            de = data.get("debt_equity_ratio")
            checks.append({
                "name":    "de_ratio_reasonable",
                "rule":    "debt_equity_ratio BETWEEN 0 AND 20",
                "passed":  de is None or (0 <= float(de or 0) <= 20),
                "value":   de,
            })

            rf = data.get("red_flags", {})
            checks.append({
                "name":    "no_wilful_default",
                "rule":    "wilful_default NOT IN red_flags",
                "passed":  "wilful default" not in json.dumps(rf).lower(),
                "value":   rf,
            })

        return checks

    # ================================================================== #
    # CROSS-REFERENCE ENGINE (GST vs Bank vs Annual Report)
    # ================================================================== #

    def cross_reference_documents(self, company_name: str) -> dict:
        """
        Cross-reference all documents for a company in the lakehouse.
        This is the "circular trading detection" feature from the problem statement.

        Mirrors a Databricks JOIN query:
          SELECT ar.revenue, gst.gst_turnover, bank.total_credits
          FROM annual_reports ar
          JOIN gst_filings gst ON ar.company_name = gst.company_name
          JOIN bank_statements bank ON ar.company_name = bank.company_name
        """
        ar_records  = self.read_bronze("annual_report",  company_name)
        gst_records = self.read_bronze("gst_filing",     company_name)
        bs_records  = self.read_bronze("bank_statement", company_name)

        flags  = []
        result = {
            "company_name":              company_name,
            "cross_reference_performed": False,
            "documents_found":           [],
            "flags":                     [],
            "circular_trading_risk":     "Unknown",
            "revenue_inflation_risk":    "Unknown",
            "databricks_query":          "SELECT ar.revenue, gst.gst_turnover, bank.total_credits FROM intellicredit.bronze.* WHERE company_name = '{}'".format(company_name),
        }

        if ar_records:  result["documents_found"].append("annual_report")
        if gst_records: result["documents_found"].append("gst_filing")
        if bs_records:  result["documents_found"].append("bank_statement")

        if len(result["documents_found"]) < 2:
            result["reason"] = "Fewer than 2 document types available for cross-reference."
            return result

        result["cross_reference_performed"] = True

        # Revenue cross-check: AR vs GST
        if ar_records and gst_records:
            ar_rev  = float(ar_records[-1].get("revenue_crores") or 0)
            gst_rev = float(gst_records[-1].get("gst_turnover_crores") or 0)
            if ar_rev > 0 and gst_rev > 0:
                variance = abs(ar_rev - gst_rev) / ar_rev
                if variance > 0.25:
                    flags.append({
                        "type":        "REVENUE_MISMATCH",
                        "severity":    "HIGH",
                        "description": f"Annual report revenue ₹{ar_rev:.0f}Cr vs GST turnover ₹{gst_rev:.0f}Cr — {variance*100:.1f}% variance exceeds 25% threshold",
                        "databricks_rule": "ABS(ar.revenue - gst.gst_turnover) / ar.revenue > 0.25",
                    })
                elif variance > 0.15:
                    flags.append({
                        "type":        "REVENUE_MISMATCH",
                        "severity":    "MEDIUM",
                        "description": f"Revenue variance {variance*100:.1f}% between AR and GST — requires explanation",
                        "databricks_rule": "ABS(ar.revenue - gst.gst_turnover) / ar.revenue > 0.15",
                    })

        # Bank credits vs Revenue cross-check
        if ar_records and bs_records:
            ar_rev    = float(ar_records[-1].get("revenue_crores") or 0)
            bank_cred = float(bs_records[-1].get("total_credits_crores") or 0)
            if ar_rev > 0 and bank_cred > 0:
                ratio = bank_cred / ar_rev
                if ratio < 0.5:
                    flags.append({
                        "type":        "CASH_FLOW_CONCERN",
                        "severity":    "MEDIUM",
                        "description": f"Bank credits (₹{bank_cred:.0f}Cr) only {ratio*100:.0f}% of reported revenue — low cash conversion",
                        "databricks_rule": "bank.total_credits / ar.revenue < 0.5",
                    })
                if ratio > 1.5:
                    flags.append({
                        "type":        "CIRCULAR_TRADING_SUSPECT",
                        "severity":    "HIGH",
                        "description": f"Bank credits (₹{bank_cred:.0f}Cr) are {ratio:.1f}x reported revenue — possible round-tripping",
                        "databricks_rule": "bank.total_credits / ar.revenue > 1.5",
                    })

        result["flags"]                  = flags
        result["circular_trading_risk"]  = "High" if any(f["type"] == "CIRCULAR_TRADING_SUSPECT" for f in flags) else "Low"
        result["revenue_inflation_risk"] = "High" if any(f["type"] == "REVENUE_MISMATCH" and f["severity"] == "HIGH" for f in flags) else "Low"
        result["summary"]                = f"Cross-referenced {len(result['documents_found'])} document types. Found {len(flags)} flag(s)."

        self._audit_log("CROSS_REFERENCE", "multi", "N/A", company_name, result["summary"])
        return result

    # ================================================================== #
    # AUDIT LOG (Databricks audit trail)
    # ================================================================== #

    def _audit_log(self, operation: str, doc_type: str, record_id: str,
                   company: str, notes: str = "") -> None:
        log_entry = {
            "timestamp":   datetime.now().isoformat(),
            "session_id":  self.session_id,
            "operation":   operation,
            "doc_type":    doc_type,
            "record_id":   record_id,
            "company":     company,
            "notes":       notes,
        }
        log_path = self.storage_path / "audit_log" / f"audit_{self.session_id}.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def get_audit_trail(self) -> list[dict]:
        """Return full audit trail for this session."""
        log_path = self.storage_path / "audit_log" / f"audit_{self.session_id}.jsonl"
        if not log_path.exists():
            return []
        with open(log_path) as f:
            return [json.loads(line) for line in f if line.strip()]

    # ================================================================== #
    # UTILITIES
    # ================================================================== #

    def _generate_record_id(self, company_name: str, doc_type: str) -> str:
        ts  = str(int(time.time() * 1000))
        raw = f"{company_name}_{doc_type}_{ts}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def get_schema(self, doc_type: str) -> dict:
        """Return Databricks Unity Catalog schema for a document type."""
        return SCHEMAS.get(doc_type, {})

    def list_tables(self) -> list[str]:
        """List all Databricks tables in the lakehouse."""
        return [s["table_name"] for s in SCHEMAS.values()]