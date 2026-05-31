from services.embedding.azure_openai_embedding_provider import (
    AzureOpenAIEmbeddingProvider,
)
from services.embedding.base import EmbeddingProvider


def create_embedding_provider(
    provider_type: str = "azure_openai",
) -> EmbeddingProvider:
    if provider_type == "azure_openai":
        return AzureOpenAIEmbeddingProvider()

    raise ValueError(f"지원하지 않는 EMBEDDING_PROVIDER입니다: {provider_type}")
