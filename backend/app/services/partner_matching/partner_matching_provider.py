from __future__ import annotations

import math
from statistics import quantiles

from services.partner_matching.schemas import (
    PartnerEmbeddingRecord,
    PartnerMatchCandidate,
    PartnerMatchingResult,
)
from services.ranking.schemas import PartnerProfile
from services.requirement.schemas import RequirementInfo
from services.similarity.base import SimilarityProvider


SCORE_WEIGHTS = {
    "semantic": 0.35,
    "specialty": 0.35,
    "installation": 0.10,
    "success": 0.10,
    "premium": 0.05,
    "stability": 0.05,
}

SOLUTION_SYNONYMS = {
    "LED전광판": {"LED전광판", "LED 전광판", "LED Display", "LED 디스플레이", "전광판"},
    "비디오월": {"비디오월", "Video Wall", "video wall", "멀티비전", "멀티비젼"},
    "사이니지": {"사이니지", "디지털사이니지", "디지털 사이니지", "Signage", "DID"},
    "투명디스플레이": {"투명디스플레이", "투명 OLED", "투명LED", "투명 LED"},
    "키오스크": {"키오스크", "KIOSK", "kiosk"},
}
CANONICAL_SOLUTION_ORDER = [
    "투명디스플레이",
    "비디오월",
    "LED전광판",
    "사이니지",
    "키오스크",
]

