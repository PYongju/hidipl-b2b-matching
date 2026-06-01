from services.partner_matching.schemas import (
    PartnerEmbeddingRecord,
    PartnerMatchCandidate,
    PartnerMatchingResult,
)
from services.ranking.schemas import PartnerProfile
from services.requirement.schemas import RequirementInfo
from services.similarity.base import SimilarityProvider


class PartnerMatchingProvider:
    def __init__(
        self,
        partners: list[PartnerProfile],
        partner_embeddings: dict[str, PartnerEmbeddingRecord],
        similarity_provider: SimilarityProvider,
        similarity_threshold: float = 60.0,
    ) -> None:
        self.partners = partners
        self.partner_embeddings = partner_embeddings
        self.similarity_provider = similarity_provider
        self.similarity_threshold = similarity_threshold

    def match(
        self,
        requirement: RequirementInfo,
        requirement_embedding_vector: list[float],
        *,
        top_n: int = 10,
    ) -> PartnerMatchingResult:
        if not requirement_embedding_vector:
            raise ValueError("requirement_embedding_vector가 없어 PartnerMatching을 실행할 수 없습니다.")

        all_candidates = [
            self._score_partner(requirement_embedding_vector, partner)
            for partner in self.partners
        ]
        all_candidates.sort(key=lambda candidate: tuple(candidate.sort_key), reverse=True)

        passed = [candidate for candidate in all_candidates if candidate.business_rule_passed]
        filtered = [candidate for candidate in all_candidates if not candidate.business_rule_passed]

        return PartnerMatchingResult(
            request_id=None,
            customer_name=requirement.customer_name,
            top_n=top_n,
            candidates=passed[:top_n],
            all_candidates=all_candidates,
            filtered_candidates=filtered,
            metadata={
                "partner_count": len(self.partners),
                "similarity_threshold": self.similarity_threshold,
                "filtered_count": len(filtered),
            },
        )

    def _score_partner(
        self,
        requirement_embedding_vector: list[float],
        partner: PartnerProfile,
    ) -> PartnerMatchCandidate:
        filter_reasons: list[str] = []
        check_required: list[str] = []
        business_rule_passed = True
        business_stage = "passed"
        semantic_similarity_score = 0.0
        cosine_similarity = None

        record = self.partner_embeddings.get(partner.name)
        if record is None:
            business_rule_passed = False
            business_stage = "embedding_missing"
            filter_reasons.append("파트너 임베딩 없음")
        else:
            similarity = self.similarity_provider.calculate(
                requirement_embedding_vector,
                record.embedding_vector,
            )
            semantic_similarity_score = round(similarity.score, 2)
            cosine_raw = similarity.metadata.get("cosine")
            cosine_similarity = float(cosine_raw) if cosine_raw is not None else None

        if partner.is_excluded:
            business_rule_passed = False
            business_stage = "excluded"
            filter_reasons.append("제외 파트너")

        if (
            business_rule_passed
            and semantic_similarity_score < self.similarity_threshold
        ):
            business_rule_passed = False
            business_stage = "low_similarity"
            filter_reasons.append("솔루션 전문성 유사도 낮음")

        response_score = self._response_speed_score(partner.response_speed)
        financial_score = self._financial_status_score(partner.financial_status)
        sort_key = [
            1 if business_rule_passed else 0,
            semantic_similarity_score,
            1 if partner.is_premium else 0,
            partner.success_rate,
            response_score,
            financial_score,
        ]

        return PartnerMatchCandidate(
            partner_name=partner.name,
            specialty_tags=list(partner.specialty_tags),
            semantic_similarity_score=semantic_similarity_score,
            cosine_similarity=cosine_similarity,
            is_premium=partner.is_premium,
            success_rate=partner.success_rate,
            response_speed=partner.response_speed,
            financial_status=partner.financial_status,
            is_excluded=partner.is_excluded,
            business_rule_passed=business_rule_passed,
            business_stage=business_stage,
            filter_reasons=filter_reasons,
            check_required=check_required,
            sort_key=sort_key,
            metadata={
                "response_speed_score": response_score,
                "financial_status_score": financial_score,
            },
        )

    def _response_speed_score(self, value: str | None) -> int:
        return {"fast": 3, "normal": 2, "slow": 1}.get((value or "").lower(), 0)

    def _financial_status_score(self, value: str | None) -> int:
        return {"good": 3, "normal": 2, "caution": 1, "bad": 0}.get((value or "").lower(), 0)
