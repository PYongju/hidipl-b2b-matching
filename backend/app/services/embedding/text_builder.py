from services.parser.schemas import LineItem, QuoteDocument
from services.requirement.schemas import RequirementInfo, RequirementProduct


def build_requirement_embedding_text(requirement: RequirementInfo) -> str:
    lines: list[str] = []

    _append_line(lines, "고객사", requirement.customer_name)
    _append_line(lines, "프로젝트명", getattr(requirement, "project_name", None))
    _append_line(lines, "요청 요약", requirement.request_summary)
    _append_line(lines, "활용 용도", _metadata_value(requirement, "frontend_fields", "활용 용도"))
    _append_line(lines, "카테고리", getattr(requirement, "category", None))
    _append_line(lines, "디스플레이 크기", getattr(requirement, "display_size_text", None))
    _append_line(lines, "수량", getattr(requirement, "quantity_text", None))

    if requirement.products:
        lines.append("요청 제품:")
        for product in requirement.products:
            lines.append(f"- {_format_requirement_product(product)}")

    _append_line(lines, "지역", requirement.region)
    _append_line(lines, "설치 일정", requirement.install_schedule_text)
    _append_line(lines, "현재 단계", requirement.project_stage)
    _append_line(lines, "예산 상한", _format_money_value(requirement.budget_max))
    _append_line(lines, "운영 시간", getattr(requirement, "operation_time", None))
    _append_line(lines, "우선 검토 기준", getattr(requirement, "review_preset", None))
    _append_line(lines, "추가 요청사항", getattr(requirement, "other_conditions", None))
    _append_line(lines, "첨부 메모", getattr(requirement, "attachment_memo", None))

    if requirement.notes:
        lines.append(f"기타 조건: {', '.join(requirement.notes)}")

    if requirement.required_keywords:
        lines.append(f"키워드: {', '.join(requirement.required_keywords)}")

    return "\n".join(line for line in lines if line.strip())


def build_quote_embedding_text(quote: QuoteDocument) -> str:
    lines: list[str] = []

    _append_line(lines, "업체명", quote.vendor_name)
    _append_line(lines, "프로젝트명", quote.project_name)
    _append_line(lines, "공급가 합계", quote.total_supply_price)
    _append_line(lines, "VAT 포함 총액", quote.total_with_vat)
    _append_line(lines, "납기 주수", _format_weeks(quote.delivery_weeks))
    _append_line(lines, "납기 원문", quote.delivery_basis_raw)
    _append_line(lines, "보증기간", _format_months(quote.warranty_months))
    _append_line(lines, "비고", quote.notes_raw)

    if quote.line_items:
        lines.append("견적 항목:")
        for item in quote.line_items:
            lines.append(f"- {_format_line_item(item)}")

    return "\n".join(line for line in lines if line.strip())


def _format_requirement_product(product: RequirementProduct) -> str:
    parts: list[str] = []

    for value in [product.display_type, product.name, product.product_type]:
        if value and value not in parts:
            parts.append(value)

    if product.width_mm is not None and product.height_mm is not None:
        parts.append(f"크기 {product.width_mm}x{product.height_mm}mm")

    if product.pitch_mm is not None:
        parts.append(f"Pitch {product.pitch_mm}")

    if product.pitch_max_mm is not None:
        parts.append(f"Pitch {product.pitch_max_mm} 이하")

    if product.diagonal_inch is not None:
        parts.append(f"{product.diagonal_inch:g}인치")

    if product.layout_rows is not None and product.layout_cols is not None:
        parts.append(f"{product.layout_rows}x{product.layout_cols}")

    quantity_text = (getattr(product, "metadata", {}) or {}).get("quantity_text")
    if quantity_text:
        parts.append(f"수량 {quantity_text}")
    elif product.quantity is not None:
        parts.append(_format_quantity(product.quantity, product.unit) or "")

    return ", ".join(part for part in parts if part) if parts else product.raw_text


def _format_line_item(item: LineItem) -> str:
    parts: list[str] = []

    for value in [
        item.name,
        item.category.value,
        _format_quantity(item.quantity, item.unit),
        _format_money("단가", item.unit_price),
        _format_money("금액", item.total_price),
        f"선택항목 {item.is_optional}",
        _truncate(item.spec_raw, 500),
        _format_spec_parsed(item.spec_parsed),
    ]:
        if value:
            parts.append(str(value))

    return ", ".join(parts)


def _append_line(lines: list[str], label: str, value: object | None) -> None:
    if value is None:
        return

    text = str(value).strip()
    if text:
        lines.append(f"{label}: {text}")


def _metadata_value(requirement: RequirementInfo, dict_key: str, item_key: str) -> str | None:
    metadata = getattr(requirement, "metadata", {}) or {}
    value = (metadata.get(dict_key) or {}).get(item_key)
    return str(value).strip() if value else None


def _format_money_value(value: int | None) -> str | None:
    if value is None:
        return None
    return f"{value}원"


def _format_months(value: int | None) -> str | None:
    if value is None:
        return None
    return f"{value}개월"


def _format_weeks(value: int | None) -> str | None:
    if value is None:
        return None
    return f"{value}주"


def _format_quantity(quantity: float | None, unit: str | None) -> str | None:
    if quantity is None:
        return None

    if unit:
        return f"{quantity:g}{unit}"

    return f"{quantity:g}"


def _format_money(label: str, value: int | None) -> str | None:
    if value is None:
        return None
    return f"{label} {value}"


def _format_spec_parsed(spec_parsed: dict) -> str | None:
    if not spec_parsed:
        return None

    return "spec_parsed: " + ", ".join(
        f"{key}={value}" for key, value in spec_parsed.items()
    )


def _truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None

    value = value.strip()
    if len(value) <= max_length:
        return value

    return value[:max_length].rstrip()
