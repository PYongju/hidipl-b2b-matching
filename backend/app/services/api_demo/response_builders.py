from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Any

from services.api_demo.enums import CellStatus
from services.parser.schemas import LineItemCategory


def build_project_response(project_record) -> dict[str, Any]:
    result = project_record.requirement_result
    requirement = result.requirement
    return {
        "project_id": project_record.project_id,
        "request_id": project_record.request_id,
        "customer_name": requirement.customer_name,
        "request_summary": requirement.request_summary,
        "products": [safe_dataclass_to_dict(product) for product in requirement.products],
        "region": requirement.region,
        "install_schedule_text": requirement.install_schedule_text,
        "embedding_dim": result.embedding_dim,
        "parser_warnings": result.parser_warnings,
        "ingestion_warnings": result.ingestion_warnings,
    }


def build_quote_upload_response(project_id, quote_pool_record) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "quote_pool_id": quote_pool_record.quote_pool_id,
        "processed_count": len(quote_pool_record.quote_ingestion_results),
        "failed_files": quote_pool_record.failed_files,
        "quotes": [
            build_quote_summary(result)
            for result in quote_pool_record.quote_ingestion_results
        ],
    }


def build_quote_summary(result) -> dict[str, Any]:
    quote = result.quote
    return {
        "quote_id": result.quote_id,
        "vendor_name": quote.vendor_name,
        "project_name": quote.project_name,
        "total_supply_price": quote.total_supply_price,
        "total_with_vat": quote.total_with_vat,
        "delivery_weeks": quote.delivery_weeks,
        "delivery_basis_raw": quote.delivery_basis_raw,
        "warranty_months": quote.warranty_months,
        "line_item_count": len(quote.line_items),
        "line_items": build_line_item_summaries(quote.line_items),
        "embedding_dim": result.embedding_dim,
        "parser_warnings": result.parser_warnings,
        "ingestion_warnings": result.ingestion_warnings,
        "source_file_path": result.source_file_path,
        "vendor_snapshot": build_vendor_snapshot_summary(quote.vendor_snapshot),
    }


def build_recommendation_response(recommendation_result) -> dict[str, Any]:
    return {
        "top_n": recommendation_result.top_n,
        "items": [
            build_recommendation_item(item)
            for item in recommendation_result.items
        ],
        "all_items": [
            build_recommendation_item(item)
            for item in recommendation_result.all_items
        ],
        "failed_candidates": recommendation_result.failed_candidates,
        "filtered_candidates": recommendation_result.filtered_candidates,
        "metadata": recommendation_result.metadata,
    }


def build_recommendation_item(item) -> dict[str, Any]:
    return {
        "rank": item.rank,
        "quote_id": item.quote_id,
        "vendor_name": item.vendor_name,
        "project_name": item.project_name,
        "partner_name": item.partner_name,
        "final_score": item.final_score,
        "spec_score": item.spec_score,
        "price_score": item.price_score,
        "delivery_score": item.delivery_score,
        "warranty_score": item.warranty_score,
        "installation_score": item.installation_score,
        "cosine_similarity": item.cosine_similarity,
        "total_supply_price": item.total_supply_price,
        "total_with_vat": item.total_with_vat,
        "delivery_weeks": item.delivery_weeks,
        "delivery_basis_raw": item.delivery_basis_raw,
        "warranty_months": item.warranty_months,
        "installation_included": _quote_installation_included(item),
        "check_required": item.check_required,
        "rule_warnings": item.rule_warnings,
        "matched_rules": item.matched_rules,
        "partner_found": item.partner_found,
        "vendor_snapshot_source": item.vendor_snapshot_source,
        "vendor_snapshot": item.vendor_snapshot_summary,
        "score_breakdown": item.score_breakdown,
    }


def build_explanation_response(explanation_result) -> dict[str, Any]:
    return strip_heavy_fields(safe_dataclass_to_dict(explanation_result))


def build_compare_response(
    project_id: str,
    quote_results: list[Any],
    recommendation_result,
    quote_ids: list[str] | None = None,
    top_n: int | None = None,
) -> dict[str, Any]:
    score_map = {
        item.quote_id: item
        for item in (recommendation_result.all_items if recommendation_result else [])
    }
    selected_ids = set(quote_ids or [])

    if not selected_ids and top_n and recommendation_result:
        selected_ids = {
            item.quote_id
            for item in recommendation_result.items[:top_n]
        }

    rows = []
    for result in quote_results:
        quote = result.quote
        if selected_ids and result.quote_id not in selected_ids:
            continue

        score_item = score_map.get(result.quote_id)
        rows.append(_build_compare_row(result, score_item))

    _apply_compare_highlights(rows)

    return {
        "project_id": project_id,
        "rows": rows,
        "metadata": {
            "row_count": len(rows),
            "quote_ids": quote_ids or [],
            "top_n": top_n,
        },
    }


