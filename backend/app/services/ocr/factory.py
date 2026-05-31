from services.config import Settings
from services.ocr.azure_document_intelligence_provider import (
    AzureDocumnetIntelligenceProvider,
)
from services.ocr.base import OCRProvider


def create_ocr_provider(settings: Settings) -> OCRProvider:
    if settings.ocr_provider == "azure":
        return AzureDocumnetIntelligenceProvider(
            endpoint=settings.document_intelligence_endpoint,
            api_key=settings.document_intelligence_api_key,
            model_id=settings.azure_document_model_id,
        )

    # 추후 OSS 전환시 추가할 코드
    # if settings.ocr_provider == "paddleocr":
    #   return PaddleOCRProvider()

    raise ValueError(f"지원하지 않는 OCR_PROVIDER 입니다 : {settings.ocr_provider}")
