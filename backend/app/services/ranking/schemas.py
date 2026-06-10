from dataclasses import dataclass, field
from typing import Any

from services.parser.schemas import QuoteDocument
from services.requirement.schemas import RequirementInfo


@dataclass
class PartnerProfile:
    name: str
    specialty_tags: list[str]
    is_premium: bool
    success_rate: float
    response_speed: str
    financial_status: str
    is_excluded: bool
    vendor_id: str | None = None
    installation_count: int | None = None
    industry_breakdown: dict[str, int] = field(default_factory=dict)
    solution_breakdown: dict[str, int] = field(default_factory=dict)
    scale_breakdown: dict[str, int] = field(default_factory=dict)
    avg_projects_3yr: float | None = None
    avg_revenue_3yr: str | None = None
    years_in_business: int | None = None
    representative: str | None = None
    company_location: str | None = None


@dataclass
class RankingCandidate:
    quote_id: str
    quote_document: QuoteDocument
    quote_embedding_vector: list[float] | None
    source_file_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RankingResult:
    rank: int
    quote_id: str
    quote_document: QuoteDocument
    partner_name: str | None
    partner_found: bool
    is_premium: bool
    success_rate: float | None
    response_speed: str | None
    financial_status: str | None
    partner_specialty_tags: list[str]
    business_rule_passed: bool
    business_stage: str
    business_sort_key: tuple | list | dict
    filter_reasons: list[str]
    final_score: float
    spec_score: float
    price_score: float
    delivery_score: float
    warranty_score: float
    installation_score: float
    cosine_similarity: float | None
    check_required: list[str]
    score_breakdown: dict[str, float]
    comparison_risks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RankingSummary:
    requirement: RequirementInfo
    top_n: int
    results: list[RankingResult]
    all_results: list[RankingResult]
