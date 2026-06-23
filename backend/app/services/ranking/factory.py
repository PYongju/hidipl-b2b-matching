from services.ranking.base import RankingProvider
from services.ranking.rule_based_ranking_provider import RuleBasedRankingProvider
from services.ranking.schemas import PartnerProfile
from services.similarity.factory import create_similarity_provider


def create_ranking_provider(
    provider_type: str = "rule",
    partner_profiles: list[PartnerProfile] | None = None,
) -> RankingProvider:
    if provider_type == "rule":
        similarity_provider = create_similarity_provider("cosine")
        return RuleBasedRankingProvider(
            similarity_provider=similarity_provider,
            partner_profiles=partner_profiles,
        )

    raise ValueError(f"지원하지 않는 RANKING_PROVIDER입니다: {provider_type}")
