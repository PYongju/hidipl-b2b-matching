from typing import Any

from services.explanation.schemas import ExplanationInput
from services.explanation.explanation_text_policy import split_check_required
from services.recommendation.schemas import RecommendationPipelineResult

_ALLOWED_ITEM_FIELDS = [
    "rank",
    "quote_id",
    "vendor_name",
    "final_score",
    "spec_score",
    "price_score",
    "delivery_score",
    "warranty_score",
    "installation_score",
    "cosine_similarity",
    "total_supply_price",
    "total_with_vat",
    "delivery_weeks",
    "warranty_months",
    "line_item_count",
    "check_required",
    "comparison_risks",
    "special_notes",
    "vendor_snapshot_summary",
    "score_breakdown",
    "partner_name",
    "partner_found",
    "is_premium",
    "success_rate",
    "response_speed",
    "financial_status",
    "business_rule_passed",
    "business_stage",
    "filter_reasons",
]


def build_explanation_input(
    recommendation_result: RecommendationPipelineResult,
) -> ExplanationInput:
    top_items = []

    for item in recommendation_result.items[:3]:
        item_dict: dict[str, Any] = {}
        for field_name in _ALLOWED_ITEM_FIELDS:
            item_dict[field_name] = getattr(item, field_name, None)
        decision_risks, _ = split_check_required(item.check_required)
        item_dict["delivery_basis_raw"] = getattr(item, "delivery_basis_raw", None)
        item_dict["installation_included"] = getattr(item, "metadata", {}).get(
            "installation_included"
        )
        item_dict["check_required"] = decision_risks
        item_dict["comparison_risks"] = list(
            getattr(item, "comparison_risks", []) or []
        )
        item_dict["relative_position"] = _build_relative_position(
            item,
            recommendation_result.items[:3],
        )
        top_items.append(item_dict)

    metadata = {
        "top_n": recommendation_result.top_n,
        "failed_candidate_count": len(recommendation_result.failed_candidates),
        "filtered_candidate_count": len(recommendation_result.filtered_candidates),
    }

    return ExplanationInput(
        request_id=recommendation_result.request_id,
        customer_name=recommendation_result.customer_name,
        top_items=top_items,
        all_items_count=len(recommendation_result.all_items),
        metadata=metadata,
    )


def _build_relative_position(item, top_items) -> dict[str, bool]:
    if not top_items:
        return {}
    final_scores = [candidate.final_score for candidate in top_items]
    price_scores = [candidate.price_score for candidate in top_items]
    spec_scores = [candidate.spec_score for candidate in top_items]
    delivery_scores = [candidate.delivery_score for candidate in top_items]
    warranty_scores = [candidate.warranty_score for candidate in top_items]
    installation_scores = [candidate.installation_score for candidate in top_items]
    totals = [
        candidate.total_with_vat
        for candidate in top_items
        if candidate.total_with_vat is not None
    ]
    return {
        "is_highest_final_score": item.final_score == max(final_scores),
        "is_best_price_score": item.price_score == max(price_scores),
        "is_lowest_total": bool(totals) and item.total_with_vat == min(totals),
        "is_highest_spec_score": item.spec_score == max(spec_scores),
        "is_lowest_spec_score": item.spec_score == min(spec_scores),
        "is_best_delivery_score": item.delivery_score == max(delivery_scores),
        "is_best_warranty_score": item.warranty_score == max(warranty_scores),
        "is_best_installation_score": item.installation_score == max(installation_scores),
    }
