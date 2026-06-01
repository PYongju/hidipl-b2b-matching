from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    DocumentAnalysisFeature,
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

from services.ocr.base import OCRProvider
from services.ocr.schemas import OCRPage, OCRResult, OCRTable


class AzureDocumnetIntelligenceProvider(OCRProvider):
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model_id: str = "prebuilt-layout",
        locale: str | None = "ko-KR",
        use_key_value_pairs: bool = True,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model_id = model_id
        self.locale = locale
        self.use_key_value_pairs = use_key_value_pairs

        self.client = DocumentIntelligenceClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.api_key),
        )

    def extract(
        self,
        source: str | Path,
        *,
        pages: str | None = None,
    ) -> OCRResult:
        try:
            result = self._analyze(source=source, pages=pages)
            return self._to_ocr_result(result)
        except HttpResponseError as e:
            raise RuntimeError(
                f"Azure Document Intelligence OCR 요청 실패 : {e.message}"
            ) from e

        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"OCR 대상 파일을 찾을 수 없습니다 : {source}"
            ) from e

    def _analyze(self, source: str | Path, pages: str | None = None) -> Any:
        features = []

        if self.use_key_value_pairs:
            features.append(DocumentAnalysisFeature.KEY_VALUE_PAIRS)

        if self._is_url(str(source)):
            poller = self.client.begin_analyze_document(
                self.model_id,
                AnalyzeDocumentRequest(url_source=str(source)),
                pages=pages,
                locale=self.locale,
                features=features if features else None,
            )
            return poller.result()

        file_path = Path(source)

        if not file_path.exists():
            raise FileNotFoundError(str(file_path))

        with open(file_path, "rb") as file:
            poller = self.client.begin_analyze_document(
                self.model_id,
                body=file,
                pages=pages,
                locale=self.locale,
                features=features if features else None,
            )
        return poller.result()

    def _to_ocr_result(self, result: Any) -> OCRResult:
        return OCRResult(
            text=self._extract_text(result),
            pages=self._extract_pages(result),
            tables=self._extract_tables(result),
            key_values=self._extract_key_values(result),
            raw=self._safe_as_dict(result),
        )

    def _extract_text(self, result: Any) -> str:
        return getattr(result, "content", "") or ""

    def _extract_pages(self, result: Any) -> list[OCRPage]:
        pages: list[OCRPage] = []

        for page in getattr(result, "pages", []) or []:
            lines = []

            for line in getattr(page, "lines", []) or []:
                if getattr(line, "content", None):
                    lines.append(line.content)

            pages.append(
                OCRPage(
                    page_number=getattr(page, "page_number", 0),
                    width=getattr(page, "width", None),
                    height=getattr(page, "height", None),
                    unit=getattr(page, "unit", None),
                    lines=lines,
                )
            )

        return pages

    def _extract_tables(self, result: Any) -> list[OCRTable]:
        tables: list[OCRTable] = []

        for table in getattr(result, "tables", []) or []:
            row_count = getattr(table, "row_count", 0)
            column_count = getattr(table, "column_count", 0)

            grid = [["" for _ in range(column_count)] for _ in range(row_count)]

            for cell in getattr(table, "cells", []) or []:
                row_index = getattr(cell, "row_index", None)
                column_index = getattr(cell, "column_index", None)
                content = getattr(cell, "content", "") or ""

                if row_index is None or column_index is None:
                    continue

                if row_index < row_count and column_index < column_count:
                    grid[row_index][column_index] = content

            tables.append(
                OCRTable(
                    row_count=row_count,
                    column_count=column_count,
                    cells=grid,
                )
            )

        return tables

    def _extract_key_values(self, result: Any) -> dict[str, str]:
        key_values: dict[str, str] = {}

        for kv in getattr(result, "key_value_pairs", []) or []:
            key = getattr(getattr(kv, "key", None), "content", None)
            value = getattr(getattr(kv, "value", None), "content", None)

            if key and value:
                key_values[key.strip()] = value.strip()

        return key_values

    def _safe_as_dict(self, result: Any) -> dict[str, Any]:
        if hasattr(result, "as_dict"):
            return result.as_dict()

        return {}

    def _is_url(self, source: str) -> bool:
        parsed = urlparse(source)
        return parsed.scheme in {"http", "https"}
