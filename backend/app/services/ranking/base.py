from abc import ABC, abstractmethod

from services.ranking.schemas import RankingCandidate, RankingSummary
from services.requirement.schemas import RequirementInfo


class RankingProvider(ABC):
    @abstractmethod
    def rank(
        self,
        requirement: RequirementInfo,
        requirement_embedding_vector: list[float] | None,
        candidates: list[RankingCandidate],
        top_n: int = 3,
    ) -> RankingSummary:
        pass