def build_vendor_snapshot_summary(vendor_snapshot) -> dict[str, Any] | None:
    if vendor_snapshot is None:
        return None
    return {
        "vendor_id": vendor_snapshot.vendor_id,
        "vendor_name": vendor_snapshot.vendor_name,
        "is_premium_partner": vendor_snapshot.is_premium_partner,
        "past_success_rate": vendor_snapshot.past_success_rate,
        "response_speed_score": vendor_snapshot.response_speed_score,
        "response_speed": vendor_snapshot.response_speed,
        "financial_status": vendor_snapshot.financial_status,
        "is_excluded": vendor_snapshot.is_excluded,
        "specialty_tags": vendor_snapshot.specialty_tags,
        "installation_count": vendor_snapshot.installation_count,
        "industry_breakdown": vendor_snapshot.industry_breakdown,
        "solution_breakdown": vendor_snapshot.solution_breakdown,
        "scale_breakdown": vendor_snapshot.scale_breakdown,
        "avg_projects_3yr": vendor_snapshot.avg_projects_3yr,
        "avg_revenue_3yr": vendor_snapshot.avg_revenue_3yr,
        "avg_revenue_3yr_million": vendor_snapshot.avg_revenue_3yr_million,
        "years_in_business": vendor_snapshot.years_in_business,
        "representative": vendor_snapshot.representative,
        "company_age_years": vendor_snapshot.company_age_years,
        "avg_project_count_3y": vendor_snapshot.avg_project_count_3y,
        "avg_revenue_3y_million": vendor_snapshot.avg_revenue_3y_million,
        "company_location": vendor_snapshot.company_location,
        "source": vendor_snapshot.source,
    }


def _build_compare_row(result, score_item) -> dict[str, Any]:
    quote = result.quote
    snapshot = quote.vendor_snapshot
    check_required = list(getattr(score_item, "check_required", []) or [])
    rule_warnings = list(getattr(score_item, "rule_warnings", []) or [])
    matched_rules = list(getattr(score_item, "matched_rules", []) or [])
    installation_included = _quote_document_installation_included(quote, score_item)

    row = {
        "quote_id": result.quote_id,
        "vendor_name": quote.vendor_name,
        "project_name": quote.project_name,
        "total_supply_price": quote.total_supply_price,
        "total_with_vat": quote.total_with_vat,
        "delivery_weeks": quote.delivery_weeks,
        "delivery_basis_raw": quote.delivery_basis_raw,
        "warranty_months": quote.warranty_months,
        "installation_included": installation_included,
        "line_item_count": len(quote.line_items),
        "final_score": getattr(score_item, "final_score", None),
        "spec_score": getattr(score_item, "spec_score", None),
        "price_score": getattr(score_item, "price_score", None),
        "delivery_score": getattr(score_item, "delivery_score", None),
        "warranty_score": getattr(score_item, "warranty_score", None),
        "installation_score": getattr(score_item, "installation_score", None),
        "check_required": check_required,
        "rule_warnings": rule_warnings,
        "matched_rules": matched_rules,
        "is_premium_partner": getattr(snapshot, "is_premium_partner", False),
        "past_success_rate": getattr(snapshot, "past_success_rate", None),
        "response_speed_score": getattr(snapshot, "response_speed_score", None),
        "financial_status": getattr(snapshot, "financial_status", None),
        "vendor_snapshot": build_vendor_snapshot_summary(snapshot),
    }
    row["company_info"] = _build_company_info(snapshot)
    row["hardware"] = _build_hardware_section(quote)
    row["cost_breakdown"] = _build_cost_breakdown(quote, check_required, rule_warnings)
    row["conditions"] = _build_conditions_section(
        quote,
        check_required=check_required,
        rule_warnings=rule_warnings,
        parser_warnings=getattr(result, "parser_warnings", []),
    )
    row["total"] = _build_total_section(quote, check_required)
    row["scores"] = _build_scores_section(score_item)
    row["highlights"] = {
        "is_lowest_total_price": False,
        "is_fastest_delivery": False,
        "is_longest_warranty": False,
        "is_highest_score": False,
    }
    return row


