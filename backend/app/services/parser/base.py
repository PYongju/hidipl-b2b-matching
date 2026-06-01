from abc import ABC, abstractmethod

from services.ocr.schemas import OCRResult
from services.parser.schemas import ParsedQuoteResult


class ParserProvider(ABC):
    @abstractmethod
    def parse(self, ocr_result: OCRResult) -> ParsedQuoteResult:
        pass
