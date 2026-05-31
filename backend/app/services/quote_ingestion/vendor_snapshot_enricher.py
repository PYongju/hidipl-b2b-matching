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
            ],
        }

    def _profile_to_snapshot(self, partner: PartnerProfile) -> VendorSnapshot:
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
            source="data/partners.py",
        )

    def _response_speed_score(self, value: str | None) -> float | None:
        return {
            "fast": 100.0,
            "normal": 70.0,
            "slow": 40.0,
        }.get((value or "").lower())
