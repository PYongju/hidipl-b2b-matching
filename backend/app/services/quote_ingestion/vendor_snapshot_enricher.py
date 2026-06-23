import re
from typing import Any

from services.parser.schemas import QuoteDocument, VendorSnapshot
from services.parser.vendor_name_resolver import normalize_company_name
from services.ranking.partner_loader import load_partner_profiles
from services.ranking.schemas import PartnerProfile


class VendorSnapshotEnricher:
    def __init__(self, partner_profiles: list[PartnerProfile] | None = None) -> None:
        self.partner_profiles = (
            partner_profiles if partner_profiles is not None else load_partner_profiles()
        )
        self.partner_index = {
            normalize_company_name(profile.name): profile
            for profile in self.partner_profiles
        }

    def enrich(self, quote: QuoteDocument) -> tuple[QuoteDocument, dict[str, Any]]:
        normalized_vendor_name = normalize_company_name(quote.vendor_name)
        partner = self.partner_index.get(normalized_vendor_name)

        if partner is None:
            quote.vendor_snapshot = None
            return quote, {
                "vendor_snapshot_source": "data/partners.py",
                "partner_found": False,
                "matched_partner_name": None,
                "normalized_vendor_name": normalized_vendor_name,
                "snapshot_fields": [],
                "check_required": ["파트너 마스터 매칭 필요"],
            }

        quote.vendor_snapshot = self._profile_to_snapshot(partner)
        return quote, {
            "vendor_snapshot_source": "data/partners.py",
            "partner_found": True,
            "matched_partner_name": partner.name,
            "normalized_vendor_name": normalized_vendor_name,
            "snapshot_fields": [
                "is_premium_partner",
                "past_success_rate",
                "response_speed_score",
                "response_speed",
                "financial_status",
                "is_excluded",
                "specialty_tags",
                "installation_count",
                "industry_breakdown",
                "solution_breakdown",
                "scale_breakdown",
                "avg_projects_3yr",
                "avg_revenue_3yr",
                "years_in_business",
                "representative",
                "company_location",
            ],
        }

    def _profile_to_snapshot(self, partner: PartnerProfile) -> VendorSnapshot:
        avg_revenue_3yr_million = parse_revenue_to_million(
            getattr(partner, "avg_revenue_3yr", None)
        )
        return VendorSnapshot(
            vendor_id=getattr(partner, "vendor_id", None),
            vendor_name=partner.name,
            is_premium_partner=partner.is_premium,
            past_success_rate=partner.success_rate,
            response_speed_score=self._response_speed_score(partner.response_speed),
            response_speed=partner.response_speed,
            financial_status=partner.financial_status,
            is_excluded=partner.is_excluded,
            specialty_tags=list(partner.specialty_tags),
            installation_count=getattr(partner, "installation_count", None),
            industry_breakdown=dict(getattr(partner, "industry_breakdown", {}) or {}),
            solution_breakdown=dict(getattr(partner, "solution_breakdown", {}) or {}),
            scale_breakdown=dict(getattr(partner, "scale_breakdown", {}) or {}),
            avg_projects_3yr=getattr(partner, "avg_projects_3yr", None),
            avg_revenue_3yr=getattr(partner, "avg_revenue_3yr", None),
            avg_revenue_3yr_million=avg_revenue_3yr_million,
            years_in_business=getattr(partner, "years_in_business", None),
            representative=getattr(partner, "representative", None),
            company_age_years=getattr(partner, "years_in_business", None),
            avg_project_count_3y=getattr(partner, "avg_projects_3yr", None),
            avg_revenue_3y_million=avg_revenue_3yr_million,
            company_location=getattr(partner, "company_location", None),
            source="data/partners.py",
        )

    def _response_speed_score(self, value: str | None) -> float | None:
        return {
            "fast": 100.0,
            "normal": 70.0,
            "slow": 40.0,
        }.get((value or "").lower())


def parse_revenue_to_million(value: str | None) -> float | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    number_match = re.search(r"([0-9][0-9,]*(?:\.[0-9]+)?)", text)
    if not number_match:
        return None

    try:
        number = float(number_match.group(1).replace(",", ""))
    except ValueError:
        return None

    normalized = text.replace(" ", "")
    if "억원" in normalized or "억" in normalized:
        return number * 100.0
    if "백만원" in normalized:
        return number

    return number
