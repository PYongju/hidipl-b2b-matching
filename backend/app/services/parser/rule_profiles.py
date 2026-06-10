from dataclasses import dataclass, field
import re


@dataclass(frozen=True)
class RuleProfile:
    name: str
    fingerprint_patterns: tuple[str, ...] = ()
    header_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    summary_patterns: tuple[str, ...] = ()

    def matches(self, text: str) -> bool:
        return all(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in self.fingerprint_patterns)


COMMON_PROFILE = RuleProfile(
    name="generic_quote_table",
    header_aliases={
        "item_name": ("품명", "품목", "구분", "내용"),
        "spec": ("상세내역", "규격", "비고"),
        "quantity": ("수량", "Qty"),
        "unit": ("단위",),
        "unit_price": ("단가",),
        "supply_amount": ("공급가액", "공급가", "금액", "견적금액"),
        "tax_amount": ("세액", "부가세"),
    },
    summary_patterns=(r"합\s*계", r"부가\s*가치\s*세", r"전\s*체\s*합\s*계", r"VAT\s*합계"),
)

ORION_STYLE_PROFILE = RuleProfile(
    name="vat_separate_item_tax_table",
    fingerprint_patterns=(
        r"VAT\s*별도",
        r"VAT\s*합계",
        r"품\s*명.*수량.*단위.*단가.*공급가액.*세\s*액",
    ),
    header_aliases=COMMON_PROFILE.header_aliases,
    summary_patterns=(r"VAT\s*별도", r"VAT\s*합계"),
)


def select_profiles(text: str) -> list[RuleProfile]:
    profiles = [COMMON_PROFILE]
    if ORION_STYLE_PROFILE.matches(text):
        profiles.append(ORION_STYLE_PROFILE)
    return profiles