def _build_company_info(snapshot) -> dict[str, Any]:
    return {
        "company_age_years": getattr(snapshot, "company_age_years", None),
        "avg_revenue_3y_million": getattr(snapshot, "avg_revenue_3y_million", None),
        "avg_project_count_3y": getattr(snapshot, "avg_project_count_3y", None),
        "company_location": getattr(snapshot, "company_location", None),
        "representative": getattr(snapshot, "representative", None),
        "installation_count": getattr(snapshot, "installation_count", None),
        "industry_breakdown": getattr(snapshot, "industry_breakdown", {}) or {},
        "solution_breakdown": getattr(snapshot, "solution_breakdown", {}) or {},
        "scale_breakdown": getattr(snapshot, "scale_breakdown", {}) or {},
    }


def _build_hardware_section(quote) -> dict[str, Any]:
    item = _select_representative_hardware_item(quote.line_items)
    spec_raw = " ".join(
        value
        for value in [
            getattr(item, "spec_raw", "") if item else "",
            getattr(quote, "notes_raw", ""),
        ]
        if value
    )
    spec_parsed = getattr(item, "spec_parsed", {}) if item else {}
    item_name = getattr(item, "name", None) if item else None

    return {
        "screen_size_mm": (
            spec_parsed.get("full_screen_size_mm")
            or spec_parsed.get("panel_size_mm")
            or _extract_screen_size(spec_raw)
        ),
        "resolution": spec_parsed.get("resolution") or _extract_resolution(spec_raw),
        "type": spec_parsed.get("type") or item_name,
        "pixel_pitch": (
            spec_parsed.get("pitch_mm")
            or spec_parsed.get("pitch_max_mm")
            or _extract_pixel_pitch(spec_raw)
        ),
        "power_consumption_kw": _extract_power_kw(spec_raw),
        "brightness_cd_m2": (
            spec_parsed.get("brightness_nit")
            or _extract_brightness(spec_raw)
        ),
        "refresh_rate": _extract_refresh_rate(spec_raw),
        "free_maintenance_period": (
            f"{quote.warranty_months}개월" if quote.warranty_months else None
        ),
        "source_spec_raw_preview": spec_raw[:200] if spec_raw else None,
    }


def _select_representative_hardware_item(line_items):
    if not line_items:
        return None
    display_items = [
        item for item in line_items
        if item.category == LineItemCategory.DISPLAY
    ]
    if display_items:
        return max(display_items, key=lambda item: len(item.spec_raw or ""))
    hardware_keywords = ["led", "비디오월", "lcd", "display", "did", "모니터"]
    hardware_items = [
        item for item in line_items
        if any(keyword in (item.name or "").lower() for keyword in hardware_keywords)
    ]
    if hardware_items:
        return max(hardware_items, key=lambda item: len(item.spec_raw or ""))
    return max(line_items, key=lambda item: len(item.spec_raw or ""))


def _build_cost_breakdown(quote, check_required, rule_warnings) -> dict[str, Any]:
    breakdown = {
        "display_hw": _empty_cost_bucket(),
        "system_equipment": _empty_cost_bucket(),
        "installation": _empty_cost_bucket(),
        "materials": _empty_cost_bucket(),
        "travel_expense": _empty_cost_bucket(
            status=CellStatus.TO_BE_DISCUSSED.value
        ),
        "etc": _empty_cost_bucket(amount=0),
        "software": _empty_cost_bucket(amount=0),
        "content": _empty_cost_bucket(amount=0),
    }

    for item in quote.line_items:
        bucket_name = _cost_bucket_name(item)
        amount = _line_item_amount(item)
        bucket = breakdown[bucket_name]
        bucket["source_items"].append(
            {
                "name": item.name,
                "category": item.category.value if hasattr(item.category, "value") else item.category,
                "amount": amount,
            }
        )
        if amount is not None:
            bucket["amount"] = (bucket["amount"] or 0) + amount

    context = " ".join([quote.notes_raw, " ".join(check_required), " ".join(rule_warnings)])
    for name, bucket in breakdown.items():
        if bucket["amount"] and bucket["amount"] > 0:
            bucket["status"] = CellStatus.INCLUDED.value
        elif bucket["source_items"]:
            bucket["status"] = CellStatus.INCLUDED.value
        elif name in {"etc", "software", "content"}:
            bucket["status"] = CellStatus.MISSING.value
        if _bucket_marked_separate(name, context):
            bucket["status"] = CellStatus.SEPARATE.value
    return breakdown


def _empty_cost_bucket(
    amount=None,
    status: str = CellStatus.MISSING.value,
) -> dict[str, Any]:
    return {"amount": amount, "status": status, "source_items": []}


