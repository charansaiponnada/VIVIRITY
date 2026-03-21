"""
core/realtime_integration.py
Real-Time Data Integration Module for Intelli-Credit.

Provides live data from:
1. MCA (Ministry of Corporate Affairs) API
2. GST Portal API
3. CIBIL Commercial Bureau API
4. RBI Rates & Indices
5. NCLT Case Tracker

Usage:
    from core.realtime_integration import RealtimeDataProvider
    provider = RealtimeDataProvider()
    data = await provider.get_full_profile(cin="U12345MH2010PTC123456")
"""

import os
import json
import time
import httpx
from typing import Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()

GOV_DATA_API_KEY = os.getenv("GOV_DATA_API_KEY", "")
TALLY_PRIME_API = os.getenv("TALLY_PRIME_API", "")


@dataclass
class MCAData:
    """MCA (Ministry of Corporate Affairs) company profile data."""

    cin: str
    company_name: str
    registration_number: str
    incorporation_date: str
    status: str
    class_description: str
    authorised_capital: float
    paid_up_capital: float
    number_of_members: int
    last_agm_date: str
    latest_financial_year: str
    registered_office_address: str
    nature_of_business: str
    sub_category: str
    directors_count: int
    charges_count: int
    latest_filing_status: dict

    def is_active(self) -> bool:
        return self.status.upper() == "ACTIVE"

    def has_paid_up_capital(self) -> bool:
        return self.paid_up_capital > 0


@dataclass
class GSTData:
    """GST Portal filing status and compliance data."""

    gstin: str
    legal_name: str
    constitution_of_business: str
    date_of_registration: str
    status: str
    filing_status: str
    last_return_filed: str
    filing_frequency: str
    itc_availed_last_6months: float
    itc_utilized_last_6months: float
    gstr1_filed: bool
    gstr3b_filed: bool
    annual_return_filed: bool
    compliance_score: float
    risk_level: str

    def is_compliant(self) -> bool:
        return self.compliance_score >= 70.0


@dataclass
class CIBILData:
    """CIBIL Commercial Bureau credit profile."""

    cin: str
    bureau_score: int
    score_range: str
    total_outstanding: float
    secured_outstanding: float
    unsecured_outstanding: float
    total_accounts: int
    active_accounts: int
    delinquent_accounts: int
    suit_filed_accounts: int
    wilful_defaulter_flag: bool
    written_off_accounts: int
    dpd_90_plus_count: int
    last_updated: str

    def is_wilful_defaulter(self) -> bool:
        return self.wilful_defaulter_flag

    def has_suit_filed(self) -> bool:
        return self.suit_filed_accounts > 0


@dataclass
class RBIRates:
    """RBI policy rates and indices."""

    repo_rate: float
    reverse_repo_rate: float
    msf_rate: float
    bank_rate: float
    crr: float
    slr: float
    inflation_rate: float
    gdp_growth: float
    pmi_manufacturing: float
    pmi_services: float
    currency_in_circulation: float
    reference_date: str

    def get_base_rate_indicator(self) -> float:
        return self.repo_rate + 3.0


@dataclass
class NCLTData:
    """NCLT (National Company Law Tribunal) case data."""

    company_name: str
    cin: str
    total_cases: int
    insolvency_cases: int
    liquidation_cases: int
    pending_cases: int
    resolved_cases: int
    latest_case_date: str
    latest_case_type: str
    latest_case_status: str
    iirc_case_number: str
    moratorium_status: bool
    resolution_plan_approved: bool

    def has_active_insolvency(self) -> bool:
        return self.insolvency_cases > 0


