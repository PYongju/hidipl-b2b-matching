from dataclasses import dataclass, field
from typing import Any

from services.requirement.schemas import RequirementInfo


@dataclass
class RequirementIngestionResult:
    request_id: str | None
    source_type: str
    source_path: str | None
    requirement: RequirementInfo
    embedding_text: str
    embedding_vector: list[float] | None
    embedding_dim: int | None
    raw_text_preview: str
    parser_warnings: list[str] = field(default_factory=list)
    parser_raw_matches: dict[str, Any] = field(default_factory=dict)
    ingestion_warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RequirementIngestionBatchResult:
    request_id: str | None
    results: list[RequirementIngestionResult] = field(default_factory=list)
    failed_inputs: list[dict[str, str]] = field(default_factory=list)
