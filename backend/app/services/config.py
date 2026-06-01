import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    document_intelligence_endpoint: str
    document_intelligence_api_key: str
    ocr_provider: str = "azure"
    azure_document_model_id: str = "prebuilt-layout"
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_embedding_deployment: str | None = None
    azure_openai_api_version: str = "2025-01-01-preview"
    azure_openai_chat_deployment: str | None = None
    azure_openai_chat_api_version: str = "2025-01-01-preview"


def get_settings() -> Settings:
    endpoint = os.getenv("DOCUMENTINTELLIGENCE_ENDPOINT")
    api_key = os.getenv("DOCUMENTINTELLIGENCE_API_KEY")

    if not endpoint:
        raise ValueError("DOCUMENTINTELLIGENCE_ENDPOINT 환경변수가 없습니다.")

    if not api_key:
        raise ValueError("DOCUMENTINTELLIGENCE_API_KEY 환경변수가 없습니다.")

    return Settings(
        document_intelligence_endpoint=endpoint,
        document_intelligence_api_key=api_key,
        ocr_provider=os.getenv("OCR_PROVIDER", "azure"),
        azure_document_model_id=os.getenv(
            "AZURE_DOCUMENT_MODEL_ID",
            "prebuilt-layout",
        ),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_openai_embedding_deployment=os.getenv(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        ),
        azure_openai_api_version=os.getenv(
            "AZURE_OPENAI_API_VERSION",
            "2025-01-01-preview",
        ),
        azure_openai_chat_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        azure_openai_chat_api_version=os.getenv(
            "AZURE_OPENAI_CHAT_API_VERSION",
            os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        ),
    )