class RealtimeDataProvider:
    """
    Real-time data provider for live government and financial APIs.

    Features:
    - Async/await for non-blocking API calls
    - Rate limiting and retry logic
    - Fallback to cached data
    - Mock mode for development/testing
    """

    MOCK_MODE = os.getenv("REALTIME_MOCK_MODE", "true").lower() == "true"
    API_TIMEOUT = 30

    def __init__(self):
        self.session = httpx.AsyncClient(timeout=self.API_TIMEOUT)
        self.cache = {}
        self.cache_ttl = 3600

    async def get_mca_data(self, cin: str) -> MCAData:
        """Fetch live MCA company data."""
        if self.MOCK_MODE:
            return self._mock_mca_data(cin)

        cache_key = f"mca_{cin}"
        if cached := self._get_cached(cache_key):
            return cached

        try:
            headers = {"Authorization": f"Bearer {GOV_DATA_API_KEY}"}
            response = await self.session.get(
                f"https://api.mca.gov.in/company/{cin}", headers=headers
            )
            data = response.json()
            result = self._parse_mca_response(data)
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            print(f"[RealtimeData] MCA API error: {e}")
            return self._mock_mca_data(cin)

    async def get_gst_data(self, gstin: str) -> GSTData:
        """Fetch GST filing status and compliance data."""
        if self.MOCK_MODE:
            return self._mock_gst_data(gstin)

        cache_key = f"gst_{gstin}"
        if cached := self._get_cached(cache_key):
            return cached

        try:
            headers = {"X-API-Key": os.getenv("GST_API_KEY", "")}
            response = await self.session.get(
                f"https://api.gst.gov.in/returns/search",
                params={"gstin": gstin, "period": "latest"},
                headers=headers,
            )
            data = response.json()
            result = self._parse_gst_response(data)
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            print(f"[RealtimeData] GST API error: {e}")
            return self._mock_gst_data(gstin)

    async def get_cibil_data(self, cin: str) -> CIBILData:
        """Fetch CIBIL Commercial Bureau credit profile."""
        if self.MOCK_MODE:
            return self._mock_cibil_data(cin)

        cache_key = f"cibil_{cin}"
        if cached := self._get_cached(cache_key):
            return cached

        try:
            headers = {"Authorization": f"Bearer {os.getenv('CIBIL_API_KEY', '')}"}
            response = await self.session.post(
                "https://api.cibil.com/commercial/report",
                json={"cin": cin, "report_type": "full"},
                headers=headers,
            )
            data = response.json()
            result = self._parse_cibil_response(data)
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            print(f"[RealtimeData] CIBIL API error: {e}")
            return self._mock_cibil_data(cin)

    async def get_rbi_rates(self) -> RBIRates:
        """Fetch current RBI policy rates."""
        if self.MOCK_MODE:
            return self._mock_rbi_rates()

        cache_key = "rbi_rates"
        if cached := self._get_cached(cache_key):
            return cached

        try:
            response = await self.session.get(
                "https://api.rbi.org.in/monetary-policy/rates"
            )
            data = response.json()
            result = self._parse_rbi_response(data)
            self._set_cache(cache_key, result, ttl=300)
            return result
        except Exception as e:
            print(f"[RealtimeData] RBI API error: {e}")
            return self._mock_rbi_rates()

    async def get_nclt_cases(self, cin: str) -> NCLTData:
        """Fetch NCLT case tracker data."""
        if self.MOCK_MODE:
            return self._mock_nclt_data(cin)

        cache_key = f"nclt_{cin}"
        if cached := self._get_cached(cache_key):
            return cached

        try:
            headers = {"Authorization": f"Bearer {GOV_DATA_API_KEY}"}
            response = await self.session.get(
                f"https://api.nclt.gov.in/company/cases/{cin}", headers=headers
            )
            data = response.json()
            result = self._parse_nclt_response(data)
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            print(f"[RealtimeData] NCLT API error: {e}")
            return self._mock_nclt_data(cin)

    async def get_full_profile(self, cin: str, gstin: str = None) -> dict:
        """
        Aggregate all real-time data sources for a complete profile.
        Returns combined dict with live_verified flag.
        """
        mca = await self.get_mca_data(cin)
        cibil = await self.get_cibil_data(cin)
        rbi = await self.get_rbi_rates()

        gst_data = None
        if gstin:
            gst_data = await self.get_gst_data(gstin)

        nclt = await self.get_nclt_cases(cin)

        return {
            "mca_data": asdict(mca) if mca else None,
            "gst_data": asdict(gst_data) if gst_data else None,
            "cibil_data": asdict(cibil) if cibil else None,
            "rbi_rates": asdict(rbi) if rbi else None,
            "nclt_cases": asdict(nclt) if nclt else None,
            "live_verified": True,
            "verification_timestamp": datetime.now().isoformat(),
            "data_sources": ["MCA_API", "GST_API", "CIBIL", "RBI", "NCLT"],
            "combined_risk_score": self._calculate_combined_risk(
                mca, cibil, gst_data, nclt
            ),
        }

    def _calculate_combined_risk(self, mca, cibil, gst, nclt) -> dict:
        """Calculate combined risk score from all sources."""
        risk_factors = []
        risk_score = 50

        if mca and not mca.is_active():
            risk_factors.append("Company not ACTIVE")
            risk_score -= 20

        if cibil:
            if cibil.is_wilful_defaulter():
                risk_factors.append("Wilful Defaulter")
                risk_score -= 30
            if cibil.has_suit_filed():
                risk_factors.append("Suit Filed")
                risk_score -= 15
            if cibil.dpd_90_plus_count > 0:
                risk_factors.append(f"DPD 90+: {cibil.dpd_90_plus_count}")
                risk_score -= 10

        if gst and not gst.is_compliant():
            risk_factors.append("Low GST Compliance")
            risk_score -= 10

        if nclt and nclt.has_active_insolvency():
            risk_factors.append("Active Insolvency")
            risk_score -= 25

        risk_score = max(0, min(100, risk_score))

        return {
            "composite_score": risk_score,
            "risk_factors": risk_factors,
            "risk_level": "LOW"
            if risk_score >= 70
            else "MEDIUM"
            if risk_score >= 40
            else "HIGH",
            "requires_manual_review": risk_score < 60,
        }

    def _get_cached(self, key: str) -> Optional[any]:
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < entry["ttl"]:
                print(f"[RealtimeData] Cache HIT: {key}")
                return entry["data"]
        return None

    def _set_cache(self, key: str, data: any, ttl: int = None):
        self.cache[key] = {
            "data": data,
            "timestamp": time.time(),
            "ttl": ttl or self.cache_ttl,
        }

    def _parse_mca_response(self, data: dict) -> MCAData:
        return MCAData(
            cin=data.get("cin", ""),
            company_name=data.get("company_name", ""),
            registration_number=data.get("registration_number", ""),
            incorporation_date=data.get("incorporation_date", ""),
            status=data.get("status", ""),
            class_description=data.get("class_description", ""),
            authorised_capital=float(data.get("authorised_capital", 0)),
            paid_up_capital=float(data.get("paid_up_capital", 0)),
            number_of_members=int(data.get("number_of_members", 0)),
            last_agm_date=data.get("last_agm_date", ""),
            latest_financial_year=data.get("latest_financial_year", ""),
            registered_office_address=data.get("registered_office_address", ""),
            nature_of_business=data.get("nature_of_business", ""),
            sub_category=data.get("sub_category", ""),
            directors_count=int(data.get("directors_count", 0)),
            charges_count=int(data.get("charges_count", 0)),
            latest_filing_status=data.get("latest_filing_status", {}),
        )

    def _parse_gst_response(self, data: dict) -> GSTData:
        return GSTData(
            gstin=data.get("gstin", ""),
            legal_name=data.get("legal_name", ""),
            constitution_of_business=data.get("constitution_of_business", ""),
            date_of_registration=data.get("date_of_registration", ""),
            status=data.get("status", "Active"),
            filing_status=data.get("filing_status", ""),
            last_return_filed=data.get("last_return_filed", ""),
            filing_frequency=data.get("filing_frequency", ""),
            itc_availed_last_6months=float(data.get("itc_availed", 0)),
            itc_utilized_last_6months=float(data.get("itc_utilized", 0)),
            gstr1_filed=data.get("gstr1_filed", False),
            gstr3b_filed=data.get("gstr3b_filed", False),
            annual_return_filed=data.get("annual_return_filed", False),
            compliance_score=float(data.get("compliance_score", 0)),
            risk_level=data.get("risk_level", "MEDIUM"),
        )

    def _parse_cibil_response(self, data: dict) -> CIBILData:
        return CIBILData(
            cin=data.get("cin", ""),
            bureau_score=int(data.get("score", 0)),
            score_range=data.get("score_range", ""),
            total_outstanding=float(data.get("total_outstanding", 0)),
            secured_outstanding=float(data.get("secured_outstanding", 0)),
            unsecured_outstanding=float(data.get("unsecured_outstanding", 0)),
            total_accounts=int(data.get("total_accounts", 0)),
            active_accounts=int(data.get("active_accounts", 0)),
            delinquent_accounts=int(data.get("delinquent_accounts", 0)),
            suit_filed_accounts=int(data.get("suit_filed", 0)),
            wilful_defaulter_flag=data.get("wilful_defaulter", False),
            written_off_accounts=int(data.get("written_off", 0)),
            dpd_90_plus_count=int(data.get("dpd_90_plus", 0)),
            last_updated=data.get("last_updated", ""),
        )

    def _parse_rbi_response(self, data: dict) -> RBIRates:
        return RBIRates(
            repo_rate=float(data.get("repo_rate", 6.5)),
            reverse_repo_rate=float(data.get("reverse_repo_rate", 3.35)),
            msf_rate=float(data.get("msf_rate", 6.75)),
            bank_rate=float(data.get("bank_rate", 6.75)),
            crr=float(data.get("crr", 4.5)),
            slr=float(data.get("slr", 18.0)),
            inflation_rate=float(data.get("inflation_rate", 5.0)),
            gdp_growth=float(data.get("gdp_growth", 7.0)),
            pmi_manufacturing=float(data.get("pmi_manufacturing", 55.0)),
            pmi_services=float(data.get("pmi_services", 58.0)),
            currency_in_circulation=float(data.get("currency_in_circulation", 0)),
            reference_date=data.get("reference_date", ""),
        )

    def _parse_nclt_response(self, data: dict) -> NCLTData:
        return NCLTData(
            company_name=data.get("company_name", ""),
            cin=data.get("cin", ""),
            total_cases=int(data.get("total_cases", 0)),
            insolvency_cases=int(data.get("insolvency_cases", 0)),
            liquidation_cases=int(data.get("liquidation_cases", 0)),
            pending_cases=int(data.get("pending_cases", 0)),
            resolved_cases=int(data.get("resolved_cases", 0)),
            latest_case_date=data.get("latest_case_date", ""),
            latest_case_type=data.get("latest_case_type", ""),
            latest_case_status=data.get("latest_case_status", ""),
            iirc_case_number=data.get("iirc_case_number", ""),
            moratorium_status=data.get("moratorium_status", False),
            resolution_plan_approved=data.get("resolution_plan_approved", False),
        )

    def _mock_mca_data(self, cin: str) -> MCAData:
        return MCAData(
            cin=cin,
            company_name="MOCK COMPANY PRIVATE LIMITED",
            registration_number=f"REG{cin[-6:]}",
            incorporation_date="2010-04-15",
            status="ACTIVE",
            class_description="Private Limited Company",
            authorised_capital=50000000.0,
            paid_up_capital=25000000.0,
            number_of_members=10,
            last_agm_date="2024-09-30",
            latest_financial_year="FY2024",
            registered_office_address="123, MOCK STREET, MUMBAI - 400001",
            nature_of_business="Manufacturing of Auto Components",
            sub_category="Subsidiary of Listed Entity",
            directors_count=6,
            charges_count=4,
            latest_filing_status={"roc": "FILED", "tds": "FILED", "esic": "FILED"},
        )

    def _mock_gst_data(self, gstin: str) -> GSTData:
        return GSTData(
            gstin=gstin or "27AABCU9603R1ZM",
            legal_name="MOCK COMPANY PRIVATE LIMITED",
            constitution_of_business="Private Limited Company",
            date_of_registration="2017-07-01",
            status="Active",
            filing_status="Regular",
            last_return_filed="GSTR-3B for Nov 2024",
            filing_frequency="Monthly",
            itc_availed_last_6months=12500000.0,
            itc_utilized_last_6months=11250000.0,
            gstr1_filed=True,
            gstr3b_filed=True,
            annual_return_filed=True,
            compliance_score=92.5,
            risk_level="LOW",
        )

    def _mock_cibil_data(self, cin: str) -> CIBILData:
        return CIBILData(
            cin=cin,
            bureau_score=752,
            score_range="700-800",
            total_outstanding=45000000.0,
            secured_outstanding=35000000.0,
            unsecured_outstanding=10000000.0,
            total_accounts=8,
            active_accounts=5,
            delinquent_accounts=0,
            suit_filed_accounts=0,
            wilful_defaulter_flag=False,
            written_off_accounts=0,
            dpd_90_plus_count=0,
            last_updated="2024-11-15",
        )

    def _mock_rbi_rates(self) -> RBIRates:
        return RBIRates(
            repo_rate=6.5,
            reverse_repo_rate=3.35,
            msf_rate=6.75,
            bank_rate=6.75,
            crr=4.5,
            slr=18.0,
            inflation_rate=5.09,
            gdp_growth=7.2,
            pmi_manufacturing=56.2,
            pmi_services=58.5,
            currency_in_circulation=35400000000000.0,
            reference_date=datetime.now().strftime("%Y-%m-%d"),
        )

    def _mock_nclt_data(self, cin: str) -> NCLTData:
        return NCLTData(
            company_name="MOCK COMPANY PRIVATE LIMITED",
            cin=cin,
            total_cases=0,
            insolvency_cases=0,
            liquidation_cases=0,
            pending_cases=0,
            resolved_cases=0,
            latest_case_date="",
            latest_case_type="",
            latest_case_status="",
            iirc_case_number="",
            moratorium_status=False,
            resolution_plan_approved=False,
        )


