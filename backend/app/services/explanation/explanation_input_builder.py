from typing import Any

from services.explanation.schemas import ExplanationInput
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
