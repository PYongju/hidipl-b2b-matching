from typing import Any

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    company_name: str
    location: str | None = None
    deadline: str | None = None
    request_text: str


class ProjectCreateResponse(BaseModel):
    project_id: str
    request_id: str
    customer_name: str | None
    request_summary: str | None
    products: list[Any]
    region: str | None
    install_schedule_text: str | None
    embedding_dim: int | None
    parser_warnings: list[str]
    ingestion_warnings: list[str]


class QuoteUploadResponse(BaseModel):
    project_id: str
    quote_pool_id: str
    processed_count: int
    failed_files: list[Any]
    quotes: list[Any]


class CandidateVendorsRequest(BaseModel):
    request_text: str | None = None
    customer_name: str | None = None
    region: str | None = None
    install_schedule_text: str | None = None
    products: list[dict[str, Any]] | None = None
    requested_vendor_names: list[str] | None = None
    top_n: int = 10
    similarity_threshold: float = 60.0


class MatchRunRequest(BaseModel):
    quote_top_n: int = 3
    explanation_provider: str | None = None
    run_explanation: bool = False


class MatchRunResponse(BaseModel):
    project_id: str
    match_id: str
    recommendation: dict[str, Any]
    explanation: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompareRequest(BaseModel):
    quote_ids: list[str] | None = None
    top_n: int | None = None


class CompareResponse(BaseModel):
    project_id: str
    rows: list[dict[str, Any]]
    metadata: dict[str, Any] = Field(default_factory=dict)

class CandidateVendorRequest(BaseModel):
    quote_top_n: int = 10

class InternalNoteRequest(BaseModel):
    screen: str | None = None
    note: str | None = None
    notes: dict[str, str] | None = None
