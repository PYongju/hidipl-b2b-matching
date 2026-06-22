import re
from dataclasses import dataclass, field
from typing import Any
from typing import Iterable

from services.ocr.schemas import OCRTable
from services.parser.schemas import QuoteItem


SUMMARY_TOKENS = ["합계", "소계", "공급가", "부가세", "부가가치세", "vat", "총금액", "전체합계"]
AMOUNT_RE = re.compile(r"(?:₩|￦|\\)?\s*(\d{1,3}(?:,\d{3})+|\d{5,})")


@dataclass
class RuleItemBlock:
    row_no: str | None = None
    item_name: str = ""
    spec_lines: list[str] = field(default_factory=list)
    quantity: float | None = None
    unit: str | None = None
    unit_price: int | None = None
    supply_amount: int | None = None
    tax_amount: int | None = None
    total_price: int | None = None
    raw_lines: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


def remove_summary_rows(items: Iterable[QuoteItem]) -> list[QuoteItem]:
    result = []
    for item in items:
        text = " ".join(str(value or "") for value in [item.item_name, item.spec, item.note]).lower()
        compact = re.sub(r"\s+", "", text)
        if any(token in compact for token in SUMMARY_TOKENS):
            continue
        result.append(item)
    return result


def table_fingerprint(tables: list[OCRTable]) -> list[str]:
    fingerprints = []
    for table in tables:
        if not table.cells:
            continue
        header = " ".join(table.cells[0]).lower()
        roles = []
        for role, aliases in {
            "item_name": ["품명", "품목", "구분", "내용"],
            "quantity": ["수량", "qty"],
            "unit_price": ["단가"],
            "supply_amount": ["공급가액", "금액"],
            "tax_amount": ["세액", "부가세"],
        }.items():
            if any(alias in header for alias in aliases):
                roles.append(role)
        fingerprints.append("+".join(roles))
    return fingerprints


def reconstruct_quote_items_from_tables(tables: list[OCRTable]) -> tuple[list[QuoteItem], list[dict[str, Any]]]:
    items: list[QuoteItem] = []
    evidence: list[dict[str, Any]] = []
    for table_index, table in enumerate(tables):
        blocks = reconstruct_item_blocks(table)
        if blocks:
            for block in blocks:
                items.append(
                    QuoteItem(
                        item_name=block.item_name,
                        spec=_clean_spec_text(" ".join(block.spec_lines)) or None,
                        quantity=block.quantity,
                        unit=block.unit,
                        unit_price=block.unit_price,
                        supply_amount=block.supply_amount,
                        tax_amount=block.tax_amount,
                        amount=block.supply_amount or block.total_price,
                    )
                )
                evidence.append({"table_index": table_index, **block.evidence})
            continue

        headerless_blocks = reconstruct_headerless_priced_item_blocks(table)
        for block in headerless_blocks:
            items.append(
                QuoteItem(
                    item_name=block.item_name,
                    spec=_clean_spec_text(" ".join(block.spec_lines)) or None,
                    quantity=block.quantity,
                    unit=block.unit,
                    unit_price=block.unit_price,
                    supply_amount=block.supply_amount,
                    tax_amount=block.tax_amount,
                    amount=block.supply_amount or block.total_price,
                )
            )
            evidence.append({"table_index": table_index, **block.evidence})
    return items, evidence


def reconstruct_headerless_priced_item_blocks(table: OCRTable) -> list[RuleItemBlock]:
    rows = [[str(cell or "").strip() for cell in row] for row in table.cells]
    blocks: list[RuleItemBlock] = []
    for row_index, row in enumerate(rows):
        nonempty = [cell for cell in row if cell]
        if len(nonempty) < 3:
            continue
        row_text = " ".join(nonempty)
        if _is_summary_text(row_text):
            continue

        amount_cell = next(
            (cell for cell in reversed(nonempty) if _parse_amount(cell) is not None),
            "",
        )
        supply_amount = _parse_amount(amount_cell)
        if supply_amount is None:
            continue

        item_name = nonempty[0].strip()
        if not item_name or _looks_like_amount_only(item_name):
            continue
        if not _looks_like_itemized_priced_row(row_text, item_name):
            continue

        spec_cells = [
            cell
            for cell in nonempty[1:]
            if cell != amount_cell and _parse_amount(cell) is None
        ]
        quantity, unit = _parse_quantity_unit(" ".join(spec_cells))
        spec_lines = [
            cell
            for cell in spec_cells
            if cell.strip() and not re.fullmatch(r"\d+(?:\.\d+)?\s*\S{0,4}", cell.strip())
        ]
        blocks.append(
            RuleItemBlock(
                item_name=item_name,
                spec_lines=spec_lines,
                quantity=quantity,
                unit=unit,
                supply_amount=supply_amount,
                total_price=supply_amount,
                raw_lines=[row_text],
                evidence={
                    "source": "ocr_headerless_priced_table",
                    "row_indexes": [row_index],
                },
            )
        )
    if len(blocks) < 2:
        return []
    return blocks


