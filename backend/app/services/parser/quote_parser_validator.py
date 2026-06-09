from __future__ import annotations

from math import ceil
import re
from typing import Any

from services.parser.schemas import LineItemCategory, QuoteDocument


SUMMARY_ROW_KEYWORDS = {
    "subtotal",
    "sub total",
    "supply total",
    "vat",
    "tax",
    "total",
    "grand total",
    "amount total",
    "합계",
    "소계",
    "총계",
    "부가세",
}

SPEC_KEYWORD_PATTERN = re.compile(
    r"(?:"
    r"fhd|uhd|4k|8k|cd|nit|mm|kg|kw|w\b|"
    r"해상도|화면\s*사이즈|화면사이즈|소비전력|밝기|베젤|bezel|무게|중량|"
    r"resolution|brightness|screen\s*size|power|weight"
    r")",
    flags=re.IGNORECASE,
)

DELIVERY_DISCUSSION_PATTERN = re.compile(r"별도\s*협의|별도협의|추후\s*협의|추후협의|협의")
DELIVERY_DAY_PATTERN = re.compile(r"(?P<days>\d{1,3})\s*(?:일|days?|day)")
DELIVERY_WEEK_PATTERN = re.compile(r"(?P<weeks>\d{1,2})\s*(?:주|weeks?|week)")
PROJECT_NAME_FALLBACK_MESSAGE = "프로젝트명이 문서에서 명확히 추출되지 않아 파일명 기준으로 보정됨"
PROJECT_NAME_MISSING_MESSAGE = "프로젝트명 확인 필요"
INVALID_PROJECT_NAMES = {
    "",
    "견적서",
    "견 적 서",
    "quotation",
    "quote",
    "estimate",
    "견적명",
    "건명",
    "프로젝트명",
    "미기재",
    "확인 필요",
}
KNOWN_VENDOR_NAME_TOKENS = [
    "딥사이닝",
    "시스메이트",
    "다올씨앤씨",
    "효성itx",
    "효성ITX",
    "삼성전자",
]


def validate_quote_document(quote: QuoteDocument) -> list[str]:
    warnings: list[str] = []

    if not quote.vendor_name.strip():
        warnings.append("vendor_name is empty.")

    if quote.total_with_vat is None:
        warnings.append("total_with_vat is empty.")

    amount_validation = build_amount_validation(quote)
    if amount_validation["validation_status"] not in {"normal", "not_enough_data"}:
        warnings.append(amount_validation["message"])

    warnings.extend(build_line_items_summary_warnings(quote))

    notes = quote.notes_raw.lower()
    if quote.warranty_months is not None and any(
        token in notes for token in ["warranty excluded", "보증 제외"]
    ):
        warnings.append("warranty_months conflicts with notes_raw.")

    if any(token in notes for token in ["installation separate", "설치비 별도", "설치 별도"]) and any(
        item.category.value == "INSTALL" and item.total_price
        for item in quote.line_items
    ):
        warnings.append("installation terms need review.")

    return _deduplicate(warnings)


def build_quote_document_check_required(
    quote: QuoteDocument,
    *,
    source_text: str = "",
    amount_validation: dict[str, Any] | None = None,
    delivery_validation: dict[str, Any] | None = None,
    multi_option_detection: dict[str, Any] | None = None,
) -> list[str]:
    checks: list[str] = []

    for item in quote.line_items:
        if item_name_spec_split_needs_review(item.name):
            checks.append("item_name/spec_raw 분리 확인 필요")
            break

    amount_validation = amount_validation or build_amount_validation(quote)
    message = amount_validation.get("message")
    if message and amount_validation["validation_status"] not in {"normal", "not_enough_data"}:
        checks.append(message)

    if build_line_item_validation(quote):
        checks.append("일부 품목의 수량×단가와 금액이 일치하지 않아 확인 필요")

    delivery_validation = delivery_validation or build_delivery_validation(quote)
    delivery_message = delivery_validation.get("message")
    if delivery_message:
        checks.append(delivery_message)

    multi_option = multi_option_detection or detect_multi_option(quote, source_text=source_text)
    if multi_option["is_multi_option_possible"]:
        checks.append("문서 내 복수 옵션 견적 확인 필요")
        labels = [
            candidate.get("label")
            for candidate in multi_option["option_total_candidates"]
            if candidate.get("label")
        ]
        if len(labels) >= 2:
            checks.append(
                f"{labels[0]}와 {labels[1]} 견적이 한 문서에 함께 포함되어 금액 분리 확인 필요"
            )

    return _deduplicate(checks)


