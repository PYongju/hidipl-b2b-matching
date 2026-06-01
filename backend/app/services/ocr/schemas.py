from dataclasses import dataclass, field
from typing import Any


@dataclass
class OCRTable:
    row_count: int
    column_count: int
    cells: list[list[str]]


@dataclass
class OCRPage:
    page_number: int
    width: float | None = None
    height: float | None = None
    unit: str | None = None
    lines: list[str] = field(default_factory=list)


@dataclass
class OCRResult:
    text: str
    pages: list[OCRPage] = field(default_factory=list)
    tables: list[OCRTable] = field(default_factory=list)
    key_values: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


# | 필드          | 설명               |
# | ------------ | ---------------- |
# | `text`       | 전체 OCR 텍스트       |
# | `pages`      | 페이지별 줄 단위 OCR 결과 |
# | `tables`     | 표 데이터            |
# | `key_values` | Key-Value 추출 결과  |
# | `raw`        | Azure 원본 결과 보관용  |