def _cost_bucket_name(item) -> str:
    text = f"{item.name} {item.spec_raw}".lower()
    if item.category == LineItemCategory.DISPLAY:
        return "display_hw"
    if item.category == LineItemCategory.PLAYER or any(
        keyword in text
        for keyword in ["processor", "controller", "scaler", "player", "송출", "제어기", "프로세서"]
    ):
        return "system_equipment"
    if item.category == LineItemCategory.INSTALL or any(
        keyword in text for keyword in ["설치", "시공", "시운전", "인수인계", "운반"]
    ):
        return "installation"
    if item.category in {LineItemCategory.CABLE, LineItemCategory.MOUNT} or any(
        keyword in text for keyword in ["케이블", "브라켓", "잡자재", "마운트", "거치대", "스틸", "보강대"]
    ):
        return "materials"
    if any(keyword in text for keyword in ["출장", "운임", "체류", "교통", "숙박"]):
        return "travel_expense"
    if item.category == LineItemCategory.SOFTWARE or any(
        keyword in text for keyword in ["software", "소프트웨어", "license", "라이선스", "cms"]
    ):
        return "software"
    if any(keyword in text for keyword in ["콘텐츠", "content", "디자인", "영상제작"]):
        return "content"
    return "etc"


def _line_item_amount(item) -> int | None:
    if item.total_price is not None:
        return item.total_price
    if item.unit_price is not None and item.quantity is not None:
        return int(item.unit_price * item.quantity)
    return None


def _bucket_marked_separate(bucket_name: str, context: str) -> bool:
    if "별도" not in context:
        return False
    keyword_map = {
        "installation": ["설치", "시공"],
        "travel_expense": ["출장", "운임", "교통", "숙박"],
        "software": ["소프트웨어", "라이선스", "cms"],
        "content": ["콘텐츠", "디자인", "영상"],
    }
    return any(keyword in context for keyword in keyword_map.get(bucket_name, []))


def _build_conditions_section(
    quote,
    *,
    check_required: list[str],
    rule_warnings: list[str],
    parser_warnings: list[str],
) -> dict[str, Any]:
    delivery = quote.delivery_basis_raw or (
        f"{quote.delivery_weeks}주" if quote.delivery_weeks else "미기재"
    )
    warranty_display = (
        f"{quote.warranty_months}개월" if quote.warranty_months else "미기재"
    )
    if quote.warranty_months and "출장실비" in " ".join(check_required + [quote.notes_raw]):
        warranty_display = f"{warranty_display}, 출장실비 별도"

    return {
        "delivery": delivery,
        "delivery_weeks": quote.delivery_weeks,
        "warranty_months": quote.warranty_months,
        "warranty_display": warranty_display,
        "as_method": _extract_as_method(quote.notes_raw),
        "install_location": getattr(quote.vendor_snapshot, "company_location", None),
        "special_notes": _compact_notes(
            [quote.notes_raw, *check_required, *rule_warnings, *parser_warnings]
        ),
    }


def _extract_as_method(text: str) -> str:
    if any(keyword in text for keyword in ["현장 방문", "방문 A/S", "출장"]):
        return "현장 방문"
    if any(keyword in text for keyword in ["택배", "입고", "센터"]):
        return "택배/입고 수리"
    return "미기재"


def _compact_notes(values: list[str]) -> list[str]:
    notes = []
    for value in values:
        if not value:
            continue
        for line in str(value).splitlines():
            line = line.strip(" -*\t")
            if line and line not in notes:
                notes.append(line[:200])
            if len(notes) >= 5:
                return notes
    return notes


def _build_total_section(quote, check_required) -> dict[str, Any]:
    is_confirmed = bool(quote.total_with_vat)
    if any("금액" in item or "가격" in item for item in check_required):
        is_confirmed = False
    if quote.total_with_vat:
        display_text = f"{quote.total_with_vat:,}원 (VAT 포함)"
    elif quote.total_supply_price:
        display_text = f"{quote.total_supply_price:,}원 (공급가)"
        is_confirmed = False
    else:
        display_text = "미확정"
        is_confirmed = False
    return {
        "total_supply_price": quote.total_supply_price,
        "total_with_vat": quote.total_with_vat,
        "is_confirmed": is_confirmed,
        "display_text": display_text,
    }


