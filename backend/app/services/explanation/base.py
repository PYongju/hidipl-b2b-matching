from abc import ABC, abstractmethod

from services.explanation.schemas import RecommendationExplanationResult
from services.recommendation.schemas import RecommendationPipelineResult


class ExplanationProvider(ABC):
    @abstractmethod
    def generate(
        self,
        recommendation_result: RecommendationPipelineResult,
    ) -> RecommendationExplanationResult:
        raise NotImplementedError