def build_line_item_validation(quote: QuoteDocument) -> list[dict[str, Any]]:
    validations = []
    for item in quote.line_items:
        if item.unit_price is None or item.total_price is None or item.quantity in (None, 0):
            continue
        calculated = round(float(item.quantity) * int(item.unit_price))
        difference = int(item.total_price) - calculated
        if difference == 0:
            continue
        validations.append(
            {
                "item_name": item.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "supply_amount": item.total_price,
                "calculated_amount": calculated,
                "difference": difference,
                "validation_status": "line_item_arithmetic_mismatch",
                "auto_corrected": False,
            }
        )
    return validations


def resolve_project_name(
    quote: QuoteDocument,
    *,
    source_text: str = "",
    file_stem: str = "",
    parser_source: str = "parser",
) -> dict[str, Any]:
    original_project_name = quote.project_name or ""
    cleaned_original = clean_project_name(original_project_name)
    if is_valid_project_name(cleaned_original):
        quote.project_name = cleaned_original
        resolution = {
            "source": parser_source,
            "original_project_name": original_project_name,
            "resolved_project_name": quote.project_name,
            "file_stem": file_stem,
            "check_required_added": False,
        }
        return resolution

    ocr_project_name = extract_project_name_from_text(source_text)
    if ocr_project_name:
        quote.project_name = ocr_project_name
        return {
            "source": "ocr_label",
            "original_project_name": original_project_name,
            "resolved_project_name": quote.project_name,
            "file_stem": file_stem,
            "check_required_added": False,
        }

    fallback_project_name = build_project_name_from_file_stem(
        file_stem,
        vendor_name=quote.vendor_name,
    )
    if fallback_project_name:
        quote.project_name = fallback_project_name
        return {
            "source": "file_name_fallback",
            "original_project_name": original_project_name,
            "resolved_project_name": quote.project_name,
            "file_stem": file_stem,
            "check_required_added": True,
            "check_required_message": PROJECT_NAME_FALLBACK_MESSAGE,
        }

    quote.project_name = ""
    return {
        "source": "missing",
        "original_project_name": original_project_name,
        "resolved_project_name": "",
        "file_stem": file_stem,
        "check_required_added": True,
        "check_required_message": PROJECT_NAME_MISSING_MESSAGE,
    }


def is_valid_project_name(value: str | None) -> bool:
    text = normalize_space(value or "")
    if not text:
        return False
    compact = re.sub(r"\s+", "", text).lower()
    invalid_compact = {re.sub(r"\s+", "", item).lower() for item in INVALID_PROJECT_NAMES}
    return compact not in invalid_compact


def extract_project_name_from_text(source_text: str) -> str | None:
    for line in (source_text or "").splitlines():
        cleaned = normalize_space(line)
        if not cleaned:
            continue
        match = re.search(
            r"(?:건\s*명|견\s*적\s*명|프로젝트\s*명|project\s*name|project)\s*[:：]\s*(?P<value>.+)",
            cleaned,
            flags=re.IGNORECASE,
        )
        if match:
            candidate = clean_project_name(match.group("value"))
            if is_valid_project_name(candidate):
                return candidate
    return None


def build_project_name_from_file_stem(
    file_stem: str,
    *,
    vendor_name: str = "",
) -> str:
    text = normalize_space(file_stem.replace("_", " "))
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", text)
    text = re.sub(r"\b[0-9a-fA-F]{8,}\b", " ", text)
    remove_tokens = [vendor_name, *KNOWN_VENDOR_NAME_TOKENS]
    for token in remove_tokens:
        token = normalize_space(token)
        if token:
            text = re.sub(re.escape(token), " ", text, flags=re.IGNORECASE)
    text = clean_project_name(text)
    if len(text) > 50:
        text = text[:50].rstrip()
    return text if is_valid_project_name(text) else ""


