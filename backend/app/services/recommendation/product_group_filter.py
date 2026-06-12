from __future__ import annotations

from collections import Counter
from typing import Any

from services.parser.schemas import QuoteDocument
from services.quote_ingestion.schemas import QuoteIngestionResult
from services.requirement.schemas import RequirementInfo


PRODUCT_GROUP_SYNONYMS = {
    "LED전광판": {
        "LED전광판",
        "LED 전광판",
        "전광판",
        "LED Display",
        "LED 디스플레이",
        "LED Screen",
        "실내용 LED",
    },
    "비디오월": {
        "비디오월",
        "Video Wall",
        "멀티비전",
        "멀티비젼",
        "46인치 비디오월",
        "49인치 비디오월",
        "55인치 비디오월",
    },
    "사이니지": {
        "사이니지",
        "디지털사이니지",
        "디지털 사이니지",
        "Signage",
    },
    "투명디스플레이": {
        "투명디스플레이",
        "투명 OLED",
        "투명LED",
    },
    "키오스크": {
        "키오스크",
        "KIOSK",
    },
}
PRODUCT_GROUP_ORDER = [
    "투명디스플레이",
    "비디오월",
    "LED전광판",
    "사이니지",
    "키오스크",
]
GENERIC_DISPLAY_KEYWORDS = {"디스플레이", "display", "DID"}


def resolve_requirement_product_groups(requirement: RequirementInfo) -> set[str]:
    values: list[Any] = [
        getattr(requirement, "category", None),
        getattr(requirement, "request_summary", None),
        *list(getattr(requirement, "required_keywords", []) or []),
    ]
    metadata = getattr(requirement, "metadata", {}) or {}
    frontend_fields = metadata.get("frontend_fields") or {}
    values.extend(
        [
            frontend_fields.get("카테고리"),
            frontend_fields.get("디스플레이 크기"),
            frontend_fields.get("추가 요청사항"),
        ]
    )
    for product in getattr(requirement, "products", []) or []:
        values.extend(
            [
                getattr(product, "product_type", None),
                getattr(product, "display_type", None),
                getattr(product, "name", None),
                getattr(product, "raw_text", None),
            ]
        )
    return _resolve_product_groups_from_values(values, include_generic_display=False)


def resolve_quote_product_groups(quote_or_result: QuoteDocument | QuoteIngestionResult) -> set[str]:
    result = quote_or_result if isinstance(quote_or_result, QuoteIngestionResult) else None
    quote = result.quote if result is not None else quote_or_result
    values: list[Any] = []
    if result is not None:
        metadata = result.metadata or {}
        raw_matches = result.parser_raw_matches or {}
        split_meta = raw_matches.get("multi_option_split") or {}
        detection = raw_matches.get("multi_option_detection") or {}
        direct_values = [
            metadata.get("option_label"),
            metadata.get("product_group"),
            split_meta.get("option_label"),
        ]
        direct_values.extend(_as_list(metadata.get("product_groups")))
        direct_groups = _resolve_product_groups_from_values(
            direct_values,
            include_generic_display=False,
        )
        if direct_groups:
            return direct_groups
        values.extend(
            [
                metadata.get("option_label"),
                metadata.get("product_group"),
                split_meta.get("option_label"),
            ]
        )
        values.extend(_as_list(metadata.get("product_groups")))
        values.extend(_as_list(detection.get("product_groups")))

    values.append(getattr(quote, "project_name", None))
    for item in getattr(quote, "line_items", []) or []:
        values.extend(
            [
                getattr(item, "name", None),
                getattr(item, "spec_raw", None),
                (getattr(item, "spec_parsed", {}) or {}).get("hardware_type"),
            ]
        )
    return _resolve_product_groups_from_values(values, include_generic_display=False)


def infer_dominant_quote_product_groups(
    quote_documents: list[QuoteIngestionResult],
) -> dict[str, Any]:
    quote_group_map = _quote_product_group_map(quote_documents)
    counts = Counter()
    for groups in quote_group_map.values():
        for group in groups:
            counts[group] += 1

    sorted_counts = counts.most_common()
    selected: set[str] = set()
    selection_required = False
    reason = None
    if sorted_counts:
        top_group, top_count = sorted_counts[0]
        second_count = sorted_counts[1][1] if len(sorted_counts) > 1 else 0
        known_count = sum(counts.values())
        if top_count >= 2 and top_count > second_count:
            selected = {top_group}
        elif known_count and top_count / known_count >= 0.6 and top_count > second_count:
            selected = {top_group}
        else:
            selection_required = True
            reason = "비교 제품군을 자동 결정할 수 없음"
    else:
        selection_required = True
        reason = "비교 제품군 정보가 없습니다."

    return {
        "selected_product_groups": sorted(selected),
        "quote_product_group_counts": dict(sorted(counts.items())),
        "quote_product_groups_by_quote_id": {
            quote_id: sorted(groups) for quote_id, groups in quote_group_map.items()
        },
        "selection_required": selection_required,
        "reason": reason,
    }