def reconstruct_item_blocks(table: OCRTable) -> list[RuleItemBlock]:
    rows = [[str(cell or "").strip() for cell in row] for row in table.cells]
    header_index, roles = _find_header_roles(rows)
    if header_index is None or "item_name" not in roles:
        return []

    blocks: list[RuleItemBlock] = []
    current: RuleItemBlock | None = None
    for row_index, row in enumerate(rows[header_index + 1:], start=header_index + 1):
        row_text = " ".join(cell for cell in row if cell).strip()
        if not row_text or _is_summary_text(row_text):
            continue

        item_name = _cell(row, roles.get("item_name"))
        spec = _cell(row, roles.get("spec"))
        row_no = _cell(row, roles.get("row_no"))
        quantity = _parse_number(_cell(row, roles.get("quantity")))
        unit = _cell(row, roles.get("unit")) or None
        unit_price = _parse_amount(_cell(row, roles.get("unit_price")))
        supply_amount = _parse_amount(_cell(row, roles.get("supply_amount")))
        tax_amount = _parse_amount(_cell(row, roles.get("tax_amount")))

        if item_name and not _looks_like_amount_only(item_name):
            if current:
                blocks.append(current)
            current = RuleItemBlock(
                row_no=row_no or None,
                item_name=item_name,
                spec_lines=[spec] if spec else [],
                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                supply_amount=supply_amount,
                tax_amount=tax_amount,
                total_price=supply_amount,
                raw_lines=[row_text],
                evidence={"source": "ocr_table", "header_roles": roles, "row_indexes": [row_index]},
            )
            continue

        if current is None:
            continue
        detail = " ".join(value for value in [item_name, spec] if value).strip()
        if detail and not _looks_like_amount_only(detail):
            current.spec_lines.append(detail)
        current.raw_lines.append(row_text)
        current.evidence["row_indexes"].append(row_index)
        current.quantity = current.quantity if current.quantity is not None else quantity
        current.unit = current.unit or unit
        current.unit_price = current.unit_price if current.unit_price is not None else unit_price
        current.supply_amount = current.supply_amount if current.supply_amount is not None else supply_amount
        current.tax_amount = current.tax_amount if current.tax_amount is not None else tax_amount
        current.total_price = current.supply_amount

    if current:
        blocks.append(current)
    return [block for block in blocks if block.item_name and not _is_summary_text(block.item_name)]