def clean_project_name(value: str | None) -> str:
    text = normalize_space(value or "")
    text = re.sub(r"\.(pdf|xlsx|xls|png|jpe?g)$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(quotation|quote|estimate|no\.?)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"견\s*적\s*서|견\s*적\s*명|건\s*명|프로젝트\s*명", " ", text)
    text = re.sub(r"[-|:：]+$", "", text)
    for stop_token in ["견적일", "작성자", "연락처", "대표이사", "주소", "Quote Date", "Contact"]:
        index = text.lower().find(stop_token.lower())
        if index > 0:
            text = text[:index]
    return normalize_space(text)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()


def item_name_spec_split_needs_review(item_name: str | None) -> bool:
    if not item_name:
        return False
    return len(item_name.strip()) >= 50 and bool(SPEC_KEYWORD_PATTERN.search(item_name))


def build_amount_validation(
    quote: QuoteDocument,
    *,
    quoted_tax_amount: int | None = None,
) -> dict[str, Any]:
    quoted_supply = quote.total_supply_price
    quoted_total = quote.total_with_vat
    quoted_tax = quoted_tax_amount if quoted_tax_amount is not None else quote.tax_amount
    calculated_total = (
        quoted_supply + quoted_tax
        if quoted_supply is not None and quoted_tax is not None
        else None
    )
    difference = (
        quoted_total - calculated_total
        if quoted_total is not None and calculated_total is not None
        else None
    )
    expected_tax = round(quoted_supply * 0.1) if quoted_supply is not None else None
    tax_difference = (
        quoted_tax - expected_tax
        if quoted_tax is not None and expected_tax is not None
        else None
    )
    line_items_sum = sum(
        item.total_price or 0 for item in quote.line_items if item.total_price is not None
    )
    line_items_difference = (
        quoted_supply - line_items_sum
        if quoted_supply is not None and line_items_sum
        else None
    )

    status = "normal"
    messages: list[str] = []
    if quoted_total is None or quoted_tax is None:
        status = "not_enough_data"
    elif difference != 0:
        abs_diff = abs(difference or 0)
        relative_diff = abs_diff / quoted_total if quoted_total else 1
        line_items_ok = line_items_difference in (None, 0)
        tax_ok = tax_difference in (None, 0)
        if abs_diff <= 50_000 or (tax_ok and line_items_ok and (abs_diff <= 100_000 or relative_diff <= 0.005)):
            status = "rounding_or_adjustment_possible"
            messages.append(
                f"공급가+VAT와 견적서 총액이 {abs_diff:,}원 차이납니다. "
                "만원 단위 절사 또는 조정금액 가능성 확인 필요"
            )
        else:
            status = "amount_mismatch"
            messages.append(
                f"공급가+VAT와 견적서 총액이 {abs_diff:,}원 차이납니다. 금액 확인 필요"
            )

    if tax_difference not in (None, 0):
        abs_tax_diff = abs(tax_difference)
        if abs_tax_diff > max(10_000, int((expected_tax or 0) * 0.02)):
            status = "amount_mismatch" if status == "normal" else status
            messages.append(
                f"VAT가 공급가의 10%와 {abs_tax_diff:,}원 차이납니다. VAT 확인 필요"
            )

    if line_items_difference not in (None, 0):
        abs_line_diff = abs(line_items_difference)
        if abs_line_diff > max(10_000, int((quoted_supply or 0) * 0.03)):
            status = "amount_mismatch" if status == "normal" else status
            messages.append("line_items 합계와 공급가가 일치하지 않아 금액 확인 필요")

    return {
        "quoted_total_supply_price": quoted_supply,
        "quoted_tax_amount": quoted_tax,
        "quoted_total_with_vat": quoted_total,
        "calculated_total_with_vat": calculated_total,
        "difference": difference,
        "expected_tax_amount": expected_tax,
        "tax_difference": tax_difference,
        "line_items_sum": line_items_sum or None,
        "line_items_difference": line_items_difference,
        "validation_status": status,
        "auto_corrected": False,
        "message": " / ".join(_deduplicate(messages)) if messages else None,
    }


def build_delivery_validation(quote: QuoteDocument) -> dict[str, Any]:
    raw = (quote.delivery_basis_raw or "").strip()
    source = "delivery_basis_raw"
    if not raw:
        raw = _find_delivery_line(quote.notes_raw or "")
        source = "notes_raw" if raw else None

    normalized_weeks = normalize_delivery_weeks(raw)
    status = "normal"
    message = None
    if raw and DELIVERY_DISCUSSION_PATTERN.search(raw):
        normalized_weeks = None
        status = "discussion_required"
        message = "납기 별도협의"
    elif raw and normalized_weeks is None:
        status = "needs_review"
        message = "납기 원문은 있으나 주 단위 변환 확인 필요"
    elif not raw:
        status = "missing"
        message = "납기 정보 미기재"
    elif quote.delivery_weeks != normalized_weeks:
        status = "normalized"

    return {
        "raw": raw or None,
        "source": source,
        "llm_delivery_weeks": quote.delivery_weeks,
        "normalized_delivery_weeks": normalized_weeks,
        "normalizer_used": raw != "" and quote.delivery_weeks != normalized_weeks,
        "validation_status": status,
        "message": message,
    }


def apply_delivery_normalization(quote: QuoteDocument) -> dict[str, Any]:
    validation = build_delivery_validation(quote)
    raw = validation.get("raw")
    if raw and not quote.delivery_basis_raw:
        quote.delivery_basis_raw = str(raw)
    if validation["validation_status"] in {"normal", "normalized"}:
        quote.delivery_weeks = validation["normalized_delivery_weeks"]
    elif validation["validation_status"] == "discussion_required":
        quote.delivery_weeks = None
    return validation


def normalize_delivery_weeks(raw: str | None) -> int | None:
    if not raw:
        return None
    text = str(raw)
    if DELIVERY_DISCUSSION_PATTERN.search(text):
        return None
    week_match = DELIVERY_WEEK_PATTERN.search(text)
    if week_match:
        return int(week_match.group("weeks"))
    day_match = DELIVERY_DAY_PATTERN.search(text)
    if day_match:
        return ceil(int(day_match.group("days")) / 7)
    if re.fullmatch(r"\s*\d{1,3}\s*", text):
        return ceil(int(text.strip()) / 7)
    return None


def detect_multi_option(quote: QuoteDocument, *, source_text: str = "") -> dict[str, Any]:
    text = "\n".join([source_text or "", quote.notes_raw or ""])
    candidates = _find_option_total_candidates(text)
    product_groups = _line_item_product_groups(quote)
    option_markers = re.findall(
        r"(?:옵션\s*\d+|[1-9]\s*안|[A-Z]\s*안)",
        text,
        flags=re.IGNORECASE,
    )
    distinct_option_markers = {
        re.sub(r"\s+", "", marker).lower()
        for marker in option_markers
    }
    detail_section_count = len(re.findall(r"상세\s*내역", text, flags=re.IGNORECASE))
    is_multi = len(candidates) >= 2 and (
        detail_section_count >= 2
        or len(product_groups) >= 2
    )
    return {
        "is_multi_option_possible": bool(is_multi),
        "option_total_candidates": candidates[:5],
        "product_groups": sorted(product_groups),
        "option_marker_count": len(option_markers),
        "detail_section_count": detail_section_count,
        "auto_split": False,
    }


def normalize_line_item_category(item) -> dict[str, Any] | None:
    name_text = (item.name or "").lower()
    text = f"{item.name} {item.spec_raw}".lower()
    before = item.category
    after = before
    normalized_cost_type = None
    reason = None
    compact_name = re.sub(r"\s+", "", name_text)
    compact_all = re.sub(r"\s+", "", text)
    if any(token in compact_name for token in ["\uc608\ube44\ud488", "smps", "\uc218\uc2e0\uce74\ub4dc"]):
        normalized = "SYSTEM_EQUIPMENT" if "\uc218\uc2e0\uce74\ub4dc" in compact_name else "MATERIALS"
        category = LineItemCategory.PLAYER if normalized == "SYSTEM_EQUIPMENT" else LineItemCategory.CABLE
        return _apply_category_change(
            item,
            before=before,
            after=category,
            normalized_cost_type=normalized,
            reason="item_name accessory/material keyword",
        )
    if "\ubaa8\ub4c8" in compact_name and "\uc608\ube44\ud488" in compact_all:
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.CABLE,
            normalized_cost_type="MATERIALS",
            reason="item_name module spare material keyword",
        )
    if any(token in compact_name for token in ["\uae30\ud0c0\uacbd\ube44", "\uae30\ud0c0\ube44\uc6a9", "\uad00\ub9ac\ube44"]) and (
        "\uc124\uce58" in compact_all or "\uc2dc\uc6b4\uc804" in compact_all or "\uc2dc\uacf5" in compact_all
    ):
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.INSTALL,
            normalized_cost_type="INSTALL",
            reason="generic expense item with install evidence",
        )
    if "\uc124\uce58" in compact_name or "\uc2dc\uacf5" in compact_name or "\uc2dc\uc6b4\uc804" in compact_name:
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.INSTALL,
            normalized_cost_type="INSTALL",
            reason="item_name functional install keyword",
        )
    if "\uc138\ud305" in compact_name:
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.SOFTWARE,
            normalized_cost_type="SOFTWARE",
            reason="item_name functional software keyword",
        )
    if any(token in compact_name for token in ["\uc6b4\uc601pc", "\uc81c\uc5b4pc", "\ud504\ub85c\uc138\uc11c", "controller", "vx400pro"]):
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.PLAYER,
            normalized_cost_type="SYSTEM_EQUIPMENT",
            reason="item_name functional system equipment keyword",
        )
    functional_change = _normalize_functional_category_from_item_name(item, name_text, before)
    if functional_change is not None:
        return functional_change
    name_change = _normalize_category_from_item_name(item, name_text, before)
    if name_change is not None:
        return name_change
    priority_change = _normalize_priority_category_keywords(item, text, before)
    if priority_change is not None:
        return priority_change
    korean_change = _normalize_line_item_category_korean_keywords(item, text, before)
    if korean_change is not None:
        return korean_change

    if any(token in text for token in ["설치비", "설치 외", "제품 설치비", "system 설치", "시운전", "현장 설치"]):
        after = LineItemCategory.INSTALL
        normalized_cost_type = "INSTALL"
        reason = "installation keyword"
    elif "잡자재" in text and "설치 kit" in text:
        after = LineItemCategory.CABLE
        normalized_cost_type = "MATERIALS"
        reason = "material keyword"
    if _contains(text, ["출장", "체류비", "배송비", "화물운임", "운임", "교통", "숙박"]):
        after = LineItemCategory.ETC
        normalized_cost_type = "TRAVEL"
        reason = "travel keyword"
    elif _contains(text, ["cms", "콘텐츠제어", "스케줄", "소프트웨어", "라이선스", "license"]):
        after = LineItemCategory.SOFTWARE
        normalized_cost_type = "SOFTWARE"
        reason = "software keyword"
    elif _contains(
        text,
        ["플레이어 pc", "운영pc", "운영 pc", "제어 pc", "제어pc", " pc", "ds-dt", "vx400pro", "controller", "컨트롤러", "프로세서", "scaler", "player"],
    ):
        after = LineItemCategory.PLAYER
        normalized_cost_type = "SYSTEM_EQUIPMENT"
        reason = "player/controller keyword"
    elif _contains(
        text,
        ["브라켓", "bracket", "wall_basement", "베이스", "steel pipe", "마운트", "거치대", "벽부형", "제작형"],
    ):
        after = LineItemCategory.MOUNT
        normalized_cost_type = "MATERIALS"
        reason = "mount/material keyword"
    elif _contains(text, ["케이블", "잡자재", "기타 잡자재", "자재비", "부자재", "예비품", "smps", "수신카드"]):
        after = LineItemCategory.CABLE
        normalized_cost_type = "MATERIALS"
        reason = "cable/material keyword"
    elif _contains(
        text,
        [
            "led display",
            "led전광판",
            "전광판",
            "video wall",
            "비디오월",
            "lcd video wall",
            "did",
            "패널",
            "vw550r",
            "lh46",
            "lh55",
            "dp550",
            "모듈 본체",
            "디지털 사이니지",
        ],
    ):
        after = LineItemCategory.DISPLAY
        normalized_cost_type = "DISPLAY"
        reason = "display keyword"
    elif _contains(
        text,
        ["설치비", "설치", "시공", "system 설치", "시운전", "자재 운반", "인수인계", "현장설치"],
    ):
        after = LineItemCategory.INSTALL
        normalized_cost_type = "INSTALL"
        reason = "installation keyword"
    else:
        return None

    if any(token in (item.name or "").lower() for token in ["설치비", "설치 외", "제품 설치비"]):
        after = LineItemCategory.INSTALL
        normalized_cost_type = "INSTALL"
        reason = "installation keyword"

    if any(token in (item.name or "").lower() for token in ["설치비", "설치 외", "제품 설치비"]):
        after = LineItemCategory.INSTALL
        normalized_cost_type = "INSTALL"
        reason = "installation keyword"

    previous_cost_type = (item.spec_parsed or {}).get("normalized_cost_type")
    item.category = after
    item.spec_parsed = {
        **(item.spec_parsed or {}),
        "normalized_cost_type": normalized_cost_type,
    }
    if before == after and previous_cost_type == normalized_cost_type:
        return None
    return {
        "item_name": item.name,
        "before": before.value,
        "after": after.value,
        "normalized_cost_type": normalized_cost_type,
        "reason": reason,
    }


