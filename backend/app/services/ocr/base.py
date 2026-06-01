from abc import ABC, abstractmethod
from pathlib import Path

from services.ocr.schemas import OCRResult

# ocr_result = ocr_provider.extract("sample_quote.pdf")
# 어떤 OCR 기술을 쓰던 한가지 방식으로 호출 가능함!!!!!!!!


class OCRProvider(ABC):
    @abstractmethod
    def extract(
        self,
        source: str | Path,
        *,
        pages: str | None = None,
    ) -> OCRResult:
        """
        견적서 파일 또는 URL에서 OCR 결과를 추출한다.

        Args:
            source:
                로컬 파일 경로 또는 URL
            pages:
                분석할 페이지 범위.
                예: "1", "1-3", "1,3,5"

        Returns:
            OCRResult:
                시스템 공통 OCR 결과 형식
        """
        pass
