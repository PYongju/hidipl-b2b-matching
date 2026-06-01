from abc import ABC, abstractmethod

from services.similarity.schemas import SimilarityResult


class SimilarityProvider(ABC):
    @abstractmethod
    def calculate(
        self,
        vector_a: list[float],
        vector_b: list[float],
    ) -> SimilarityResult:
        pass