def _apply_category_change(
    item,
    *,
    before: LineItemCategory,
    after: LineItemCategory,
    normalized_cost_type: str,
    reason: str,
) -> dict[str, Any] | None:
    previous_cost_type = (item.spec_parsed or {}).get("normalized_cost_type")
    item.category = after
    item.spec_parsed = {**(item.spec_parsed or {}), "normalized_cost_type": normalized_cost_type}
    if before == after and previous_cost_type == normalized_cost_type:
        return None
    return {
        "item_name": item.name,
        "before": before.value,
        "after": after.value,
        "normalized_cost_type": normalized_cost_type,
        "reason": reason,
    }


def _normalize_functional_category_from_item_name(
    item,
    name_text: str,
    before: LineItemCategory,
) -> dict[str, Any] | None:
    compact = re.sub(r"\s+", "", name_text)
    if any(
        token in compact
        for token in [
            "설치",
            "시공",
            "장비설치",
            "비디오월설치",
            "전광판장비설치",
            "system설치",
            "시운전",
            "인수인계",
            "현장설치",
            "제품설치비",
        ]
    ):
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.INSTALL,
            normalized_cost_type="INSTALL",
            reason="item_name functional install keyword",
        )
    if any(token in compact for token in ["cms", "소프트웨어", "세팅", "콘텐츠제어", "스케줄", "해상도맞춤"]):
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.SOFTWARE,
            normalized_cost_type="SOFTWARE",
            reason="item_name functional software keyword",
        )
    if any(
        token in compact
        for token in [
            "controller",
            "컨트롤러",
            "프로세서",
            "novastar",
            "colorlight",
            "vx400pro",
            "운영pc",
            "제어pc",
            "플레이어pc",
        ]
    ):
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.PLAYER,
            normalized_cost_type="SYSTEM_EQUIPMENT",
            reason="item_name functional system equipment keyword",
        )
    if any(token in compact for token in ["브라켓", "bracket", "구조물", "wall_basement", "베이스"]):
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.MOUNT,
            normalized_cost_type="MATERIALS",
            reason="item_name functional mount keyword",
        )
    if any(token in compact for token in ["잡자재", "케이블", "배관", "배선"]):
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.CABLE,
            normalized_cost_type="MATERIALS",
            reason="item_name functional material keyword",
        )
    if any(token in compact for token in ["배송비", "화물운임", "운송", "출장", "체류비"]):
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.ETC,
            normalized_cost_type="TRAVEL",
            reason="item_name functional travel keyword",
        )
    if any(token in compact for token in ["유지보수", "유지관리"]):
        return _apply_category_change(
            item,
            before=before,
            after=LineItemCategory.ETC,
            normalized_cost_type="ETC",
            reason="item_name functional maintenance keyword",
        )
    return None