def _build_scores_section(score_item) -> dict[str, Any]:
    return {
        "final_score": getattr(score_item, "final_score", None),
        "spec_score": getattr(score_item, "spec_score", None),
        "price_score": getattr(score_item, "price_score", None),
        "delivery_score": getattr(score_item, "delivery_score", None),
        "warranty_score": getattr(score_item, "warranty_score", None),
        "installation_score": getattr(score_item, "installation_score", None),
        "cosine_similarity": getattr(score_item, "cosine_similarity", None),
    }


def _apply_compare_highlights(rows: list[dict[str, Any]]) -> None:
    confirmed_price_rows = [
        row for row in rows
        if row["total"]["is_confirmed"] and row.get("total_with_vat") is not None
    ]
    if confirmed_price_rows:
        lowest = min(row["total_with_vat"] for row in confirmed_price_rows)
        for row in confirmed_price_rows:
            row["highlights"]["is_lowest_total_price"] = row["total_with_vat"] == lowest

    delivery_rows = [row for row in rows if row.get("delivery_weeks") is not None]
    if delivery_rows:
        fastest = min(row["delivery_weeks"] for row in delivery_rows)
        for row in delivery_rows:
            row["highlights"]["is_fastest_delivery"] = row["delivery_weeks"] == fastest

    warranty_rows = [row for row in rows if row.get("warranty_months") is not None]
    if warranty_rows:
        longest = max(row["warranty_months"] for row in warranty_rows)
        for row in warranty_rows:
            row["highlights"]["is_longest_warranty"] = row["warranty_months"] == longest

    score_rows = [row for row in rows if row.get("final_score") is not None]
    if score_rows:
        highest = max(row["final_score"] for row in score_rows)
        for row in score_rows:
            row["highlights"]["is_highest_score"] = row["final_score"] == highest


def _quote_document_installation_included(quote, score_item=None) -> bool:
    if any(item.category == LineItemCategory.INSTALL for item in quote.line_items):
        return True
    score = getattr(score_item, "installation_score", None)
    return bool(score and score >= 80)


def _extract_screen_size(text: str) -> str | None:
    match = re.search(r"(\d{1,3}(?:,\d{3})?)\s*[xX×]\s*(\d{1,3}(?:,\d{3})?)\s*(?:mm)?", text)
    if not match:
        return None
    return f"{match.group(1)} x {match.group(2)}mm"


def _extract_resolution(text: str) -> str | None:
    for match in re.finditer(r"(\d{3,5})\s*[xX×]\s*(\d{3,5})\s*(?:pixels?|px)?", text):
        left = int(match.group(1).replace(",", ""))
        right = int(match.group(2).replace(",", ""))
        if left <= 10000 and right <= 10000:
            return f"{match.group(1)} x {match.group(2)}"
    return None


def _extract_pixel_pitch(text: str) -> float | None:
    match = re.search(r"(?:P|Pitch|pitch|피치)\s*[: ]?\s*(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1))
    return None


def _extract_power_kw(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(kW|kw|KW)", text)
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+(?:\.\d+)?)\s*W", text)
    if match:
        return round(float(match.group(1)) / 1000, 3)
    return None


def _extract_brightness(text: str) -> int | None:
    match = re.search(r"(\d{2,5})\s*(?:nit|cd/?m2|cd/㎡)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _extract_refresh_rate(text: str) -> str | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*Hz", text, re.IGNORECASE)
    if match:
        return f"{match.group(1)}Hz"
    return None


def build_line_item_summaries(line_items) -> list[dict[str, Any]]:
    summaries = []
    for item in line_items:
        summaries.append(
            {
                "name": item.name,
                "category": item.category.value if hasattr(item.category, "value") else item.category,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
                "is_optional": item.is_optional,
                "spec_raw": (item.spec_raw or "")[:300],
                "spec_parsed": item.spec_parsed,
                "extraction_confidence": item.extraction_confidence,
            }
        )
    return summaries


def _quote_installation_included(item) -> bool:
    return bool(item.installation_score and item.installation_score >= 80)


def safe_dataclass_to_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        return {
            key: safe_dataclass_to_dict(value)
            for key, value in asdict(obj).items()
        }
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {
            key: safe_dataclass_to_dict(value)
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [safe_dataclass_to_dict(value) for value in obj]
    return obj


def strip_heavy_fields(obj: Any) -> Any:
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key in {"embedding_vector", "raw", "raw_document", "binary_content"}:
                continue
            if key in {"source_text", "ocr_text"}:
                result[key] = str(value)[:1000]
                continue
            result[key] = strip_heavy_fields(value)
        return result
    if isinstance(obj, list):
        return [strip_heavy_fields(value) for value in obj]
    return safe_dataclass_to_dict(obj)
