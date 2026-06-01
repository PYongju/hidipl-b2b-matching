from services.explanation.base import ExplanationProvider
from services.explanation.schemas import (
    RecommendationExplanationResult,
    SupplierExplanation,
)
from services.recommendation.schemas import RecommendationItem, RecommendationPipelineResult


class TemplateExplanationProvider(ExplanationProvider):
    def generate(
        self,
        recommendation_result: RecommendationPipelineResult,
    ) -> RecommendationExplanationResult:
        supplier_explanations = [
            self._build_supplier_explanation(item)
            for item in recommendation_result.items[:3]
        ]

        return RecommendationExplanationResult(
            request_id=recommendation_result.request_id,
            customer_name=recommendation_result.customer_name,
            overall_summary=self._build_overall_summary(recommendation_result.items[:3]),
            supplier_explanations=supplier_explanations,
            provider="template",
            warnings=[],
            metadata={
                "top_item_count": len(supplier_explanations),
                "all_item_count": len(recommendation_result.all_items),
            },
        )

    def _build_supplier_explanation(
        self,
        item: RecommendationItem,
    ) -> SupplierExplanation:
        return SupplierExplanation(
            quote_id=item.quote_id,
            vendor_name=item.vendor_name,
            rank=item.rank,
            card_summary=self._build_card_summary(item),
            strengths=self._build_strengths(item),
            weaknesses=self._build_weaknesses(item),
            check_required=item.check_required,
            metadata={
                "final_score": item.final_score,
                "spec_score": item.spec_score,
                "business_rule_passed": item.business_rule_passed,
                "filter_reasons": item.filter_reasons,
            },
        )

    def _build_card_summary(self, item: RecommendationItem) -> str:
        if not item.partner_found:
            return "파트너 마스터 매칭 확인이 필요한 후보입니다."

        if item.is_premium and item.spec_score >= 80:
            return "프리미엄 파트너이며 요청 스펙과의 유사도가 높아 우선 검토 후보입니다."

        if item.price_score >= 80 and item.check_required:
            return "가격 경쟁력은 있으나 확인 필요 항목 검토가 필요합니다."

        if item.spec_score >= 80:
            return "요청 스펙과의 유사도가 높아 비교 검토 후보입니다."

        if item.price_score >= 80:
            return "가격 경쟁력은 있으나 스펙 적합성 확인이 필요합니다."

        return "계산 결과와 업무 룰 기준을 함께 확인해야 하는 후보입니다."

    def _build_overall_summary(self, items: list[RecommendationItem]) -> str:
        if not items:
            return "추천 가능한 공급사 후보가 없습니다. 파트너 매칭 및 필터 사유 확인이 필요합니다."

        sentences = []
        for item in items[:3]:
            vendor = item.vendor_name or item.partner_name or item.quote_id
            if item.rank == 1:
                if item.is_premium:
                    sentence = (
                        f"1순위 {vendor}은 프리미엄 파트너이며 업무 룰 기준에서 우선 검토 대상입니다."
                    )
                else:
                    sentence = f"1순위 {vendor}은 계산 점수와 업무 룰 기준에서 가장 앞선 후보입니다."
            else:
                sentence = f"{item.rank}순위 {vendor}은"
                details = []
                if item.price_score >= 80:
                    details.append("가격 경쟁력이 있습니다")
                if item.spec_score >= 80:
                    details.append("스펙 유사도가 높습니다")
                if item.check_required:
                    details.append("확인 필요 항목이 있습니다")
                if not details:
                    details.append("추가 검토가 필요합니다")
                sentence += " " + ", ".join(details) + "."
            sentences.append(sentence)

        return " ".join(sentences[:5])

    def _build_strengths(self, item: RecommendationItem) -> list[str]:
        strengths = []

        if item.is_premium:
            strengths.append("프리미엄 파트너")
        if item.spec_score >= 80:
            strengths.append("요청 스펙과의 유사도 높음")
        if item.price_score >= 80:
            strengths.append("가격 경쟁력 우수")
        if item.delivery_score >= 80:
            strengths.append("납기 조건 양호")
        if item.warranty_score >= 80:
            strengths.append("보증 조건 양호")
        if item.installation_score >= 80:
            strengths.append("설치 포함 조건 충족")
        if item.success_rate is not None and item.success_rate >= 0.1:
            strengths.append("성사율 우수")

        return strengths[:3] or ["비교 검토 가능"]

    def _build_weaknesses(self, item: RecommendationItem) -> list[str]:
        weaknesses = []

        if item.check_required:
            weaknesses.extend(item.check_required)
        if item.filter_reasons:
            weaknesses.extend(item.filter_reasons)
        if item.delivery_score < 70:
            weaknesses.append("납기 확인 필요")
        if item.warranty_score < 70:
            weaknesses.append("보증 조건 확인 필요")
        if item.installation_score < 70:
            weaknesses.append("설치 범위 확인 필요")
        if not item.partner_found:
            weaknesses.append("파트너 마스터 매칭 확인 필요")

        deduped = []
        for weakness in weaknesses:
            if weakness and weakness not in deduped:
                deduped.append(weakness)

        return deduped[:3] or ["특이 리스크 없음"]