def _normalize_category_from_item_name(
    item,
    name_text: str,
    before: LineItemCategory,
) -> dict[str, Any] | None:
    mappings = [
        (["설치비", "설치 외", "제품 설치비", "system 설치", "시운전"], LineItemCategory.INSTALL, "INSTALL"),
        (["배송비", "화물운임", "출장", "체류비", "운송비용"], LineItemCategory.ETC, "TRAVEL"),
        (["cms", "콘텐츠제어", "스케줄", "소프트웨어"], LineItemCategory.SOFTWARE, "SOFTWARE"),
        (
            [
                "controller",
                "컨트롤러",
                "vx400pro",
                "novastar",
                "플레이어 pc",
                "운영pc",
                "제어 pc",
                "제어pc",
                "프로세서",
                "processor",
            ],
            LineItemCategory.PLAYER,
            "SYSTEM_EQUIPMENT",
        ),
        (["유지보수"], LineItemCategory.ETC, "ETC"),
        (["브라켓", "bracket", "wall_basement", "구조물", "베이스", "steel pipe"], LineItemCategory.MOUNT, "MATERIALS"),
        (["led screen", "led display", "led cabinet", "led 디스플레이", "비디오월", "video wall", "패널", "dled-c"], LineItemCategory.DISPLAY, "DISPLAY"),
    ]
    for keywords, after, normalized_cost_type in mappings:
        if not any(keyword in name_text for keyword in keywords):
            continue
        previous_cost_type = (item.spec_parsed or {}).get("normalized_cost_type")
        item.category = after
        item.spec_parsed = {**(item.spec_parsed or {}), "normalized_cost_type": normalized_cost_type}
        return {
            "item_name": item.name,
            "before": before.value,
            "after": after.value,
            "normalized_cost_type": normalized_cost_type,
            "reason": "item_name priority keyword",
        }
    if before == LineItemCategory.DISPLAY:
        item.spec_parsed = {**(item.spec_parsed or {}), "normalized_cost_type": "DISPLAY"}
        return {
            "item_name": item.name,
            "before": before.value,
            "after": before.value,
            "normalized_cost_type": "DISPLAY",
            "reason": "preserve existing display classification",
        }
    return None


