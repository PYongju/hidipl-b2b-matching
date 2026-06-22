from dataclasses import asdict
from datetime import datetime
from enum import Enum
import hashlib
from pathlib import Path
import re
from typing import Any

from services.embedding.text_builder import build_quote_embedding_text
from services.parser.excel_quote_parser_provider import ExcelQuoteParserProvider
from services.parser.quote_parser_validator import resolve_project_name
from services.parser.schemas import LineItemCategory, QuoteDocument
from services.parser.vendor_name_resolver import (
    VendorNameResolver,
    is_invalid_vendor_name,
)
from services.quote_ingestion.multi_option_splitter import split_multi_option_result
from services.quote_ingestion.vendor_snapshot_enricher import VendorSnapshotEnricher
from services.quote_ingestion.schemas import (
    QuoteIngestionBatchResult,
    QuoteIngestionResult,
)


class QuoteIngestionPipeline:
    def __init__(
        self,
        ocr_provider,
        parser_provider,
        embedding_provider=None,
        excel_parser_provider=None,
        vendor_snapshot_enricher=None,
    ) -> None:
        self.ocr_provider = ocr_provider
        self.parser_provider = parser_provider
        self.embedding_provider = embedding_provider
        self.excel_parser_provider = excel_parser_provider or ExcelQuoteParserProvider()
        self.vendor_snapshot_enricher = vendor_snapshot_enricher or VendorSnapshotEnricher()

    def process_file(
        self,
        file_path: str | Path,
        *,
        quote_id: str | None = None,
        request_id: str | None = None,
        pages: str | None = None,
    ) -> QuoteIngestionResult:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"견적서 파일을 찾을 수 없습니다: {path}")

        full_hash = self._calculate_sha256(path)
        short_hash = full_hash[:8]
        ingestion_warnings: list[str] = []

        if path.suffix.lower() in {".xlsx", ".xlsm"}:
            return self._process_excel_file(
                path=path,
                quote_id=quote_id,
                request_id=request_id,
                full_hash=full_hash,
                short_hash=short_hash,
                ingestion_warnings=ingestion_warnings,
            )

        try:
            ocr_result = self.ocr_provider.extract(path, pages=pages)
        except Exception as e:
            raise RuntimeError(f"견적서 OCR 처리 실패: {path} - {e}") from e

        try:
            parsed_result = self.parser_provider.parse(ocr_result)
        except Exception as e:
            raise RuntimeError(f"견적서 Parser 처리 실패: {path} - {e}") from e

        quote_document = parsed_result.quote_document
        vendor_debug = self._resolve_vendor_name(
            quote_document=quote_document,
            source_text=ocr_result.text or parsed_result.source_text,
            path=path,
        )
        if vendor_debug:
            parsed_result.raw_matches["vendor_name_debug"] = vendor_debug
        else:
            vendor_debug = parsed_result.raw_matches.get("vendor_name_debug")

        project_name_resolution = resolve_project_name(
            quote_document,
            source_text=ocr_result.text or parsed_result.source_text,
            file_stem=path.stem,
            parser_source="rule_label"
            if self.parser_provider.__class__.__name__ in {"RuleBasedQuoteParser", "RuleBasedQuoteParserProvider"}
            else "parser",
        )
        parsed_result.raw_matches["project_name_resolution"] = project_name_resolution
        if project_name_resolution.get("check_required_message"):
            quality_notes = parsed_result.raw_matches.get("parser_quality_notes") or []
            if not isinstance(quality_notes, list):
                quality_notes = [str(quality_notes)]
            quality_notes.append(str(project_name_resolution["check_required_message"]))
            parsed_result.raw_matches["parser_quality_notes"] = list(
                dict.fromkeys(quality_notes)
            )

        self._enrich_quote_document(
            quote_document=quote_document,
            path=path,
            short_hash=short_hash,
            explicit_quote_id=quote_id,
        )
        _, vendor_snapshot_debug = self.vendor_snapshot_enricher.enrich(quote_document)

        self._apply_final_category_sanity_checks(quote_document)

        embedding_text = build_quote_embedding_text(quote_document)
        embedding_vector = None

        if self.embedding_provider is None:
            ingestion_warnings.append(
                "EmbeddingProvider가 없어 embedding_vector를 생성하지 않았습니다."
            )
        else:
            try:
                embedding_vector = self.embedding_provider.embed_text(embedding_text)
            except Exception as e:
                ingestion_warnings.append(f"Embedding 처리 실패: {e}")

        embedding_dim = len(embedding_vector) if embedding_vector is not None else None

        return QuoteIngestionResult(
            quote_id=quote_document.quote_id,
            request_id=request_id,
            source_file_path=str(path),
            quote=quote_document,
            embedding_text=embedding_text,
            embedding_vector=embedding_vector,
            embedding_dim=embedding_dim,
            ocr_text_preview=(ocr_result.text or "")[:1000],
            parser_warnings=parsed_result.warnings,
            parser_raw_matches=parsed_result.raw_matches,
            ingestion_warnings=ingestion_warnings,
            metadata={
                "file_name": path.name,
                "file_stem": path.stem,
                "source_file_hash": full_hash,
                "source_file_hash_short": short_hash,
                "ocr_provider": self.ocr_provider.__class__.__name__,
                "parser_provider": self.parser_provider.__class__.__name__,
                "vendor_name_source": (
                    vendor_debug.get("vendor_name_source") if vendor_debug else None
                ),
                "vendor_name_confidence": (
                    vendor_debug.get("confidence") if vendor_debug else None
                ),
                "parser_check_required": self._build_parser_check_required(
                    parsed_result.raw_matches
                ),
                "parser_quality_notes": list(
                    parsed_result.raw_matches.get("parser_quality_notes") or []
                ),
                "project_name_resolution": project_name_resolution,
                "vendor_snapshot": vendor_snapshot_debug,
                "embedding_provider": (
                    self.embedding_provider.__class__.__name__
                    if self.embedding_provider is not None
                    else None
                ),
                "status": "completed",
                "embedding_status": (
                    "completed" if embedding_vector is not None else "not_available"
                ),
            },
        )

    def process_file_to_results(
        self,
        file_path: str | Path,
        *,
        quote_id: str | None = None,
        request_id: str | None = None,
        pages: str | None = None,
    ) -> list[QuoteIngestionResult]:
        result = self.process_file(
            file_path,
            quote_id=quote_id,
            request_id=request_id,
            pages=pages,
        )
        split_results = split_multi_option_result(result)
        if len(split_results) == 1 and split_results[0] is result:
            return split_results

        for split_result in split_results:
            self._apply_final_category_sanity_checks(split_result.quote)
            self._refresh_embedding(split_result)
        return split_results

    def _apply_final_category_sanity_checks(self, quote_document: QuoteDocument) -> None:
        for item in quote_document.line_items:
            name = (item.name or "").lower()
            if any(token in name for token in ["설치비", "설치 외", "제품 설치비"]):
                item.category = LineItemCategory.INSTALL
                item.spec_parsed = {
                    **(item.spec_parsed or {}),
                    "normalized_cost_type": "INSTALL",
                }

    def _process_excel_file(
        self,
        *,
        path: Path,
        quote_id: str | None,
        request_id: str | None,
        full_hash: str,
        short_hash: str,
        ingestion_warnings: list[str],
    ) -> QuoteIngestionResult:
        try:
            quote_document = self.excel_parser_provider.parse(path)
            text_preview = self.excel_parser_provider.extract_text_preview(path)
            vendor_debug = self._resolve_vendor_name(
                quote_document=quote_document,
                source_text=text_preview,
                path=path,
            )
        except Exception as e:
            raise RuntimeError(f"Excel 견적서 Parser 처리 실패: {path} - {e}") from e

        self._enrich_quote_document(
            quote_document=quote_document,
            path=path,
            short_hash=short_hash,
            explicit_quote_id=quote_id,
        )
        _, vendor_snapshot_debug = self.vendor_snapshot_enricher.enrich(quote_document)

        embedding_text = build_quote_embedding_text(quote_document)
        embedding_vector = None

        if self.embedding_provider is None:
            ingestion_warnings.append(
                "EmbeddingProvider가 없어 embedding_vector를 생성하지 않았습니다."
            )
        else:
            try:
                embedding_vector = self.embedding_provider.embed_text(embedding_text)
            except Exception as e:
                ingestion_warnings.append(f"Embedding 처리 실패: {e}")

        embedding_dim = len(embedding_vector) if embedding_vector is not None else None

        return QuoteIngestionResult(
            quote_id=quote_document.quote_id,
            request_id=request_id,
            source_file_path=str(path),
            quote=quote_document,
            embedding_text=embedding_text,
            embedding_vector=embedding_vector,
            embedding_dim=embedding_dim,
            ocr_text_preview=text_preview[:1000],
            parser_warnings=[],
            parser_raw_matches={
                "source_type": "excel",
                **({"vendor_name_debug": vendor_debug} if vendor_debug else {}),
            },
            ingestion_warnings=ingestion_warnings,
            metadata={
                "file_name": path.name,
                "file_stem": path.stem,
                "source_file_hash": full_hash,
                "source_file_hash_short": short_hash,
                "ocr_provider": None,
                "parser_provider": self.excel_parser_provider.__class__.__name__,
                "vendor_name_source": (
                    vendor_debug.get("vendor_name_source") if vendor_debug else None
                ),
                "vendor_name_confidence": (
                    vendor_debug.get("confidence") if vendor_debug else None
                ),
                "vendor_snapshot": vendor_snapshot_debug,
                "embedding_provider": (
                    self.embedding_provider.__class__.__name__
                    if self.embedding_provider is not None
                    else None
                ),
                "status": "completed",
                "embedding_status": (
                    "completed" if embedding_vector is not None else "not_available"
                ),
            },
        )

    def process_files(
        self,
        file_paths: list[str | Path],
        *,
        request_id: str | None = None,
        pages: str | None = None,
    ) -> QuoteIngestionBatchResult:
        results: list[QuoteIngestionResult] = []
        failed_files: list[dict[str, str]] = []

        for file_path in file_paths:
            path = Path(file_path)
            try:
                results.extend(
                    self.process_file_to_results(
                        path,
                        request_id=request_id,
                        pages=pages,
                    )
                )
            except Exception as e:
                failed_files.append(
                    {
                        "file_path": str(path),
                        "error": str(e),
                    }
                )

        return QuoteIngestionBatchResult(
            request_id=request_id,
            results=results,
            failed_files=failed_files,
        )

    def _resolve_vendor_name(
        self,
        *,
        quote_document: QuoteDocument,
        source_text: str,
        path: Path,
    ) -> dict[str, Any] | None:
        if quote_document.vendor_name and not is_invalid_vendor_name(quote_document.vendor_name):
            return None

        resolved_vendor_name, vendor_debug = VendorNameResolver().resolve(
            current_vendor_name=quote_document.vendor_name,
            source_text=source_text,
            source_file_path=str(path),
        )

        if resolved_vendor_name:
            quote_document.vendor_name = resolved_vendor_name

        return vendor_debug

    def _build_parser_check_required(
        self,
        raw_matches: dict[str, Any],
    ) -> list[str]:
        checks = []
        parser_check_required = raw_matches.get("parser_check_required") or []
        if isinstance(parser_check_required, list):
            checks.extend(str(item) for item in parser_check_required if item)
        elif parser_check_required:
            checks.append(str(parser_check_required))

        warranty_condition = raw_matches.get("warranty_condition_check_required")
        if warranty_condition:
            checks.append(str(warranty_condition))

        if raw_matches.get("delivery_basis_raw") == "별도협의":
            checks.append("납기 별도협의")

        return list(dict.fromkeys(checks))

    def _refresh_embedding(self, result: QuoteIngestionResult) -> None:
        result.embedding_text = build_quote_embedding_text(result.quote)
        result.embedding_vector = None
        result.embedding_dim = None

        if self.embedding_provider is None:
            result.ingestion_warnings.append(
                "EmbeddingProvider가 없어 embedding_vector를 생성하지 않았습니다."
            )
            result.metadata["embedding_status"] = "not_available"
            return

        try:
            result.embedding_vector = self.embedding_provider.embed_text(result.embedding_text)
        except Exception as e:
            result.ingestion_warnings.append(f"Embedding 처리 실패: {e}")
            result.metadata["embedding_status"] = "failed"
            return

        result.embedding_dim = len(result.embedding_vector)
        result.metadata["embedding_provider"] = self.embedding_provider.__class__.__name__
        result.metadata["embedding_status"] = "completed"

    def to_storage_dict(self, result: QuoteIngestionResult) -> dict[str, Any]:
        return self._to_jsonable(asdict(result))

    def _calculate_sha256(self, path: Path) -> str:
        hasher = hashlib.sha256()

        with open(path, "rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                hasher.update(chunk)

        return hasher.hexdigest()

    def _enrich_quote_document(
        self,
        *,
        quote_document: QuoteDocument,
        path: Path,
        short_hash: str,
        explicit_quote_id: str | None,
    ) -> None:
        quote_document.source_file_path = str(path)
        quote_document.source_file_hash = short_hash

        if explicit_quote_id:
            quote_document.quote_id = explicit_quote_id
            return

        if self._is_empty_or_temporary_quote_id(quote_document.quote_id):
            quote_document.quote_id = self._build_quote_id(
                vendor_name=quote_document.vendor_name,
                received_at=quote_document.received_at,
                short_hash=short_hash,
            )

    def _build_quote_id(
        self,
        *,
        vendor_name: str,
        received_at: datetime,
        short_hash: str,
    ) -> str:
        safe_vendor = self._safe_quote_id_part(vendor_name) or "unknown_vendor"
        return f"{safe_vendor}_{received_at:%Y%m%d_%H%M%S}_{short_hash}"

    def _safe_quote_id_part(self, value: str) -> str:
        value = re.sub(r"\s+", "_", value.strip())
        value = re.sub(r"[^0-9A-Za-z가-힣_]+", "_", value)
        value = re.sub(r"_+", "_", value)
        return value.strip("_")

    def _is_empty_or_temporary_quote_id(self, quote_id: str | None) -> bool:
        if not quote_id:
            return True

        return not re.search(r"_[0-9]{8}_[0-9]{6}_[0-9a-fA-F]{8}$", quote_id)

    def _safe_quote_id_part(self, value: str) -> str:
        value = re.sub(r"\s+", "_", value.strip())
        value = re.sub(r"[^0-9A-Za-z가-힣]+", "_", value)
        value = re.sub(r"_+", "_", value)
        return value.strip("_")

    def _safe_quote_id_part(self, value: str) -> str:
        value = re.sub(r"\s+", "_", value.strip())
        value = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)
        value = re.sub(r"_+", "_", value)
        return value.strip("_")

    def _to_jsonable(self, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, dict):
            return {key: self._to_jsonable(item) for key, item in value.items()}

        if isinstance(value, list):
            return [self._to_jsonable(item) for item in value]

        return value
