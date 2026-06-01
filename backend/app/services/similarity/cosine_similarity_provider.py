import math

from services.similarity.base import SimilarityProvider
from services.similarity.schemas import SimilarityResult


class CosineSimilarityProvider(SimilarityProvider):
    def calculate(
        self,
        vector_a: list[float],
        vector_b: list[float],
    ) -> SimilarityResult:
        if not vector_a or not vector_b:
            raise ValueError("Similarity 계산 대상 벡터가 비어 있습니다.")

        if len(vector_a) != len(vector_b):
            raise ValueError("Similarity 계산 대상 벡터 길이가 서로 다릅니다.")

        dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
        norm_a = math.sqrt(sum(a * a for a in vector_a))
        norm_b = math.sqrt(sum(b * b for b in vector_b))

        # zero vector는 의미 방향이 없으므로 Ranking 입력으로 쓰기 어렵다.
        # 호출자가 예외 처리를 통해 잘못된 embedding을 확인할 수 있게 한다.
        if norm_a == 0 or norm_b == 0:
            raise ValueError("Zero vector는 cosine similarity를 계산할 수 없습니다.")

        cosine = dot_product / (norm_a * norm_b)
        cosine = max(-1.0, min(1.0, cosine))
        normalized_score = ((cosine + 1.0) / 2.0) * 100.0

        return SimilarityResult(
            score=normalized_score,
            method="cosine",
            metadata={"cosine": f"{cosine:.12f}"},
        )
