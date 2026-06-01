from services.config import get_settings
from services.embedding.factory import create_embedding_provider
from services.ocr.factory import create_ocr_provider
from services.requirement.factory import create_requirement_parser_provider
from services.requirement.input_processor import RequirementInputProcessor
from services.requirement_ingestion.requirement_ingestion_pipeline import (
    RequirementIngestionPipeline,
)


def create_requirement_ingestion_pipeline(settings=None) -> RequirementIngestionPipeline:
    if settings is None:
        settings = get_settings()

    requirement_parser = create_requirement_parser_provider("rule")

    try:
        ocr_provider = create_ocr_provider(settings)
    except Exception as e:
        print(f"OCRProvider 생성 실패. 텍스트 입력만 처리 가능합니다: {e}")
        ocr_provider = None

    input_processor = RequirementInputProcessor(
        parser_provider=requirement_parser,
        ocr_provider=ocr_provider,
    )

    try:
        embedding_provider = create_embedding_provider("azure_openai")
    except Exception as e:
        print(f"EmbeddingProvider 생성 실패. 임베딩 없이 파이프라인을 생성합니다: {e}")
        embedding_provider = None

    return RequirementIngestionPipeline(
        input_processor=input_processor,
        embedding_provider=embedding_provider,
    )
