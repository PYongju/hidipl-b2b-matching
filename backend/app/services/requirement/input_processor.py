from pathlib import Path

from services.ocr.base import OCRProvider
from services.requirement.base import RequirementParserProvider
from services.requirement.schemas import ParsedRequirementResult


class RequirementInputProcessor:
    def __init__(
        self,
        parser_provider: RequirementParserProvider,
        ocr_provider: OCRProvider | None = None,
    ) -> None:
        self.parser_provider = parser_provider
        self.ocr_provider = ocr_provider

    def process_text(self, text: str) -> ParsedRequirementResult:
        return self.parser_provider.parse(text)

    def process_file(
        self,
        file_path: str | Path,
        *,
        pages: str | None = None,
    ) -> ParsedRequirementResult:
        if self.ocr_provider is None:
            raise ValueError("파일 입력을 처리하려면 OCRProvider가 필요합니다.")

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"요청사항 입력 파일을 찾을 수 없습니다: {path}")

        ocr_result = self.ocr_provider.extract(path, pages=pages)
        return self.parser_provider.parse(ocr_result.text)

    def process(
        self,
        source: str | Path,
        *,
        input_type: str = "text",
        pages: str | None = None,
    ) -> ParsedRequirementResult:
        if input_type == "text":
            return self.process_text(str(source))

        if input_type in {"file", "image", "pdf"}:
            return self.process_file(source, pages=pages)

        raise ValueError(f"지원하지 않는 requirement input_type입니다: {input_type}")
