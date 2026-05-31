from importlib import import_module
from typing import Any

from services.ranking.schemas import PartnerProfile


PARTNER_VARIABLE_CANDIDATES = [
    "partners",
    "PARTNERS",
    "partner_list",
    "PARTNER_LIST",
]


def load_partner_profiles() -> list[PartnerProfile]:
    try:
        module = import_module("data.partners")
    except Exception:
        return []

    raw_partners = None
    for name in PARTNER_VARIABLE_CANDIDATES:
        value = getattr(module, name, None)
        if isinstance(value, list):
            raw_partners = value
            break

    if raw_partners is None:
        return []

    return [
        dict_to_partner_profile(partner)
        for partner in raw_partners
        if isinstance(partner, dict)
    ]


def dict_to_partner_profile(partner: dict[str, Any]) -> PartnerProfile:
    return PartnerProfile(
        name=str(partner.get("name") or ""),
        specialty_tags=list(partner.get("specialty_tags") or []),
        is_premium=bool(partner.get("is_premium")),
        success_rate=float(partner.get("success_rate") or 0.0),
        response_speed=str(partner.get("response_speed") or ""),
        financial_status=str(partner.get("financial_status") or ""),
        is_excluded=bool(partner.get("is_excluded")),
    )
