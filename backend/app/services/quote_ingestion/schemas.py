from dataclasses import dataclass, field
from typing import Any

from services.parser.schemas import QuoteDocument


@dataclass
class QuoteIngestionResult:
    quote_id: str | None
    request_id: str | None
    source_file_path: str
    quote: QuoteDocument
    embedding_text: str
    embedding_vector: list[float] | None
    embedding_dim: int | None
    ocr_text_preview: str
    parser_warnings: list[str] = field(default_factory=list)
    parser_raw_matches: dict[str, Any] = field(default_factory=dict)
    ingestion_warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QuoteIngestionBatchResult:
    request_id: str | None
    results: list[QuoteIngestionResult] = field(default_factory=list)
    failed_files: list[dict[str, str]] = field(default_factory=list)