def _normalize_priority_category_keywords(
    item,
    text: str,
    before: LineItemCategory,
) -> dict[str, Any] | None:
    after = before
    normalized_cost_type = None
    reason = None
    if any(token in text for token in ["설치비", "설치 외", "제품 설치비", "system 설치", "시운전", "현장 설치"]):
        after = LineItemCategory.INSTALL
        normalized_cost_type = "INSTALL"
        reason = "installation keyword"
    elif "잡자재" in text and "설치 kit" in text:
        after = LineItemCategory.CABLE
        normalized_cost_type = "MATERIALS"
        reason = "material keyword"
    elif any(token in text for token in ["dp-49br", "dp-55br", "dp-49 br", "dp-55 br"]):
        after = LineItemCategory.MOUNT
        normalized_cost_type = "MATERIALS"
        reason = "mount/material keyword"
    else:
        return None

    previous_cost_type = (item.spec_parsed or {}).get("normalized_cost_type")
    item.category = after
    item.spec_parsed = {
        **(item.spec_parsed or {}),
        "normalized_cost_type": normalized_cost_type,
    }
    if before == after and previous_cost_type == normalized_cost_type:
        return None
    return {
        "item_name": item.name,
        "before": before.value,
        "after": after.value,
        "normalized_cost_type": normalized_cost_type,
        "reason": reason,
    }


