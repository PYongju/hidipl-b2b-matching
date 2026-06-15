import re
from typing import Any

from services.api_demo.schemas import ProjectCreateRequest
from services.requirement.schemas import RequirementInfo, RequirementProduct


FRONTEND_REQUEST_LABELS = [
    "프로젝트명",
    "활용 용도",
    "디스플레이 크기",
    "수량",
    "운영 시간",
    "카테고리",
    "예산 상한",
    "현재 단계",
    "우선 검토 기준",
    "추가 요청사항",
    "첨부 메모",
]

EMPTY_VALUES = {"", "미입력", "없음", "null", "undefined", "none"}


def build_requirement_info_from_project_payload(
    payload: ProjectCreateRequest,
    *,
    request_id: str | None = None,
) -> RequirementInfo:
    payload_dict = (
        payload.model_dump()
        if hasattr(payload, "model_dump")
        else payload.dict()
    )
    return build_requirement_info_from_project_payload_dict(
        payload_dict,
        request_id=request_id,
    )


def build_requirement_info_from_project_payload_dict(
    payload: dict[str, Any],
    *,
    request_id: str | None = None,
) -> RequirementInfo:
    request_text = str(payload.get("request_text") or "")
    frontend_fields = parse_frontend_request_text(request_text)

    customer_name = normalize_empty(
        payload.get("company_name") or payload.get("customer_name")
    )
    region = normalize_empty(payload.get("location") or payload.get("region"))
    install_schedule_text = normalize_empty(
        payload.get("deadline") or payload.get("install_schedule_text")
    )

    project_name = frontend_fields.get("프로젝트명")
    usage = frontend_fields.get("활용 용도")
    display_size = frontend_fields.get("디스플레이 크기")
    quantity_text = frontend_fields.get("수량")
    operation_time = frontend_fields.get("운영 시간")
    category = frontend_fields.get("카테고리")
    budget_text = frontend_fields.get("예산 상한")
    project_stage = frontend_fields.get("현재 단계")
    review_preset = frontend_fields.get("우선 검토 기준")
    other_conditions = frontend_fields.get("추가 요청사항")
    attachment_memo = frontend_fields.get("첨부 메모")

    explicit_products = payload.get("products") or []
    products = _build_products(
        category=category,
        display_size=display_size,
        quantity_text=quantity_text,
        explicit_products=explicit_products,
    )
    budget_max = parse_budget_amount(budget_text)
    request_summary = _build_request_summary(
        usage=usage,
        category=category,
        display_size=display_size,
        other_conditions=other_conditions,
        customer_name=customer_name,
        region=region,
        install_schedule_text=install_schedule_text,
    )
    notes = [
        value
        for value in [operation_time, review_preset, other_conditions, attachment_memo]
        if value
    ]
    required_keywords = _build_required_keywords(
        category=category,
        usage=usage,
        display_size=display_size,
        other_conditions=other_conditions,
        products=products,
    )

    metadata = {
        "source": "frontend_project_payload",
        "requirement_source": "frontend_project_payload",
        "request_id": request_id,
        "original_request_text": request_text,
        "frontend_fields": frontend_fields,
        "raw_frontend_fields": parse_frontend_request_text(
            request_text,
            normalize=False,
        ),
        "budget_text": budget_text,
        "review_preset": review_preset,
        "operation_time": operation_time,
        "other_conditions": other_conditions,
        "attachment_memo": attachment_memo,
        "quantity_text": quantity_text,
        "display_size": display_size,
        "category": category,
        "requirement_details_missing": not any(
            [frontend_fields, products, required_keywords]
        ),
    }

    return RequirementInfo(
        raw_text=request_text,
        customer_name=customer_name,
        project_name=project_name,
        request_summary=request_summary,
        products=products,
        region=region,
        install_schedule_text=install_schedule_text,
        project_stage=project_stage,
        category=category,
        display_size_text=display_size,
        quantity_text=quantity_text,
        operation_time=operation_time,
        review_preset=review_preset,
        other_conditions=other_conditions,
        attachment_memo=attachment_memo,
        budget_min=None,
        budget_max=budget_max,
        notes=notes,
        required_keywords=required_keywords,
        metadata=metadata,
    )


def is_frontend_project_payload(payload: ProjectCreateRequest) -> bool:
    if (
        normalize_empty(payload.company_name)
        or normalize_empty(payload.location)
        or normalize_empty(payload.deadline)
    ):
        return True
    fields = parse_frontend_request_text(payload.request_text)
    return len(fields) >= 2


def has_meaningful_request_text(payload: ProjectCreateRequest) -> bool:
    request_text = getattr(payload, "request_text", None)
    text = normalize_empty(request_text)
    if not text:
        return False

    raw_frontend_fields = parse_frontend_request_text(
        request_text,
        normalize=False,
    )
    if len(raw_frontend_fields) >= 2:
        return bool(parse_frontend_request_text(request_text))
    return True


