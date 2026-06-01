from dataclasses import dataclass, field
from typing import Any


@dataclass
class SupplierExplanation:
    quote_id: str
    vendor_name: str | None
    rank: int
    card_summary: str
    strengths: list[str]
    weaknesses: list[str]
    check_required: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecommendationExplanationResult:
    request_id: str | None
    customer_name: str | None
    overall_summary: str
    supplier_explanations: list[SupplierExplanation]
    provider: str
    warnings: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExplanationInput:
    request_id: str | None
    customer_name: str | None
    top_items: list[dict[str, Any]]
    all_items_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
