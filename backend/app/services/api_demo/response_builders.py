from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

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
        snapshot = quote.vendor_snapshot
        rows.append(
            {
                "quote_id": result.quote_id,
                "vendor_name": quote.vendor_name,
                "project_name": quote.project_name,
                "total_supply_price": quote.total_supply_price,
                "total_with_vat": quote.total_with_vat,
                "delivery_weeks": quote.delivery_weeks,
                "delivery_basis_raw": quote.delivery_basis_raw,
                "warranty_months": quote.warranty_months,
                "installation_included": any(
                    item.category == LineItemCategory.INSTALL
                    for item in quote.line_items
                ),
                "line_item_count": len(quote.line_items),
                "final_score": getattr(score_item, "final_score", None),
                "spec_score": getattr(score_item, "spec_score", None),
                "price_score": getattr(score_item, "price_score", None),
                "delivery_score": getattr(score_item, "delivery_score", None),
                "warranty_score": getattr(score_item, "warranty_score", None),
                "installation_score": getattr(score_item, "installation_score", None),
                "check_required": getattr(score_item, "check_required", []),
                "rule_warnings": getattr(score_item, "rule_warnings", []),
                "matched_rules": getattr(score_item, "matched_rules", []),
                "is_premium_partner": getattr(snapshot, "is_premium_partner", False),
                "past_success_rate": getattr(snapshot, "past_success_rate", None),
                "response_speed_score": getattr(snapshot, "response_speed_score", None),
                "financial_status": getattr(snapshot, "financial_status", None),
                "vendor_snapshot": build_vendor_snapshot_summary(snapshot),
            }
        )

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
        "source": vendor_snapshot.source,
    }


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