def _normalize_line_item_category_korean_keywords(
    item,
    text: str,
    before: LineItemCategory,
) -> dict[str, Any] | None:
    after = before
    normalized_cost_type = None
    reason = None

    if "잡자재" in text and "설치 kit" in text:
        after = LineItemCategory.CABLE
        normalized_cost_type = "MATERIALS"
        reason = "material keyword"
    elif any(token in text for token in ["dp-49br", "dp-55br", "dp-49 br", "dp-55 br"]):
        after = LineItemCategory.MOUNT
        normalized_cost_type = "MATERIALS"
        reason = "mount/material keyword"
    elif "설치 외" in text:
        after = LineItemCategory.INSTALL
        normalized_cost_type = "INSTALL"
        reason = "installation keyword"
    elif _contains(
        text,
        ["설치비", "설치", "시공", "system 설치", "시운전", "자재 운반", "인수인계", "현장설치"],
    ):
        after = LineItemCategory.INSTALL
        normalized_cost_type = "INSTALL"
        reason = "installation keyword"
    elif _contains(text, ["출장", "체류비", "배송비", "화물운임", "운임", "교통", "숙박"]):
        after = LineItemCategory.ETC
        normalized_cost_type = "TRAVEL"
        reason = "travel keyword"
    elif _contains(text, ["cms", "콘텐츠제어", "스케줄", "소프트웨어", "라이선스", "license"]):
        after = LineItemCategory.SOFTWARE
        normalized_cost_type = "SOFTWARE"
        reason = "software keyword"
    elif _contains(
        text,
        [
            "플레이어 pc",
            "운영pc",
            "운영 pc",
            "제어 pc",
            "제어pc",
            " pc",
            "ds-dt",
            "led용 제어 pc",
            "vx400pro",
            "controller",
            "컨트롤러",
            "프로세서",
            "scaler",
            "player",
            "all-in-one",
            "colorlight",
            "novastar",
        ],
    ):
        after = LineItemCategory.PLAYER
        normalized_cost_type = "SYSTEM_EQUIPMENT"
        reason = "player/controller keyword"
    elif _contains(
        text,
        ["브라켓", "bracket", "wall_basement", "베이스", "steel pipe", "마운트", "거치대", "벽부형", "제작형", "구조물"],
    ):
        after = LineItemCategory.MOUNT
        normalized_cost_type = "MATERIALS"
        reason = "mount/material keyword"
    elif _contains(text, ["케이블", "잡자재", "기타 잡자재", "자재비", "부자재", "예비품", "smps", "수신카드"]):
        after = LineItemCategory.CABLE
        normalized_cost_type = "MATERIALS"
        reason = "cable/material keyword"
    elif _contains(
        text,
        [
            "led display",
            "led전광판",
            "led 전광판",
            "video wall",
            "비디오월",
            "lcd video wall",
            "did",
            "패널",
            "vw550r",
            "lh46",
            "lh55",
            "dp550",
            "dp-49",
            "dp-55",
            "49vl",
            "55inch",
            "dled-c",
            "model : ds-d4015cw",
            "ds-d4015cw",
            "모듈 본체",
            "디지털 사이니지",
            "led screen",
            "led cabinet",
            "led 디스플레이",
        ],
    ):
        after = LineItemCategory.DISPLAY
        normalized_cost_type = "DISPLAY"
        reason = "display keyword"
    elif _contains(text, ["캐비닛 및 모듈", "모듈 면 평탄화"]):
        after = LineItemCategory.INSTALL
        normalized_cost_type = "INSTALL"
        reason = "installation keyword"
    elif _contains(text, ["관리비", "기업이윤"]):
        after = LineItemCategory.ETC
        normalized_cost_type = "ETC"
        reason = "etc keyword"
    else:
        return None

    previous_cost_type = (item.spec_parsed or {}).get("normalized_cost_type")
    item.category = after
    item.spec_parsed = {
        **(item.spec_parsed or {}),
        "normalized_cost_type": normalized_cost_type,
    }
    if before == after and previous_cost_type == normalized_cost_type:
        return None
    return {
        "item_name": item.name,
        "before": before.value,
        "after": after.value,
        "normalized_cost_type": normalized_cost_type,
        "reason": reason,
    }