def parse_frontend_request_text(
    request_text: str | None,
    *,
    normalize: bool = True,
) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in (request_text or "").splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label = label.strip()
        if label not in FRONTEND_REQUEST_LABELS:
            continue
        cleaned = normalize_empty(value) if normalize else value.strip()
        if cleaned is not None:
            fields[label] = cleaned
    return fields


def normalize_empty(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in EMPTY_VALUES:
        return None
    return text


def parse_budget_amount(value: str | None) -> int | None:
    text = normalize_empty(value)
    if not text:
        return None
    compact = text.replace(",", "").replace(" ", "")
    number_match = re.search(r"(\d+(?:\.\d+)?)", compact)
    if not number_match:
        return None
    number = float(number_match.group(1))
    if "억" in compact:
        return int(number * 100_000_000)
    if "천만" in compact:
        return int(number * 10_000_000)
    if "백만" in compact:
        return int(number * 1_000_000)
    if "만원" in compact:
        return int(number * 10_000)
    if "천원" in compact:
        return int(number * 1_000)
    return int(number)


def _build_products(
    *,
    category: str | None,
    display_size: str | None,
    quantity_text: str | None,
    explicit_products: list[dict[str, Any]],
) -> list[RequirementProduct]:
    products: list[RequirementProduct] = []
    for product in explicit_products:
        raw_text = ", ".join(
            f"{key}: {value}"
            for key, value in product.items()
            if normalize_empty(value) is not None
        )
        products.append(
            RequirementProduct(
                product_type=normalize_empty(product.get("product_type")) or category,
                name=normalize_empty(product.get("name")) or category,
                quantity=_parse_quantity_number(product.get("quantity") or quantity_text),
                unit=_parse_quantity_unit(product.get("quantity") or quantity_text),
                width_mm=_parse_dimension(display_size or raw_text, index=0),
                height_mm=_parse_dimension(display_size or raw_text, index=1),
                raw_text=raw_text or " / ".join(
                    value for value in [category, display_size, quantity_text] if value
                ),
                metadata={
                    "display_size": display_size,
                    "quantity_text": quantity_text,
                    "source": "frontend_project_payload",
                },
            )
        )

    if not products and any([category, display_size, quantity_text]):
        products.append(
            RequirementProduct(
                product_type=category,
                name=category or display_size,
                quantity=_parse_quantity_number(quantity_text),
                unit=_parse_quantity_unit(quantity_text),
                width_mm=_parse_dimension(display_size, index=0),
                height_mm=_parse_dimension(display_size, index=1),
                raw_text=" / ".join(
                    value for value in [category, display_size, quantity_text] if value
                ),
                metadata={
                    "display_size": display_size,
                    "quantity_text": quantity_text,
                    "source": "frontend_project_payload",
                },
            )
        )
    return products


def _parse_dimension(value: str | None, *, index: int) -> int | None:
    text = normalize_empty(value)
    if not text:
        return None
    match = re.search(r"(\d{3,5})\s*[xX×]\s*(\d{3,5})", text.replace(",", ""))
    if not match:
        return None
    return int(match.group(index + 1))


def _parse_quantity_number(value: Any) -> float | None:
    text = normalize_empty(value)
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def _parse_quantity_unit(value: Any) -> str | None:
    text = normalize_empty(value)
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?\s*([^\d\s]+)", text)
    return match.group(1) if match else None


def _build_request_summary(
    *,
    usage: str | None,
    category: str | None,
    display_size: str | None,
    other_conditions: str | None,
    customer_name: str | None = None,
    region: str | None = None,
    install_schedule_text: str | None = None,
) -> str | None:
    parts = [value for value in [usage, category, display_size, other_conditions] if value]
    if parts:
        return " / ".join(parts)
    fallback_parts = [
        value
        for value in [customer_name, region, install_schedule_text]
        if value
    ]
    if fallback_parts:
        return " / ".join(fallback_parts)
    return "프로젝트 요구사항 미상"


def _build_required_keywords(
    *,
    category: str | None,
    usage: str | None,
    display_size: str | None,
    other_conditions: str | None,
    products: list[RequirementProduct],
) -> list[str]:
    keywords = []
    for value in [category, usage, display_size, other_conditions]:
        if value:
            keywords.extend(_keyword_tokens(value))
    for product in products:
        for value in [product.product_type, product.name, product.raw_text]:
            if value:
                keywords.extend(_keyword_tokens(value))
    keywords.extend(["디스플레이", "설치"])
    return _dedupe_keywords(keywords)


def _keyword_tokens(value: str) -> list[str]:
    tokens = re.split(r"[\s,/()]+", value)
    return [token.strip() for token in tokens if len(token.strip()) >= 2]


def _dedupe_keywords(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = normalize_empty(value)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result
