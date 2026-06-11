from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Any

from services.api_demo.enums import CellStatus
from services.parser.schemas import LineItemCategory
from services.parser.rule_note_extractor import clean_special_notes
from services.explanation.explanation_text_policy import split_comparison_risks


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
    metadata = getattr(result, "metadata", {}) or {}
    summary = {
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
        "source_file_path": _safe_display_path(result.source_file_path),
        "vendor_snapshot": build_vendor_snapshot_summary(quote.vendor_snapshot),
    }
    if metadata.get("candidate_vendor_link") is not None:
        summary["candidate_vendor_link"] = metadata["candidate_vendor_link"]
    return summary


def build_candidate_vendors_response(project_id: str, candidate_vendor_record) -> dict[str, Any]:
    result = candidate_vendor_record.candidate_vendor_result
    requirement = getattr(candidate_vendor_record.requirement_result, "requirement", None)
    all_candidates = list(getattr(result, "all_candidates", []) or [])
    selected_candidates = [
        candidate for candidate in all_candidates if getattr(candidate, "business_rule_passed", False)
    ]
    filtered_candidates = [
        candidate for candidate in all_candidates if not getattr(candidate, "business_rule_passed", False)
    ]
    metadata = dict(getattr(result, "metadata", {}) or {})
    metadata.update(
        {
            "candidate_count": len(all_candidates),
            "selected_vendor_count": candidate_vendor_record.selected_vendor_count,
            "selected_count": len(selected_candidates),
            "not_selected_count": len(filtered_candidates),
            "executed_at": candidate_vendor_record.executed_at,
        }
    )
    metadata.pop("embedding_vector", None)

    return {
        "ok": True,
        "data": {
            "project_id": project_id,
            "request_id": result.request_id,
            "customer_name": result.customer_name
            or getattr(requirement, "customer_name", None),
            "top_n": candidate_vendor_record.top_n,
            "similarity_threshold": candidate_vendor_record.similarity_threshold,
            "selected_vendor_names": list(candidate_vendor_record.selected_vendor_names),
            "requested_vendor_names": list(candidate_vendor_record.requested_vendor_names),
            "candidate_vendors": [
                build_candidate_vendor_item(candidate, rank=index + 1)
                for index, candidate in enumerate(all_candidates)
            ],
            "filtered_vendors": [
                build_filtered_vendor_item(candidate)
                for candidate in filtered_candidates
            ],
            "metadata": strip_heavy_fields(metadata),
        },
        "error": None,
    }


def build_candidate_vendors_not_found_response(project_id: str) -> dict[str, Any]:
    return {
        "ok": False,
        "data": {
            "project_id": project_id,
            "candidate_vendors": [],
            "selected_vendor_names": [],
            "requested_vendor_names": [],
        },
        "error": "candidate vendors result not found",
    }


def _safe_display_path(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).replace("\\", "/").split("/")[-1]


def build_candidate_vendor_item(candidate, *, rank: int) -> dict[str, Any]:
    metadata = getattr(candidate, "metadata", {}) or {}
    return {
        "rank": getattr(candidate, "rank", None) or rank,
        "vendor_name": candidate.partner_name,
        "specialty_tags": list(candidate.specialty_tags),
        "semantic_similarity_score": candidate.semantic_similarity_score,
        "semantic_score_calibrated": getattr(candidate, "semantic_score_calibrated", None),
        "cosine_similarity": candidate.cosine_similarity,
        "final_score": getattr(candidate, "final_score", None),
        "score_breakdown": strip_heavy_fields(getattr(candidate, "score_breakdown", {}) or {}),
        "is_premium": candidate.is_premium,
        "success_rate": candidate.success_rate,
        "response_speed": candidate.response_speed,
        "financial_status": candidate.financial_status,
        "company_location": getattr(candidate, "company_location", None)
        or metadata.get("company_location"),
        "installation_count": getattr(candidate, "installation_count", None)
        if getattr(candidate, "installation_count", None) is not None
        else metadata.get("installation_count"),
        "business_rule_passed": candidate.business_rule_passed,
        "business_stage": candidate.business_stage,
        "filter_reasons": list(candidate.filter_reasons),
        "check_required": list(candidate.check_required),
    }


