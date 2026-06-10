from services.config import get_settings
from services.embedding.factory import create_embedding_provider
from services.ocr.factory import create_ocr_provider
from services.parser.factory import create_parser_provider
from services.quote_ingestion.quote_ingestion_pipeline import QuoteIngestionPipeline


def create_quote_ingestion_pipeline(settings=None) -> QuoteIngestionPipeline:
    if settings is None:
        settings = get_settings()

    ocr_provider = create_ocr_provider(settings)
    parser_provider = create_parser_provider(settings=settings)

    try:
        embedding_provider = create_embedding_provider("azure_openai")
    except Exception as e:
        print(f"EmbeddingProvider 생성 실패. 임베딩 없이 파이프라인을 생성합니다: {e}")
        embedding_provider = None

    return QuoteIngestionPipeline(
        ocr_provider=ocr_provider,
        parser_provider=parser_provider,
        embedding_provider=embedding_provider,
    )