def filter_quotes_by_product_group_scope(
    requirement: RequirementInfo,
    quote_documents: list[QuoteIngestionResult],
) -> tuple[list[QuoteIngestionResult], list[dict[str, Any]], dict[str, Any]]:
    requirement_groups = resolve_requirement_product_groups(requirement)
    dominant = infer_dominant_quote_product_groups(quote_documents)
    quote_counts = dominant["quote_product_group_counts"]
    quote_group_map = dominant["quote_product_groups_by_quote_id"]

    if requirement_groups:
        selected_groups = set(requirement_groups)
        source = "requirement"
        selection_required = False
        reason = None
    else:
        selected_groups = set(dominant["selected_product_groups"])
        source = "quote_pool_dominant_group" if selected_groups else "quote_pool_ambiguous"
        selection_required = bool(dominant["selection_required"])
        reason = dominant.get("reason")

    metadata: dict[str, Any] = {
        "enabled": bool(selected_groups),
        "source": source,
        "selected_product_groups": sorted(selected_groups),
        "requirement_product_groups": sorted(requirement_groups),
        "quote_product_group_counts": quote_counts,
        "quote_product_groups_by_quote_id": quote_group_map,
        "input_quote_count": len(quote_documents),
        "selection_required": selection_required,
        "fallback_used": False,
    }
    if reason:
        metadata["reason"] = reason

    if not selected_groups:
        metadata.update(
            {
                "ranking_quote_count": len(quote_documents),
                "excluded_quote_count": 0,
            }
        )
        return list(quote_documents), [], metadata

    included: list[QuoteIngestionResult] = []
    excluded: list[dict[str, Any]] = []
    uncertain_quote_ids: list[str] = []
    for quote_result in quote_documents:
        quote_groups = resolve_quote_product_groups(quote_result)
        if not quote_groups:
            included.append(quote_result)
            uncertain_quote_ids.append(quote_result.quote_id or quote_result.quote.quote_id)
            continue
        if quote_groups & selected_groups:
            included.append(quote_result)
            continue
        excluded.append(
            _build_excluded_candidate(
                quote_result,
                selected_groups=selected_groups,
                quote_groups=quote_groups,
                source=source,
            )
        )

    if not included:
        metadata.update(
            {
                "enabled": False,
                "fallback_used": True,
                "warning": "No quotes matched product group scope; ranking all quotes.",
                "ranking_quote_count": len(quote_documents),
                "excluded_quote_count": 0,
            }
        )
        return list(quote_documents), [], metadata

    metadata.update(
        {
            "ranking_quote_count": len(included),
            "excluded_quote_count": len(excluded),
            "uncertain_quote_ids": [quote_id for quote_id in uncertain_quote_ids if quote_id],
        }
    )
    return included, excluded, metadata


def _quote_product_group_map(
    quote_documents: list[QuoteIngestionResult],
) -> dict[str, set[str]]:
    result = {}
    for quote_result in quote_documents:
        quote_id = quote_result.quote_id or quote_result.quote.quote_id
        result[quote_id] = resolve_quote_product_groups(quote_result)
    return result


def _build_excluded_candidate(
    quote_result: QuoteIngestionResult,
    *,
    selected_groups: set[str],
    quote_groups: set[str],
    source: str,
) -> dict[str, Any]:
    metadata = quote_result.metadata or {}
    split_from_multi_option = bool(metadata.get("split_from_multi_option"))
    reason = (
        "동일 PDF 내 복수 제품군 옵션 중 비교 scope와 다른 제품군"
        if split_from_multi_option
        else "다른 업로드 견적서의 주요 제품군과 불일치"
    )
    if source == "requirement":
        reason = "고객 요구사항의 비교 제품군과 불일치"
    return {
        "quote_id": quote_result.quote_id or quote_result.quote.quote_id,
        "vendor_name": quote_result.quote.vendor_name,
        "project_name": quote_result.quote.project_name,
        "selected_product_groups": sorted(selected_groups),
        "quote_product_groups": sorted(quote_groups),
        "split_from_multi_option": split_from_multi_option,
        "parent_quote_id": metadata.get("parent_quote_id"),
        "option_label": metadata.get("option_label"),
        "reason": reason,
        "filter_type": "product_group_scope_mismatch",
    }


def _resolve_product_groups_from_values(
    values: list[Any],
    *,
    include_generic_display: bool,
) -> set[str]:
    groups = set()
    for value in values:
        group = _canonical_product_group(value, include_generic_display=include_generic_display)
        if group:
            groups.add(group)
    return groups


def _canonical_product_group(value: Any, *, include_generic_display: bool) -> str | None:
    text = str(value or "").lower().replace(" ", "")
    if not text:
        return None
    for canonical in PRODUCT_GROUP_ORDER:
        for synonym in PRODUCT_GROUP_SYNONYMS[canonical]:
            if synonym.lower().replace(" ", "") in text:
                return canonical
    if include_generic_display and any(
        keyword.lower().replace(" ", "") in text for keyword in GENERIC_DISPLAY_KEYWORDS
    ):
        return "디스플레이"
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]
