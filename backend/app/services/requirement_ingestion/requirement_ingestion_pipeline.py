from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from services.embedding.text_builder import build_requirement_embedding_text
from services.requirement.input_processor import RequirementInputProcessor
from services.requirement_ingestion.schemas import (
    RequirementIngestionBatchResult,
    RequirementIngestionResult,
)


class RequirementIngestionPipeline:
    def __init__(
        self,
        input_processor: RequirementInputProcessor,
        embedding_provider=None,
    ) -> None:
        self.input_processor = input_processor
        self.embedding_provider = embedding_provider

    def process_text(
        self,
        text: str,
        *,
        request_id: str | None = None,
    ) -> RequirementIngestionResult:
        if not text or not text.strip():
            raise ValueError("고객 요청 텍스트가 비어 있습니다.")

        try:
            parsed_result = self.input_processor.process_text(text)
        except Exception as e:
            raise RuntimeError(f"고객 요청 Parser 처리 실패: {e}") from e

        return self._build_result(
            request_id=request_id,
            source_type="text",
            source_path=None,
            parsed_result=parsed_result,
            raw_text_preview=text[:1000],
            metadata={
                "input_processor": self.input_processor.__class__.__name__,
                "parser_provider": self.input_processor.parser_provider.__class__.__name__,
                "embedding_provider": self._embedding_provider_name(),
                "status": "completed",
            },
        )

    def process_file(
        self,
        file_path: str | Path,
        *,
        request_id: str | None = None,
        pages: str | None = None,
    ) -> RequirementIngestionResult:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"고객 요청 파일을 찾을 수 없습니다: {path}")

        raw_text_preview = ""
        try:
            raw_text_preview = self._extract_raw_text_preview(path, pages=pages)
            parsed_result = self.input_processor.process_file(path, pages=pages)
        except Exception as e:
            raise RuntimeError(f"고객 요청 파일 처리 실패: {path} - {e}") from e

        return self._build_result(
            request_id=request_id,
            source_type="file",
            source_path=str(path),
            parsed_result=parsed_result,
            raw_text_preview=raw_text_preview,
            metadata={
                "file_name": path.name,
                "file_stem": path.stem,
                "input_processor": self.input_processor.__class__.__name__,
                "parser_provider": self.input_processor.parser_provider.__class__.__name__,
                "ocr_provider": (
                    self.input_processor.ocr_provider.__class__.__name__
                    if self.input_processor.ocr_provider is not None
                    else None
                ),
                "embedding_provider": self._embedding_provider_name(),
                "status": "completed",
            },
        )

    def process_inputs(
        self,
        inputs: list[str | Path],
        *,
        request_id: str | None = None,
        pages: str | None = None,
    ) -> RequirementIngestionBatchResult:
        results: list[RequirementIngestionResult] = []
        failed_inputs: list[dict[str, str]] = []

        for source in inputs:
            try:
                path = Path(source)
                if path.exists():
                    results.append(
                        self.process_file(
                            path,
                            request_id=request_id,
                            pages=pages,
                        )
                    )
                else:
                    results.append(
                        self.process_text(
                            str(source),
                            request_id=request_id,
                        )
                    )
            except Exception as e:
                failed_inputs.append(
                    {
                        "input": str(source),
                        "error": str(e),
                    }
                )

        return RequirementIngestionBatchResult(
            request_id=request_id,
            results=results,
            failed_inputs=failed_inputs,
        )

    def to_storage_dict(self, result: RequirementIngestionResult) -> dict[str, Any]:
        return self._to_jsonable(asdict(result))

    def _build_result(
        self,
        *,
        request_id: str | None,
        source_type: str,
        source_path: str | None,
        parsed_result,
        raw_text_preview: str,
        metadata: dict[str, Any],
    ) -> RequirementIngestionResult:
        ingestion_warnings: list[str] = []
        requirement = parsed_result.requirement
        embedding_text = build_requirement_embedding_text(requirement)
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
        metadata["embedding_status"] = (
            "completed" if embedding_vector is not None else "not_available"
        )

        return RequirementIngestionResult(
            request_id=request_id,
            source_type=source_type,
            source_path=source_path,
            requirement=requirement,
            embedding_text=embedding_text,
            embedding_vector=embedding_vector,
            embedding_dim=embedding_dim,
            raw_text_preview=raw_text_preview[:1000],
            parser_warnings=parsed_result.warnings,
            parser_raw_matches=parsed_result.raw_matches,
            ingestion_warnings=ingestion_warnings,
            metadata=metadata,
        )

    def _extract_raw_text_preview(
        self,
        path: Path,
        *,
        pages: str | None = None,
    ) -> str:
        if self.input_processor.ocr_provider is None:
            return ""

        ocr_result = self.input_processor.ocr_provider.extract(path, pages=pages)
        return (ocr_result.text or "")[:1000]

    def _embedding_provider_name(self) -> str | None:
        if self.embedding_provider is None:
            return None

        return self.embedding_provider.__class__.__name__

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