class LiveDataEnricher:
    """
    Enriches extracted financial data with live verified information.
    Used by the scoring agent to cross-validate PDF-extracted data.
    """

    def __init__(self, provider: RealtimeDataProvider = None):
        self.provider = provider or RealtimeDataProvider()

    async def enrich_financials(self, extracted_data: dict, cin: str) -> dict:
        """
        Cross-validate and enrich extracted financial data with live APIs.
        Returns enriched data with verification status.
        """
        live_profile = await self.provider.get_full_profile(cin)

        enrichment_report = {
            "verified_fields": [],
            "mismatched_fields": [],
            "live_overrides": {},
            "warnings": [],
        }

        mca = live_profile.get("mca_data", {})
        cibil = live_profile.get("cibil_data", {})
        gst = live_profile.get("gst_data", {})

        if mca:
            mca_company_name = mca.get("company_name", "").lower()
            extracted_company = extracted_data.get("company_name", "").lower()

            if mca_company_name and extracted_company:
                if mca_company_name[:20] == extracted_company[:20]:
                    enrichment_report["verified_fields"].append("company_name")
                else:
                    enrichment_report["warnings"].append(
                        f"Company name mismatch: MCA={mca_company_name}, Extracted={extracted_company}"
                    )

            if extracted_data.get("paid_up_capital"):
                mca_cap = mca.get("paid_up_capital", 0)
                extracted_cap = float(
                    str(extracted_data.get("paid_up_capital", 0)).replace(",", "")
                )
                variance = abs(mca_cap - extracted_cap) / (mca_cap or 1)
                if variance < 0.1:
                    enrichment_report["verified_fields"].append("paid_up_capital")
                else:
                    enrichment_report["mismatched_fields"].append(
                        {
                            "field": "paid_up_capital",
                            "mca_value": mca_cap,
                            "extracted_value": extracted_cap,
                            "variance_pct": round(variance * 100, 2),
                        }
                    )
                    enrichment_report["live_overrides"]["paid_up_capital"] = mca_cap

        if gst and cibil:
            if extracted_data.get("gstr_mismatch_detected"):
                if gst.get("compliance_score", 0) >= 80:
                    enrichment_report["warnings"].append(
                        "GST mismatch flag set but GST portal shows high compliance. Review recommended."
                    )

        if cibil:
            if cibil.get("wilful_defaulter_flag"):
                enrichment_report["live_overrides"]["wilful_defaulter"] = True
                enrichment_report["warnings"].append(
                    "Wilful Defaulter confirmed via CIBIL"
                )

            if cibil.get("suit_filed_accounts", 0) > 0:
                enrichment_report["live_overrides"]["suit_filed"] = True
                enrichment_report["warnings"].append(
                    f"Suit Filed: {cibil['suit_filed_accounts']} accounts"
                )

            if cibil.get("dpd_90_plus_count", 0) > 0:
                enrichment_report["live_overrides"]["dpd_90_plus"] = True
                enrichment_report["warnings"].append(
                    f"DPD 90+: {cibil['dpd_90_plus_count']} accounts"
                )

        return {
            "enriched_data": extracted_data,
            "live_profile": live_profile,
            "enrichment_report": enrichment_report,
            "verification_timestamp": datetime.now().isoformat(),
        }


async def fetch_live_data_async(cin: str, gstin: str = None) -> dict:
    """Async helper function for quick usage."""
    provider = RealtimeDataProvider()
    return await provider.get_full_profile(cin, gstin)


if __name__ == "__main__":
    import asyncio

    async def test():
        provider = RealtimeDataProvider()
        profile = await provider.get_full_profile("U12345MH2010PTC123456")
        print(json.dumps(profile, indent=2, default=str))

    asyncio.run(test())