def assign_amount_pairs_by_order(
    items: list[QuoteItem],
    source_text: str,
    summary_supply_amount: int | None,
) -> dict[str, Any] | None:
    if not items or not summary_supply_amount:
        return None
    missing = [item for item in items if item.amount is None and item.supply_amount is None]
    if len(missing) != len(items):
        return None

    pairs = _extract_currency_amount_pairs(source_text)
    if len(pairs) != len(items):
        return None
    assigned_sum = sum(pair[1] for pair in pairs)
    if assigned_sum != summary_supply_amount:
        return None

    assignments = []
    for item, (unit_price, supply_amount, raw_line) in zip(items, pairs):
        quantity = item.quantity
        if quantity in (None, 0) and unit_price and supply_amount % unit_price == 0:
            quantity = float(supply_amount // unit_price)
        if quantity and int(quantity * unit_price) != supply_amount:
            return None
        item.quantity = quantity
        item.unit_price = unit_price
        item.supply_amount = supply_amount
        item.amount = supply_amount
        assignments.append(
            {
                "item_name": item.item_name,
                "unit_price": unit_price,
                "supply_amount": supply_amount,
                "source_text": raw_line[:300],
            }
        )
    return {
        "source": "ordered_currency_amount_pairs",
        "confidence": "high",
        "summary_supply_amount": summary_supply_amount,
        "assignments": assignments,
    }


def align_profile_item_roles(
    items: list[QuoteItem],
    source_text: str,
    profile_names: list[str],
) -> dict[str, Any] | None:
    if "vat_separate_item_tax_table" not in profile_names:
        return None
    priced_items = [item for item in items if (item.amount or item.supply_amount)]
    if len(priced_items) < 4:
        return None

    role_patterns = [
        (
            "SYSTEM_EQUIPMENT",
            r"(?:LED\s*Controller|Novastar(?:\s+[A-Z0-9_-]+)?|Controller)",
            "LED Controller",
        ),
        (
            "MATERIALS",
            r"(?:구조물(?:\s*설계\s*/?\s*제작)?|structure)",
            "구조물 설계 / 제작",
        ),
        ("INSTALL", r"(?:설치비|설치\s*공사|installation)", "설치비"),
    ]
    roles = []
    for role, pattern, fallback_name in role_patterns:
        match = re.search(pattern, source_text, re.IGNORECASE)
        if not match:
            return None
        roles.append(
            {
                "role": role,
                "name": re.sub(r"\s+", " ", match.group(0)).strip() or fallback_name,
            }
        )

    target_items = priced_items[1:4]
    if len(target_items) != len(roles):
        return None
    changes = []
    for item, role in zip(target_items, roles):
        before = item.item_name
        item.item_name = role["name"]
        changes.append(
            {
                "before": before,
                "after": item.item_name,
                "role": role["role"],
                "amount": item.amount or item.supply_amount,
                "source": "profile_semantic_role_alignment",
            }
        )
    return {"profile": "vat_separate_item_tax_table", "changes": changes}


def _find_header_roles(rows: list[list[str]]) -> tuple[int | None, dict[str, int]]:
    aliases = {
        "row_no": ("no", "no.", "번호", "순번"),
        "item_name": ("품명", "품목", "구분", "제품명", "모델명", "품 명"),
        "spec": ("내용", "상세내역", "상세 내역", "규격", "비고"),
        "quantity": ("수량", "qty", "q'ty"),
        "unit": ("단위",),
        "unit_price": ("단가", "견적단가"),
        "supply_amount": ("공급가액", "공급가", "견적금액", "금액", "소계"),
        "tax_amount": ("세액", "부가세", "vat"),
    }
    best: tuple[int | None, dict[str, int]] = (None, {})
    for row_index, row in enumerate(rows[:8]):
        roles: dict[str, int] = {}
        for column_index, cell in enumerate(row):
            compact = re.sub(r"\s+", "", cell).lower()
            for role, names in aliases.items():
                if role in roles:
                    continue
                if any(re.sub(r"\s+", "", name).lower() in compact for name in names):
                    roles[role] = column_index
        if len(roles) > len(best[1]):
            best = (row_index, roles)
    if len(best[1]) < 2:
        return None, {}
    return best


def _extract_currency_amount_pairs(text: str) -> list[tuple[int, int, str]]:
    pairs = []
    for line in text.splitlines():
        if _is_summary_text(line):
            continue
        if not re.search(r"[₩￦\\]", line):
            continue
        amounts = [int(match.group(1).replace(",", "")) for match in AMOUNT_RE.finditer(line)]
        if len(amounts) == 2 and all(value > 0 for value in amounts):
            pairs.append((amounts[0], amounts[1], line.strip()))
    return pairs


def _is_summary_text(text: str) -> bool:
    compact = re.sub(r"\s+", "", text).lower()
    return any(token in compact for token in SUMMARY_TOKENS)


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def _parse_amount(value: str) -> int | None:
    match = AMOUNT_RE.search(value or "")
    return int(match.group(1).replace(",", "")) if match else None


def _parse_number(value: str) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", value or "")
    return float(match.group(0)) if match else None


def _parse_quantity_unit(value: str) -> tuple[float | None, str | None]:
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(EA|SET|SETS|식|개|대|조|매|unit|units)?",
        value or "",
        flags=re.IGNORECASE,
    )
    unit_match = re.search(
        r"(\d+(?:\.\d+)?)\s+(EA|SET|SETS|식|개|대|조|매|unit|units)\b",
        value or "",
        flags=re.IGNORECASE,
    )
    if unit_match:
        match = unit_match
    if not match:
        return None, None
    quantity = float(match.group(1))
    unit = match.group(2) or None
    return quantity, unit


def _looks_like_itemized_priced_row(row_text: str, item_name: str) -> bool:
    normalized = (row_text or "").lower()
    item_normalized = (item_name or "").lower()
    item_keywords = [
        "비디오월",
        "video wall",
        "패널",
        "panel",
        "브라켓",
        "bracket",
        "설치",
        "시운전",
        "install",
        "잡자재",
        "케이블",
        "cable",
        "기타",
        "led",
        "display",
        "did",
    ]
    if any(keyword in normalized for keyword in item_keywords):
        return True
    if re.search(r"\b(?:EA|SET|식|개|대)\b", row_text, flags=re.IGNORECASE):
        return True
    return len(item_normalized.strip()) >= 2


def _looks_like_amount_only(value: str) -> bool:
    compact = re.sub(r"[\s₩￦\\,]", "", value or "")
    return bool(compact) and compact.isdigit()


def _clean_spec_text(value: str) -> str:
    value = re.sub(r":?unselected:?", " ", value or "", flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()
