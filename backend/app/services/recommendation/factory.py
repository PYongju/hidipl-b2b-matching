from services.ranking.factory import create_ranking_provider
from services.recommendation.recommendation_pipeline import RecommendationPipeline


def create_recommendation_pipeline(
    provider_type: str = "rule",
) -> RecommendationPipeline:
    ranking_provider = create_ranking_provider(provider_type)
    return RecommendationPipeline(ranking_provider=ranking_provider)