def build_line_items_summary_warnings(quote: QuoteDocument) -> list[str]:
    warnings = []
    for item in quote.line_items:
        compact = " ".join([item.name, item.spec_raw]).strip().lower()
        if any(keyword in compact for keyword in SUMMARY_ROW_KEYWORDS):
            warnings.append(f"summary row may be included in line_items: {item.name}")
    return warnings


def _find_delivery_line(text: str) -> str | None:
    for line in text.splitlines():
        if any(keyword in line for keyword in ["납기", "Delivery", "delivery", "발주", "계약 후"]):
            return line.strip()
    return None


def _find_option_total_candidates(text: str) -> list[dict[str, Any]]:
    amounts = [
        int(match.group(0).replace(",", ""))
        for match in re.finditer(r"\d{1,3}(?:,\d{3})+", text)
    ]
    candidates = []
    seen = set()
    for idx in range(len(amounts) - 2):
        supply, tax, total = amounts[idx], amounts[idx + 1], amounts[idx + 2]
        if supply <= 0 or tax <= 0 or total <= 0:
            continue
        if supply < 100_000 or tax < 10_000 or total < 100_000:
            continue
        if abs((supply + tax) - total) > max(50_000, int(total * 0.03)):
            continue
        key = (supply, tax, total)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "label": _infer_option_label(text, supply),
                "supply_price": supply,
                "tax_amount": tax,
                "total_with_vat": total,
            }
        )
    return candidates


def _infer_option_label(text: str, amount: int) -> str | None:
    amount_text = f"{amount:,}"
    index = text.find(amount_text)
    if index < 0:
        return None
    window = text[max(0, index - 200):index]
    for label in ["LED전광판", "LED 전광판", "비디오월", "Video Wall", "LCD"]:
        if label.lower() in window.lower():
            return label
    option = re.search(r"(옵션\s*\d+|[1-9]\s*안|[A-Z]\s*안)", window, flags=re.IGNORECASE)
    return option.group(1) if option else None


def _line_item_product_groups(quote: QuoteDocument) -> set[str]:
    groups = set()
    for item in quote.line_items:
        text = f"{item.name} {item.spec_raw}".lower()
        if _contains(text, ["lh46", "lh55", "dp-49", "dp-55", "vw550r", "49vl", "55inch", "video wall"]):
            groups.add("비디오월")
        if _contains(text, ["led display", "led screen", "led cabinet", "pixel pitch", "cabinet", "dled-c", "ds-d4015cw"]):
            groups.add("LED전광판")
        if _contains(text, ["led", "led전광판", "led 전광판"]):
            groups.add("LED전광판")
        if _contains(text, ["비디오월", "video wall"]):
            groups.add("비디오월")
        if _contains(text, ["led", "전광판"]):
            groups.add("LED전광판")
        if _contains(text, ["비디오월", "video wall"]):
            groups.add("비디오월")
    return groups


def _contains(text: str, keywords: list[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _deduplicate(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if not value:
            continue
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result
