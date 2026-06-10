from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequirementProduct:
    product_type: str | None = None
    display_type: str | None = None
    name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    diagonal_inch: float | None = None
    layout_rows: int | None = None
    layout_cols: int | None = None
    width_mm: int | None = None
    height_mm: int | None = None
    pitch_mm: float | None = None
    pitch_max_mm: float | None = None
    raw_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RequirementInfo:
    raw_text: str
    customer_name: str | None = None
    project_name: str | None = None
    commission_model: str | None = None
    commission_rate_percent: float | None = None
    request_summary: str | None = None
    products: list[RequirementProduct] = field(default_factory=list)
    region: str | None = None
    install_schedule_text: str | None = None
    review_deadline_text: str | None = None
    project_stage: str | None = None
    category: str | None = None
    display_size_text: str | None = None
    quantity_text: str | None = None
    operation_time: str | None = None
    review_preset: str | None = None
    other_conditions: str | None = None
    attachment_memo: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    notes: list[str] = field(default_factory=list)
    required_keywords: list[str] = field(default_factory=list)
    preferred_keywords: list[str] = field(default_factory=list)
    excluded_keywords: list[str] = field(default_factory=list)
    priority: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedRequirementResult:
    requirement: RequirementInfo
    warnings: list[str] = field(default_factory=list)
    raw_matches: dict[str, Any] = field(default_factory=dict)
