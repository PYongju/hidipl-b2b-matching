from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecommendationItem:
    rank: int
    quote_id: str
    partner_name: str | None
    partner_found: bool
    is_premium: bool
    success_rate: float | None
    response_speed: str | None
    financial_status: str | None
    business_rule_passed: bool
    business_stage: str
    filter_reasons: list[str]
    business_sort_key: tuple | list | dict
    vendor_name: str | None
    project_name: str | None
    source_file_path: str | None
    final_score: float
    spec_score: float
    price_score: float
    delivery_score: float
    warranty_score: float
    installation_score: float
    cosine_similarity: float | None
    total_supply_price: int | None
    total_with_vat: int | None
    delivery_weeks: int | None
    delivery_basis_raw: str
    warranty_months: int | None
    line_item_count: int
    check_required: list[str]
    score_breakdown: dict[str, float]
    comparison_risks: list[str] = field(default_factory=list)
    critical_risks: list[dict[str, Any]] = field(default_factory=list)
    special_notes: list[str] = field(default_factory=list)
    rule_warnings: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    vendor_snapshot_source: str | None = None
    vendor_snapshot_summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecommendationPipelineResult:
    request_id: str | None
    customer_name: str | None
    top_n: int
    items: list[RecommendationItem]
    all_items: list[RecommendationItem]
    failed_candidates: list[dict[str, str]]
    filtered_candidates: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