RELATED_SOLUTIONS = {
    "LED전광판": {"비디오월": 75.0, "사이니지": 60.0, "투명디스플레이": 35.0},
    "비디오월": {"LED전광판": 75.0, "사이니지": 60.0, "투명디스플레이": 35.0},
    "사이니지": {"LED전광판": 65.0, "비디오월": 65.0, "투명디스플레이": 50.0, "키오스크": 45.0},
    "투명디스플레이": {"사이니지": 55.0, "LED전광판": 45.0, "비디오월": 35.0},
    "키오스크": {"사이니지": 50.0},
}


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
            raise ValueError("requirement_embedding_vector is required for PartnerMatching.")

        requirement_keywords = build_requirement_solution_keywords(requirement)
        all_candidates = [
            self._score_partner(requirement_embedding_vector, requirement_keywords, partner)
            for partner in self.partners
        ]
        self._apply_relative_scores(all_candidates)
        all_candidates.sort(key=lambda candidate: tuple(candidate.sort_key), reverse=True)
        self._assign_selection_stages(all_candidates, top_n=top_n)

        passed = [candidate for candidate in all_candidates if candidate.business_rule_passed]
        filtered = [candidate for candidate in all_candidates if not candidate.business_rule_passed]
        cosine_values = [
            candidate.cosine_similarity
            for candidate in all_candidates
            if candidate.cosine_similarity is not None
        ]
        semantic_scores = [candidate.semantic_similarity_score for candidate in all_candidates]
        calibrated_scores = [
            candidate.semantic_score_calibrated for candidate in all_candidates
        ]
        specialty_scores = [candidate.specialty_match_score for candidate in all_candidates]
        final_scores = [candidate.final_score for candidate in all_candidates]

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
                "selected_count": len(passed),
                "not_selected_count": len(filtered),
                "filtered_count": len(filtered),
                "scoring_weights": dict(SCORE_WEIGHTS),
                "requirement_solution_keywords": sorted(requirement_keywords),
                "cosine_range": _range_metadata(cosine_values),
                "semantic_score_range": _range_metadata(semantic_scores),
                "calibrated_semantic_score_range": _range_metadata(calibrated_scores),
                "specialty_match_score_range": _range_metadata(specialty_scores),
                "final_score_range": _range_metadata(final_scores),
            },
        )

    def _assign_selection_stages(
        self,
        all_candidates: list[PartnerMatchCandidate],
        *,
        top_n: int,
    ) -> None:
        selected_count = 0
        for index, candidate in enumerate(all_candidates, start=1):
            candidate.rank = index
            if candidate.business_stage in {"excluded", "embedding_missing"}:
                candidate.business_rule_passed = False
                continue
            if selected_count < top_n:
                candidate.business_rule_passed = True
                candidate.business_stage = "selected_top_n"
                selected_count += 1
            else:
                candidate.business_rule_passed = False
                candidate.business_stage = "not_selected_top_n"
                reason = f"상위 {top_n}개 추천 후보 외"
                if reason not in candidate.filter_reasons:
                    candidate.filter_reasons.append(reason)

    def _score_partner(
        self,
        requirement_embedding_vector: list[float],
        requirement_keywords: set[str],
        partner: PartnerProfile,
    ) -> PartnerMatchCandidate:
        filter_reasons: list[str] = []
        check_required: list[str] = []
        business_rule_passed = True
        business_stage = "scored"
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

        response_score = self._response_speed_score(partner.response_speed)
        financial_score = self._financial_status_score(partner.financial_status)
        specialty_score = self._specialty_match_score(requirement_keywords, partner)
        premium_score = 100.0 if partner.is_premium else 0.0
        stability_score = round(((response_score + financial_score) / 6) * 100, 2)

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
            sort_key=[],
            company_location=partner.company_location,
            installation_count=partner.installation_count,
            specialty_match_score=specialty_score,
            premium_score=premium_score,
            stability_score=stability_score,
            metadata={
                "response_speed_score": response_score,
                "financial_status_score": financial_score,
                "company_location": partner.company_location,
                "installation_count": partner.installation_count,
                "solution_breakdown": dict(partner.solution_breakdown or {}),
                "industry_breakdown": dict(partner.industry_breakdown or {}),
                "scale_breakdown": dict(partner.scale_breakdown or {}),
                "requirement_solution_keywords": sorted(requirement_keywords),
            },
        )

    def _apply_relative_scores(self, candidates: list[PartnerMatchCandidate]) -> None:
        cosine_values = [
            candidate.cosine_similarity
            for candidate in candidates
            if candidate.cosine_similarity is not None
        ]
        p10, p90 = _percentile_bounds(cosine_values)
        max_installation_count = max(
            [candidate.installation_count or 0 for candidate in candidates] or [0]
        )
        max_success_rate = max([candidate.success_rate or 0.0 for candidate in candidates] or [0.0])

        for candidate in candidates:
            semantic_score = _scale_value(candidate.cosine_similarity, p10, p90)
            installation_score = _log_scale(candidate.installation_count or 0, max_installation_count)
            success_score = _scale_value(candidate.success_rate or 0.0, 0.0, max_success_rate)
            final_score = (
                semantic_score * SCORE_WEIGHTS["semantic"]
                + candidate.specialty_match_score * SCORE_WEIGHTS["specialty"]
                + installation_score * SCORE_WEIGHTS["installation"]
                + success_score * SCORE_WEIGHTS["success"]
                + candidate.premium_score * SCORE_WEIGHTS["premium"]
                + candidate.stability_score * SCORE_WEIGHTS["stability"]
            )

            candidate.semantic_score_calibrated = round(semantic_score, 2)
            candidate.installation_score = round(installation_score, 2)
            candidate.success_score = round(success_score, 2)
            candidate.final_score = round(final_score, 2)
            candidate.score_breakdown = {
                "semantic_score": candidate.semantic_score_calibrated,
                "semantic_score_calibrated": candidate.semantic_score_calibrated,
                "specialty_match_score": candidate.specialty_match_score,
                "installation_score": candidate.installation_score,
                "success_score": candidate.success_score,
                "premium_score": candidate.premium_score,
                "stability_score": candidate.stability_score,
                "weights": dict(SCORE_WEIGHTS),
            }
            candidate.sort_key = [
                0 if candidate.business_stage in {"excluded", "embedding_missing"} else 1,
                candidate.final_score,
                candidate.specialty_match_score,
                candidate.semantic_score_calibrated,
                1 if candidate.is_premium else 0,
                candidate.success_score,
                candidate.installation_score,
                _reverse_name_key(candidate.partner_name),
            ]

    def _specialty_match_score(
        self,
        requirement_keywords: set[str],
        partner: PartnerProfile,
    ) -> float:
        if not requirement_keywords:
            return 50.0

        partner_keywords = _canonical_solution_keywords(
            [
                *list(partner.specialty_tags or []),
                *list((partner.solution_breakdown or {}).keys()),
            ]
        )
        if not partner_keywords:
            return 0.0

        scores: list[float] = []
        for required in requirement_keywords:
            if required in partner_keywords:
                scores.append(100.0)
                continue
            related_scores = [
                RELATED_SOLUTIONS.get(required, {}).get(partner_keyword, 0.0)
                for partner_keyword in partner_keywords
            ]
            scores.append(max(related_scores or [0.0]))

        solution_bonus = self._solution_history_bonus(requirement_keywords, partner)
        return round(min(100.0, max(scores or [0.0]) + solution_bonus), 2)

    def _solution_history_bonus(
        self,
        requirement_keywords: set[str],
        partner: PartnerProfile,
    ) -> float:
        breakdown = partner.solution_breakdown or {}
        if not breakdown:
            return 0.0
        bonus = 0.0
        for key, count in breakdown.items():
            canonical = _canonical_solution_keyword(key)
            if canonical in requirement_keywords and count:
                bonus = max(bonus, min(10.0, math.log1p(count) * 2.5))
        return bonus

    def _response_speed_score(self, value: str | None) -> int:
        return {"fast": 3, "normal": 2, "slow": 1}.get((value or "").lower(), 0)

    def _financial_status_score(self, value: str | None) -> int:
        return {"good": 3, "normal": 2, "caution": 1, "bad": 0}.get((value or "").lower(), 0)


