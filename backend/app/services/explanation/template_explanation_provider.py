from services.explanation.base import ExplanationProvider
from services.explanation.explanation_text_policy import (
    decision_weaknesses,
    has_risk,
    split_comparison_risks,
    trim_sentence,
)
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
        top_items = recommendation_result.items[:3]
        supplier_explanations = [
            self._build_supplier_explanation(item, top_items)
            for item in top_items
        ]

        return RecommendationExplanationResult(
            request_id=recommendation_result.request_id,
            customer_name=recommendation_result.customer_name,
            overall_summary=self._build_overall_summary(top_items),
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
        top_items: list[RecommendationItem],
    ) -> SupplierExplanation:
        check_required, comparison_risks = split_comparison_risks(
            item.check_required,
            item.comparison_risks,
            item.rule_warnings,
        )
        return SupplierExplanation(
            quote_id=item.quote_id,
            vendor_name=item.vendor_name,
            rank=item.rank,
            card_summary=self._build_card_summary(item, top_items),
            strengths=self._build_strengths(item, top_items),
            weaknesses=self._build_weaknesses(item),
            check_required=check_required,
            metadata={
                "provider": "template",
                "final_score": item.final_score,
                "spec_score": item.spec_score,
                "price_score": item.price_score,
                "delivery_score": item.delivery_score,
                "warranty_score": item.warranty_score,
                "installation_score": item.installation_score,
                "business_rule_passed": item.business_rule_passed,
                "filter_reasons": item.filter_reasons,
                "llm_used": False,
                "fallback_used": False,
                "comparison_risks": comparison_risks,
            },
        )

    def _build_card_summary(
        self,
        item: RecommendationItem,
        top_items: list[RecommendationItem],
    ) -> str:
        risks = self._build_weaknesses(item)
        if item.rank == 1 and _is_best(item, top_items, "final_score"):
            if _is_best(item, top_items, "price_score"):
                return "최저가와 종합 점수에서 가장 우수한 견적입니다."
            return "종합 점수가 가장 높은 추천 견적입니다."
        if item.delivery_weeks and not self._has_delivery_uncertainty(item):
            return "납기는 명확하지만 가격과 조건 확인이 필요합니다."
        if risks and risks != ["특이 리스크 없음"]:
            risk = risks[0].replace(" 확인 필요", "")
            return trim_sentence(f"{risk} 확인이 필요한 견적입니다.", max_chars=45)
        return "주요 점수가 균형적인 비교 후보입니다."

    def _build_overall_summary(self, items: list[RecommendationItem]) -> str:
        if not items:
            return "추천 가능한 공급사 정보가 없습니다. 견적 데이터와 필터 조건 확인이 필요합니다."

        top = items[0]
        top_vendor = top.vendor_name or top.partner_name or top.quote_id
        if _is_best(top, items, "price_score"):
            first = f"1순위 {top_vendor}는 최종 점수 {top.final_score:.2f}로 가장 우수하며 가격 경쟁력도 가장 높습니다."
        else:
            first = f"1순위 {top_vendor}는 최종 점수 {top.final_score:.2f}로 가장 우수하며 가격과 사양을 함께 고려한 결과입니다."
        parts = [first]

        if len(items) >= 2:
            second = items[1]
            second_vendor = second.vendor_name or second.partner_name or second.quote_id
            if second.delivery_weeks and not self._has_delivery_uncertainty(second):
                parts.append(f"{second_vendor}은 납기 조건이 명확하지만 가격 리스크 확인이 필요합니다.")
            else:
                parts.append(f"{second_vendor}은 사양과 가격 조건을 추가 비교할 후보입니다.")
        if len(items) >= 3:
            third = items[2]
            third_vendor = third.vendor_name or third.partner_name or third.quote_id
            risks = self._build_weaknesses(third)
            if risks and risks != ["특이 리스크 없음"]:
                risk_text = ", ".join(risk.replace(" 확인 필요", "") for risk in risks[:2])
                parts.append(f"{third_vendor}은 {risk_text} 확인이 필요합니다.")

        return " ".join(parts[:3])

    def _build_strengths(
        self,
        item: RecommendationItem,
        top_items: list[RecommendationItem],
    ) -> list[str]:
        strengths: list[str] = []
        if _is_best(item, top_items, "final_score"):
            strengths.append(f"최종 점수 {item.final_score:.2f}로 1위")
        if _is_best(item, top_items, "price_score"):
            strengths.append(f"가격 점수 {item.price_score:.0f}점으로 경쟁력 우수")
        if _is_best(item, top_items, "spec_score") and item.spec_score >= 75:
            strengths.append("사양 점수가 Top3 중 우수")
        if (
            item.delivery_weeks
            and item.delivery_score >= 80
            and not self._has_delivery_uncertainty(item)
        ):
            strengths.append(f"납기 {item.delivery_weeks}주로 조건 명확")
        if item.warranty_months and item.warranty_score >= 80:
            strengths.append(f"보증 {item.warranty_months}개월")
        if item.installation_score >= 80 and not self._has_installation_uncertainty(item):
            strengths.append("설치 조건 반영")

        return _dedupe(strengths)[:2] or ["비교 검토 가능"]

    def _build_weaknesses(self, item: RecommendationItem) -> list[str]:
        weaknesses = decision_weaknesses(
            check_required=item.check_required,
            comparison_risks=item.comparison_risks,
            filter_reasons=item.filter_reasons,
            limit=2,
        )
        if weaknesses != ["특이 리스크 없음"]:
            return weaknesses

        score_risks: list[str] = []
        if item.delivery_score < 70 and not self._has_delivery_uncertainty(item):
            score_risks.append("납기 조건 확인 필요")
        if item.warranty_score < 70:
            score_risks.append("보증기간 확인 필요")
        if item.installation_score < 70:
            score_risks.append("설치 범위 확인 필요")
        if not item.partner_found:
            score_risks.append("파트너 매칭 확인 필요")
        return _dedupe(score_risks)[:2] or ["특이 리스크 없음"]

    def _has_delivery_uncertainty(self, item: RecommendationItem) -> bool:
        return has_risk(item.check_required, "납기 정보 미기재") or has_risk(
            item.check_required, "납기 별도협의"
        )

    def _has_installation_uncertainty(self, item: RecommendationItem) -> bool:
        return any("설치" in message and "확인" in message for message in item.check_required)


def _is_best(item: RecommendationItem, items: list[RecommendationItem], field: str) -> bool:
    values = [getattr(candidate, field) for candidate in items if getattr(candidate, field) is not None]
    return bool(values) and getattr(item, field) == max(values)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
