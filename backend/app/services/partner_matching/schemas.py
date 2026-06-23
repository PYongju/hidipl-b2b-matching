from dataclasses import dataclass, field
from typing import Any


@dataclass
class PartnerEmbeddingRecord:
    partner_name: str
    embedding_text: str
    embedding_vector: list[float]
    embedding_dim: int
    source_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PartnerMatchCandidate:
    partner_name: str
    specialty_tags: list[str]
    semantic_similarity_score: float
    cosine_similarity: float | None
    is_premium: bool
    success_rate: float
    response_speed: str
    financial_status: str
    is_excluded: bool
    business_rule_passed: bool
    business_stage: str
    filter_reasons: list[str]
    check_required: list[str]
    sort_key: list[Any]
    rank: int | None = None
    company_location: str | None = None
    installation_count: int | None = None
    final_score: float = 0.0
    semantic_score_calibrated: float = 0.0
    specialty_match_score: float = 0.0
    installation_score: float = 0.0
    success_score: float = 0.0
    premium_score: float = 0.0
    stability_score: float = 0.0
    score_breakdown: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PartnerMatchingResult:
    request_id: str | None
    customer_name: str | None
    top_n: int
    candidates: list[PartnerMatchCandidate]
    all_candidates: list[PartnerMatchCandidate]
    filtered_candidates: list[PartnerMatchCandidate]
    metadata: dict[str, Any] = field(default_factory=dict)