def build_requirement_solution_keywords(requirement: RequirementInfo) -> set[str]:
    values: list[str] = []
    metadata = getattr(requirement, "metadata", {}) or {}
    frontend_fields = metadata.get("frontend_fields") or {}
    for value in [
        getattr(requirement, "category", None),
        getattr(requirement, "display_size_text", None),
        getattr(requirement, "request_summary", None),
        getattr(requirement, "other_conditions", None),
        frontend_fields.get("카테고리"),
        frontend_fields.get("디스플레이 크기"),
        frontend_fields.get("추가 요청사항"),
        *list(getattr(requirement, "required_keywords", []) or []),
    ]:
        if value:
            values.append(str(value))

    for product in getattr(requirement, "products", []) or []:
        for value in [
            getattr(product, "product_type", None),
            getattr(product, "display_type", None),
            getattr(product, "name", None),
            getattr(product, "raw_text", None),
        ]:
            if value:
                values.append(str(value))

    return _canonical_solution_keywords(values)


def _canonical_solution_keywords(values: list[str]) -> set[str]:
    keywords = set()
    for value in values:
        canonical = _canonical_solution_keyword(value)
        if canonical:
            keywords.add(canonical)
    return keywords


def _canonical_solution_keyword(value: str | None) -> str | None:
    text = str(value or "").lower().replace(" ", "")
    if not text:
        return None
    for canonical in CANONICAL_SOLUTION_ORDER:
        synonyms = SOLUTION_SYNONYMS[canonical]
        for synonym in synonyms:
            if synonym.lower().replace(" ", "") in text:
                return canonical
    return None


def _percentile_bounds(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    if len(values) < 4:
        return min(values), max(values)
    quartiles = quantiles(values, n=10, method="inclusive")
    return quartiles[0], quartiles[-1]


def _scale_value(value: float | None, low: float, high: float) -> float:
    if value is None:
        return 0.0
    if high <= low:
        return 100.0 if value >= high else 0.0
    return max(0.0, min(100.0, ((value - low) / (high - low)) * 100))


def _log_scale(value: int, max_value: int) -> float:
    if value <= 0 or max_value <= 0:
        return 0.0
    return max(0.0, min(100.0, (math.log1p(value) / math.log1p(max_value)) * 100))


def _range_metadata(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "max": None, "spread": None}
    minimum = min(values)
    maximum = max(values)
    return {
        "min": round(minimum, 6),
        "max": round(maximum, 6),
        "spread": round(maximum - minimum, 6),
    }


def _reverse_name_key(value: str) -> str:
    return "".join(chr(0x10FFFF - ord(char)) for char in value)
