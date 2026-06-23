from services.similarity.base import SimilarityProvider
from services.similarity.cosine_similarity_provider import CosineSimilarityProvider


def create_similarity_provider(
    provider_type: str = "cosine",
) -> SimilarityProvider:
    if provider_type == "cosine":
        return CosineSimilarityProvider()

    raise ValueError(f"지원하지 않는 SIMILARITY_PROVIDER입니다: {provider_type}")
