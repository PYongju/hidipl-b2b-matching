from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QuoteItem:
    name: str
    qty: int
    is_optional: bool
    spec: Optional[str] = None
    unit_price: Optional[int] = None          # 결측 시 None, 추정 금지 (P0-3)
    normalization_note: Optional[str] = None


@dataclass
class QuoteDocument:
    quote_id: str
    vendor_id: str
    vendor_name: str
    category: str                              # 'LED' | '비디오월'
    warranty_months: int
    total_price: int
    past_success_rate: float                   # 0.00 ~ 1.00 (0.0 → 블랙리스트)
    response_speed_score: int                  # 1 ~ 10
    items: list[QuoteItem] = field(default_factory=list)
    is_premium_partner: bool = False
    installation_cases_count: int = 0
    annual_revenue: Optional[int] = None
    delivery_days: Optional[int] = None        # 결측 시 None, 무시 처리 (P0-3)


@dataclass
class ProjectRequirements:
    project_id: str
    company_name: str
    location: str
    deadline: str                              # ISO 8601 date (e.g. '2026-09-01')
    use_case: str
    display_requirements: str
    current_phase: str                         # '정보탐색' | '기획' | '실행'
    client_type: str = "일반"                  # '일반' | '대기업' | '정부공공'


@dataclass
class MatchResult:
    quote: QuoteDocument
    score: float                               # 0.0 ~ 100.0
    rank: int
    matched_rules: list[str] = field(default_factory=list)
    excluded_by: Optional[str] = None          # None이면 블랙리스트 미적용