def build_filtered_vendor_item(candidate) -> dict[str, Any]:
    metadata = getattr(candidate, "metadata", {}) or {}
    return {
        "vendor_name": candidate.partner_name,
        "semantic_similarity_score": candidate.semantic_similarity_score,
        "business_rule_passed": candidate.business_rule_passed,
        "business_stage": candidate.business_stage,
        "filter_reasons": list(candidate.filter_reasons),
        "company_location": getattr(candidate, "company_location", None)
        or metadata.get("company_location"),
        "installation_count": getattr(candidate, "installation_count", None)
        if getattr(candidate, "installation_count", None) is not None
        else metadata.get("installation_count"),
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
        "comparison_risks": list(getattr(item, "comparison_risks", []) or []),
        "rule_warnings": item.rule_warnings,
        "matched_rules": item.matched_rules,
        "partner_found": item.partner_found,
        "business_rule_passed": item.business_rule_passed,
        "business_stage": item.business_stage,
        "filter_reasons": list(item.filter_reasons),
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
    project_install_location: str | None = None,
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
    elif not selected_ids and recommendation_result:
        selected_ids = {
            item.quote_id
            for item in recommendation_result.all_items
        }

    rows = []
    for result in quote_results:
        quote = result.quote
        if selected_ids and result.quote_id not in selected_ids:
            continue

        score_item = score_map.get(result.quote_id)
        rows.append(
            _build_compare_row(
                result,
                score_item,
                project_install_location=project_install_location,
            )
        )

    _apply_compare_highlights(rows)

    product_group_filter = (
        (getattr(recommendation_result, "metadata", {}) or {}).get("product_group_filter")
        if recommendation_result
        else None
    )
    product_group_excluded_candidates = (
        (getattr(recommendation_result, "metadata", {}) or {}).get(
            "product_group_excluded_candidates",
            [],
        )
        if recommendation_result
        else []
    )

    return {
        "project_id": project_id,
        "rows": rows,
        "metadata": {
            "row_count": len(rows),
            "quote_ids": quote_ids or [],
            "top_n": top_n,
            "product_group_filter": product_group_filter,
            "excluded_candidates": product_group_excluded_candidates,
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


def _build_compare_row(
    result,
    score_item,
    *,
    project_install_location: str | None = None,
) -> dict[str, Any]:
    quote = result.quote
    snapshot = quote.vendor_snapshot
    check_required = list(getattr(score_item, "check_required", []) or [])
    parser_check_required = list(
        (getattr(result, "metadata", {}) or {}).get("parser_check_required") or []
    )
    rule_warnings = list(getattr(score_item, "rule_warnings", []) or [])
    check_required, comparison_risks = split_comparison_risks(
        [*check_required, *parser_check_required],
        getattr(score_item, "comparison_risks", []) or [],
        rule_warnings,
    )
    matched_rules = list(getattr(score_item, "matched_rules", []) or [])
    installation_included = _quote_document_installation_included(quote, score_item)
    install_location = _resolve_install_location(
        result,
        project_install_location=project_install_location,
    )

    row = {
        "quote_id": result.quote_id,
        "vendor_name": quote.vendor_name,
        "candidate_vendor_link": (getattr(result, "metadata", {}) or {}).get(
            "candidate_vendor_link"
        ),
        "company_location": getattr(snapshot, "company_location", None),
        "install_location": install_location,
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
        "comparison_risks": comparison_risks,
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
        install_location=install_location,
        check_required=check_required,
        rule_warnings=rule_warnings,
        parser_warnings=getattr(result, "parser_warnings", []),
        parser_raw_matches=getattr(result, "parser_raw_matches", {}) or {},
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
    item_spec_raw = getattr(item, "spec_raw", "") if item else ""
    preview_source = _find_spec_preview_source(quote, item)
    spec_raw = " ".join(
        value
        for value in [
            item_spec_raw,
            preview_source,
            getattr(quote, "notes_raw", ""),
        ]
        if value
    )
    spec_parsed = getattr(item, "spec_parsed", {}) if item else {}
    item_name = getattr(item, "name", None) if item else None

    raw_hardware = {
        "screen_size_mm": (
            spec_parsed.get("screen_size_mm")
            or spec_parsed.get("full_screen_size_mm")
            or spec_parsed.get("total_dimensions_mm")
            or (
                None
                if spec_parsed.get("panel_size_mm")
                or spec_parsed.get("cabinet_size_mm")
                or spec_parsed.get("module_size_mm")
                else _extract_screen_size(spec_raw)
            )
        ),
        "resolution": (
            spec_parsed.get("resolution")
            or spec_parsed.get("resolution_type")
            or _extract_resolution(spec_raw)
        ),
        "type": _normalize_hardware_type(spec_parsed.get("type") or item_name),
        "pixel_pitch": (
            spec_parsed.get("pixel_pitch")
            or spec_parsed.get("pixel_pitch_mm")
            or spec_parsed.get("pitch_mm")
            or spec_parsed.get("pitch_max_mm")
            or _extract_pixel_pitch(spec_raw)
        ),
        "power_consumption_kw": (
            spec_parsed.get("power_consumption_kw")
            or _power_w_to_kw(spec_parsed.get("power_consumption_w"))
            or _extract_power_kw(spec_raw)
        ),
        "brightness_cd_m2": (
            spec_parsed.get("brightness_cd_m2")
            or spec_parsed.get("brightness_nit")
            or _extract_brightness(spec_raw)
        ),
        "refresh_rate": (
            spec_parsed.get("refresh_rate")
            or spec_parsed.get("refresh_rate_hz")
            or _extract_refresh_rate(spec_raw)
        ),
        "free_maintenance_period": (
            f"{quote.warranty_months}개월" if quote.warranty_months else None
        ),
        "source_spec_raw_preview": _clean_spec_preview(preview_source),
    }
    return _sanitize_hardware_section(raw_hardware, spec_parsed, spec_raw)


def _sanitize_hardware_section(
    hardware: dict[str, Any],
    spec_parsed: dict[str, Any],
    spec_raw: str,
) -> dict[str, Any]:
    evidence = spec_parsed.get("_evidence") or {}
    screen = _dimension_pair(hardware.get("screen_size_mm"))
    if screen and (screen[0] < 1000 or screen[1] < 500):
        hardware["screen_size_mm"] = None
    if not evidence.get("screen_size_mm") and not evidence.get("full_screen_size_mm"):
        if any(spec_parsed.get(key) == hardware.get("screen_size_mm") for key in ["panel_size_mm", "cabinet_size_mm", "module_size_mm"]):
            hardware["screen_size_mm"] = None

    resolution = _dimension_pair(hardware.get("resolution"))
    if resolution and (
        resolution in {(600.0, 400.0), (300.0, 168.0)}
        or resolution[0] < 640
        or resolution[1] < 480
    ):
        hardware["resolution"] = None
    if any(spec_parsed.get(key) == hardware.get("resolution") for key in ["cabinet_resolution", "module_resolution", "panel_size_mm"]):
        hardware["resolution"] = None

    pitch = _as_float(hardware.get("pixel_pitch"))
    hardware["pixel_pitch"] = pitch if pitch is not None and 0.5 <= pitch <= 20 else None
    brightness = _as_float(hardware.get("brightness_cd_m2"))
    hardware["brightness_cd_m2"] = int(brightness) if brightness is not None and 100 <= brightness <= 5000 else None
    refresh = _as_float(str(hardware.get("refresh_rate") or "").replace("Hz", ""))
    hardware["refresh_rate"] = int(refresh) if refresh is not None and 30 <= refresh <= 10000 else None
    power = _as_float(hardware.get("power_consumption_kw"))
    hardware["power_consumption_kw"] = power if power is not None and 0 < power <= 1000 else None
    return hardware


def _clean_spec_preview(value: str | None) -> str | None:
    if not value:
        return None
    lines = []
    for raw_line in str(value).splitlines():
        line = re.sub(r":?unselected:?", " ", raw_line, flags=re.IGNORECASE)
        line = re.sub(r"(?:\|\s*){2,}", " | ", line)
        line = re.sub(r"\s+", " ", line).strip(" |")
        line = _trim_preview_at_inline_row_marker(line)
        if "|" in line:
            segments = [
                segment.strip()
                for segment in line.split("|")
                if segment.strip()
            ]
            kept = []
            for segment in segments:
                if re.search(r"(?:₩|￦|\\)\s*\d|(?:\d{1,3},){1,3}\d{3}", segment):
                    break
                if _has_spec_keyword(segment) or _looks_like_model_preview(segment):
                    kept.append(segment)
            if kept:
                line = " | ".join(kept)
        if not line:
            continue
        has_money = bool(re.search(r"(?:₩|￦|\\)\s*\d|(?:\d{1,3},){1,3}\d{3}", line))
        has_summary = bool(re.search(r"(?:합계|소계|공급가|부가세|부가가치세|총금액|전체\s*합계|VAT)", line, re.IGNORECASE))
        if has_money and has_summary:
            continue
        has_spec_hint = _has_spec_keyword(line) or _looks_like_model_preview(line)
        if has_money and not has_spec_hint:
            continue
        if not has_spec_hint:
            continue
        lines.append(line)
    preview = " ".join(lines)
    preview = re.sub(r"\s*\|\s*(?:\|\s*)+", " | ", preview)
    preview = re.sub(r"\s+", " ", preview).strip(" |")
    return preview[:300] if preview else None


def _find_spec_preview_source(quote, representative_item) -> str | None:
    candidates = []
    if representative_item is not None:
        candidates.append(getattr(representative_item, "spec_raw", "") or "")
    for item in getattr(quote, "line_items", []) or []:
        spec_raw = getattr(item, "spec_raw", "") or ""
        if not spec_raw:
            continue
        if item is representative_item:
            continue
        spec = getattr(item, "spec_parsed", {}) or {}
        category = getattr(item, "category", None)
        normalized = str(spec.get("normalized_cost_type") or "").upper()
        if category == LineItemCategory.DISPLAY or normalized == "DISPLAY" or _has_spec_keyword(spec_raw):
            candidates.append(spec_raw)
    notes_raw = getattr(quote, "notes_raw", "") or ""
    if notes_raw and _has_spec_keyword(notes_raw):
        candidates.append(notes_raw)
    for value in candidates:
        if _clean_spec_preview(value):
            return value
    return None


def _trim_preview_at_inline_row_marker(line: str) -> str:
    parts = re.split(
        r"\s+\d{1,2}\s+(?=(?:All-in-one|브라켓|설치비|제품\s*설치비|예비품|SMPS|수신카드|충북|[A-Z]{2,}[-_]))",
        line,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    return parts[0].strip()


def _looks_like_model_preview(value: str | None) -> bool:
    if not value:
        return False
    text = str(value)
    if len(text) > 120:
        return False
    if re.search(r"\b[A-Z]{1,5}[-_]?\d{2,}[A-Z0-9._-]*\b", text):
        return True
    if re.search(r"\b\d{2}\s*(?:inch|인치|\"|”)", text, re.IGNORECASE):
        return True
    return False


def _has_spec_keyword(value: str | None) -> bool:
    if not value:
        return False
    text = str(value).lower()
    keywords = [
        "해상도",
        "제안해상도",
        "화면사이즈",
        "스크린",
        "screen",
        "display size",
        "전체 크기",
        "전체화면",
        "pixel pitch",
        "led pitch",
        "pitch",
        "밝기",
        "nit",
        "cd",
        "bezel",
        "베젤",
        "refresh",
        "hz",
        "전기용량",
        "최대전력",
        "최대소비전력",
        "소비전력",
        "kw",
        "cabinet",
        "module",
        "fhd",
        "uhd",
        "4k",
    ]
    return any(keyword in text for keyword in keywords)


def _dimension_pair(value: Any) -> tuple[float, float] | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)", str(value).replace(",", ""))
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _select_representative_hardware_item(line_items):
    if not line_items:
        return None
    line_items = [
        item for item in line_items
        if not (getattr(item, "spec_parsed", {}) or {}).get("reconciliation_residual")
    ]
    if not line_items:
        return None
    display_items = [
        item for item in line_items
        if item.category == LineItemCategory.DISPLAY
    ]
    if display_items:
        filtered = [item for item in display_items if not _is_bad_hardware_candidate(item)]
        if filtered:
            return max(filtered, key=_hardware_candidate_score)
        return None
    hardware_keywords = ["led", "비디오월", "lcd", "display", "did", "모니터", "패널", "전광판"]
    hardware_items = [
        item for item in line_items
        if any(keyword in (item.name or "").lower() for keyword in hardware_keywords)
    ]
    if hardware_items:
        filtered = [item for item in hardware_items if not _is_bad_hardware_candidate(item)]
        if filtered:
            return max(filtered, key=_hardware_candidate_score)
    return None


def _is_bad_hardware_candidate(item) -> bool:
    text = (getattr(item, "name", "") or "").lower()
    return any(
        token in text
        for token in [
            "예비품",
            "유지보수",
            "세팅",
            "설치",
            "pc",
            "controller",
            "컨트롤러",
            "프로세서",
            "브라켓",
            "잡자재",
            "잔액",
            "미파싱",
        ]
    )


def _hardware_candidate_score(item) -> tuple[int, int, int]:
    spec = getattr(item, "spec_parsed", {}) or {}
    spec_score = sum(
        1
        for key in ["screen_size_mm", "full_screen_size_mm", "resolution", "pixel_pitch_mm", "brightness_cd_m2", "brightness_nit"]
        if spec.get(key)
    )
    amount = getattr(item, "total_price", None) or 0
    return (spec_score, int(amount), len(getattr(item, "spec_raw", "") or ""))


def _normalize_hardware_type(value: str | None) -> str | None:
    if not value:
        return None
    if value.upper().startswith("DLED-C"):
        return "DLED-C"
    return value


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
    name_text = (item.name or "").lower()
    normalized_cost_type = str((item.spec_parsed or {}).get("normalized_cost_type") or "").upper()
    functional_bucket = _functional_cost_bucket_from_item_name(name_text)
    if functional_bucket:
        return functional_bucket
    if normalized_cost_type == "DISPLAY" or item.category == LineItemCategory.DISPLAY:
        return "display_hw"
    if normalized_cost_type == "TRAVEL":
        return "travel_expense"
    if normalized_cost_type == "SOFTWARE":
        return "software"
    if normalized_cost_type == "SYSTEM_EQUIPMENT":
        return "system_equipment"
    if normalized_cost_type == "MATERIALS":
        return "materials"
    if any(keyword in text for keyword in ["예비품", "smps", "수신카드", "spare"]):
        return "materials"
    if normalized_cost_type == "INSTALL":
        return "installation"
    if any(keyword in text for keyword in ["출장", "운임", "화물운임", "배송비", "체류", "체류비", "교통", "숙박"]):
        return "travel_expense"
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
    if item.category == LineItemCategory.SOFTWARE or any(
        keyword in text for keyword in ["software", "소프트웨어", "license", "라이선스", "cms"]
    ):
        return "software"
    if any(keyword in text for keyword in ["콘텐츠", "content", "디자인", "영상제작"]):
        return "content"
    return "etc"


def _functional_cost_bucket_from_item_name(name_text: str) -> str | None:
    compact = re.sub(r"\s+", "", name_text)
    if any(token in compact for token in ["설치", "시공", "장비설치", "비디오월설치", "전광판장비설치", "system설치", "시운전", "인수인계"]):
        return "installation"
    if any(token in compact for token in ["배송비", "화물운임", "운송", "출장", "체류비"]):
        return "travel_expense"
    if any(token in compact for token in ["cms", "소프트웨어", "세팅", "콘텐츠제어", "스케줄", "해상도맞춤"]):
        return "software"
    if any(token in compact for token in ["controller", "컨트롤러", "프로세서", "novastar", "colorlight", "vx400pro", "운영pc", "제어pc", "플레이어pc"]):
        return "system_equipment"
    if any(token in compact for token in ["브라켓", "bracket", "구조물", "wall_basement", "베이스", "잡자재", "케이블", "배관", "배선"]):
        return "materials"
    return None


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
        "travel_expense": ["출장", "운임", "화물운임", "배송비", "체류", "체류비", "교통", "숙박"],
        "software": ["소프트웨어", "라이선스", "cms"],
        "content": ["콘텐츠", "디자인", "영상"],
    }
    return any(keyword in context for keyword in keyword_map.get(bucket_name, []))


def _build_conditions_section(
    quote,
    *,
    install_location: str | None,
    check_required: list[str],
    rule_warnings: list[str],
    parser_warnings: list[str],
    parser_raw_matches: dict[str, Any] | None = None,
) -> dict[str, Any]:
    delivery = quote.delivery_basis_raw or (
        f"{quote.delivery_weeks}주" if quote.delivery_weeks else "미기재"
    )
    warranty_display = (
        f"{quote.warranty_months}개월" if quote.warranty_months else "미기재"
    )
    if quote.warranty_months and "출장실비" in " ".join(check_required + [quote.notes_raw]):
        warranty_display = f"{warranty_display}, 출장실비 별도"

    parser_raw_matches = parser_raw_matches or {}
    payment_terms = parser_raw_matches.get("payment_terms")
    special_notes = clean_special_notes(
        [
            *(parser_raw_matches.get("special_notes") or []),
            *check_required,
            *[
                warning
                for warning in rule_warnings
                if not split_comparison_risks([], [], [warning])[1]
            ],
        ],
        payment_terms=payment_terms,
    )
    return {
        "delivery": delivery,
        "delivery_weeks": quote.delivery_weeks,
        "payment_terms": payment_terms,
        "warranty_months": quote.warranty_months,
        "warranty_display": warranty_display,
        "as_method": _extract_as_method(quote.notes_raw),
        "install_location": install_location,
        "special_notes": special_notes[:10],
    }


def _resolve_install_location(
    result,
    *,
    project_install_location: str | None = None,
) -> str | None:
    return _clean_location_value(project_install_location)


def _clean_location_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in {"", "미입력", "없음", "null", "undefined", "none"}:
        return None
    return text or None


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
    install_keywords = [
        "설치",
        "시공",
        "system 설치",
        "시운전",
        "장비 설치",
        "제품 설치비",
        "비디오월 설치",
        "전광판 장비 설치",
        "인수인계",
    ]
    for item in quote.line_items:
        spec = getattr(item, "spec_parsed", {}) or {}
        text = f"{getattr(item, 'name', '')} {getattr(item, 'spec_raw', '')}".lower()
        amount = _line_item_amount(item)
        if amount is not None and amount <= 0:
            continue
        if item.category == LineItemCategory.INSTALL:
            return True
        if str(spec.get("normalized_cost_type") or "").upper() == "INSTALL":
            return True
        if any(keyword in text for keyword in install_keywords):
            return True
    score = getattr(score_item, "installation_score", None)
    return bool(score and score >= 80)


def _extract_screen_size(text: str) -> str | None:
    match = re.search(
        r"(?:전체화면\s*크기|스크린\s*크기|display\s*size|제안사이즈|화면사이즈)[^0-9]{0,80}"
        r"(?:가로\s*[:：]?\s*|\(W\)\s*)?(\d{2,5}(?:,\d{3})?(?:\.\d+)?)\s*(?:mm\s*)?[xX×]\s*"
        r"(?:세로\s*[:：]?\s*|\(H\)\s*)?(\d{2,5}(?:,\d{3})?(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return f"{match.group(1).replace(',', '')} x {match.group(2).replace(',', '')}"


def _extract_resolution(text: str) -> str | None:
    for match in re.finditer(r"(?:전체화면\s*해상도|제안해상도|해상도|resolution)[^0-9]{0,80}(\d{3,5})\s*[xX×]\s*(\d{3,5})\s*(?:pixels?|px)?", text, re.IGNORECASE):
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
    match = re.search(r"(\d+(?:\.\d+)?)\s*kW\b", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+(?:\.\d+)?)\s*W\b", text, re.IGNORECASE)
    if match:
        return round(float(match.group(1)) / 1000, 3)
    return None


def _power_w_to_kw(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(value) / 1000, 3)
    except (TypeError, ValueError):
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
            if key in {
                "embedding_vector",
                "requirement_embedding",
                "partner_embedding",
                "raw",
                "raw_document",
                "binary_content",
                "api_key",
                "endpoint",
                "deployment",
            }:
                continue
            if key in {"source_text", "ocr_text"}:
                result[key] = str(value)[:1000]
                continue
            result[key] = strip_heavy_fields(value)
        return result
    if isinstance(obj, list):
        return [strip_heavy_fields(value) for value in obj]
    return safe_dataclass_to_dict(obj)
