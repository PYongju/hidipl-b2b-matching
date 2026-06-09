import re
from dataclasses import dataclass, field
from typing import Any


AMOUNT_PATTERN = re.compile(r"(?:₩|￦|\\)?\s*(\d{1,3}(?:,\d{3})+|\d{5,})")


@dataclass
class AmountExtraction:
    supply_amount: int | None = None
    tax_amount: int | None = None
    total_amount: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


def extract_summary_amounts(text: str) -> AmountExtraction:
    result = AmountExtraction()
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        compact = re.sub(r"\s+", "", line).lower()
        nearby = " ".join(lines[index:index + 3])
        amounts = _amounts(line) or _amounts(nearby)
        if not amounts:
            continue

        if _contains_any(compact, ["부가세포함가", "전체합계", "전체합계(vat포함)", "vat합계", "총금액", "vat포함"]):
            _set_if_better(result, "total_amount", amounts[-1], line)
        elif _contains_any(compact, ["부가가치세", "부가세", "세액"]) or compact == "vat":
            _set_if_better(result, "tax_amount", amounts[-1], line)
        elif _contains_any(compact, ["공급가액", "공급금액", "공급가", "vat별도", "소계", "합계"]):
            _set_if_better(result, "supply_amount", amounts[-1], line)

    # Some summaries place supply/tax on the VAT-separate row and total on the next row.
    for index, line in enumerate(lines):
        compact = re.sub(r"\s+", "", line).lower()
        if "vat별도" not in compact:
            continue
        amounts = _amounts(line)
        if len(amounts) < 2:
            amounts = _amounts(" ".join(lines[index:index + 2]))
        if len(amounts) >= 2:
            _set_if_better(result, "supply_amount", amounts[0], line)
            _set_if_better(result, "tax_amount", amounts[1], line)

    return result


def _amounts(text: str) -> list[int]:
    return [int(match.group(1).replace(",", "")) for match in AMOUNT_PATTERN.finditer(text)]


def _contains_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def _set_if_better(result: AmountExtraction, field_name: str, value: int, evidence_text: str) -> None:
    if value <= 0:
        return
    current = getattr(result, field_name)
    if current is None or value >= current:
        setattr(result, field_name, value)
        result.evidence[field_name] = {
            "source": "summary_row",
            "text": evidence_text[:500],
        }
