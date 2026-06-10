import re
from typing import Any

from services.parser.schemas import LineItemCategory, QuoteDocument
from services.ranking.base import RankingProvider
from services.ranking.partner_loader import load_partner_profiles
from services.ranking.schemas import (
    PartnerProfile,
    RankingCandidate,
    RankingResult,
    RankingSummary,
)
from services.requirement.schemas import RequirementInfo
from services.similarity.base import SimilarityProvider


class RuleBasedRankingProvider(RankingProvider):
    def __init__(
        self,
        similarity_provider: SimilarityProvider,
        partner_profiles: list[PartnerProfile] | None = None,
    ) -> None:
        self.similarity_provider = similarity_provider
        self.partner_profiles = partner_profiles if partner_profiles is not None else load_partner_profiles()
        self.partner_index = {
            self._normalize_company_name(profile.name): profile
            for profile in self.partner_profiles
        }

    def rank(
        self,
        requirement: RequirementInfo,
        requirement_embedding_vector: list[float] | None,
        candidates: list[RankingCandidate],
        top_n: int = 3,
    ) -> RankingSummary:
        price_map = self._build_candidate_price_map(candidates)
        valid_prices = [price for price in price_map.values() if price and price > 0]
        lowest_price = min(valid_prices) if valid_prices else None

        scored_contexts = []
        highest_spec_score = 0.0

        for candidate in candidates:
            result = self._score_candidate(
                requirement=requirement,
                requirement_embedding_vector=requirement_embedding_vector,
                candidate=candidate,
                candidate_price=price_map.get(candidate.quote_id),
                lowest_price=lowest_price,
            )
            highest_spec_score = max(highest_spec_score, result.spec_score)
            scored_contexts.append(
                {
                    "result": result,
                    "candidate_price": price_map.get(candidate.quote_id),
                }
            )

        results = []
        for context in scored_contexts:
            result = context["result"]
            self._apply_business_rules(
                requirement=requirement,
                result=result,
                candidate_price=context["candidate_price"],
                lowest_price=lowest_price,
                highest_spec_score=highest_spec_score,
            )
            results.append(result)

        results.sort(key=lambda result: tuple(result.business_sort_key), reverse=True)

        for index, result in enumerate(results, start=1):
            result.rank = index

        passed_results = [result for result in results if result.business_rule_passed]

        return RankingSummary(
            requirement=requirement,
            top_n=top_n,
            results=passed_results[:top_n],
            all_results=results,
        )

    def _score_candidate(
        self,
        *,
        requirement: RequirementInfo,
        requirement_embedding_vector: list[float] | None,
        candidate: RankingCandidate,
        candidate_price: int | None,
        lowest_price: int | None,
    ) -> RankingResult:
        check_required: list[str] = []
        for check in candidate.metadata.get("parser_check_required", []) or []:
            self._append_check(check_required, str(check))

        spec_score, cosine_similarity = self._calculate_spec_score(
            requirement_embedding_vector=requirement_embedding_vector,
            quote_embedding_vector=candidate.quote_embedding_vector,
            check_required=check_required,
        )
        price_score = self._calculate_price_score(
            requirement=requirement,
            candidate_price=candidate_price,
            lowest_price=lowest_price,
            check_required=check_required,
        )
        delivery_score = self._calculate_delivery_score(
            requirement=requirement,
            quote=candidate.quote_document,
            check_required=check_required,
        )
        warranty_score = self._calculate_warranty_score(
            requirement=requirement,
            quote=candidate.quote_document,
            check_required=check_required,
        )
        installation_score = self._calculate_installation_score(
            quote=candidate.quote_document,
            check_required=check_required,
        )
        final_score = (
            spec_score * 0.30
            + price_score * 0.30
            + delivery_score * 0.20
            + warranty_score * 0.10
            + installation_score * 0.10
        )

        vendor_snapshot = candidate.quote_document.vendor_snapshot
        partner = None if vendor_snapshot is not None else self._find_partner(candidate.quote_document.vendor_name)
        partner_found = vendor_snapshot is not None or partner is not None
        is_premium = (
            bool(vendor_snapshot.is_premium_partner)
            if vendor_snapshot is not None
            else bool(partner.is_premium) if partner else False
        )
        success_rate = (
            float(vendor_snapshot.past_success_rate)
            if vendor_snapshot is not None and vendor_snapshot.past_success_rate is not None
            else float(partner.success_rate) if partner else 0.0
        )
        response_speed = (
            vendor_snapshot.response_speed
            if vendor_snapshot is not None
            else partner.response_speed if partner else None
        )
        financial_status = (
            vendor_snapshot.financial_status
            if vendor_snapshot is not None
            else partner.financial_status if partner else None
        )
        specialty_tags = (
            list(vendor_snapshot.specialty_tags)
            if vendor_snapshot is not None
            else list(partner.specialty_tags) if partner else []
        )
        partner_name = (
            vendor_snapshot.vendor_name
            if vendor_snapshot is not None
            else partner.name if partner else None
        )
        matched_rules = self._build_matched_rules(
            is_premium=is_premium,
            success_rate=success_rate,
            response_speed=response_speed,
        )

        score_breakdown = {
            "spec_score": self._round_score(spec_score),
            "spec_weight": 0.30,
            "price_score": self._round_score(price_score),
            "price_weight": 0.30,
            "delivery_score": self._round_score(delivery_score),
            "delivery_weight": 0.20,
            "warranty_score": self._round_score(warranty_score),
            "warranty_weight": 0.10,
            "installation_score": self._round_score(installation_score),
            "installation_weight": 0.10,
            "final_score": self._round_score(final_score),
            "is_premium": is_premium,
            "success_rate": success_rate,
            "response_speed_score": self._response_speed_score(response_speed),
            "financial_status_score": self._financial_status_score(financial_status),
            "business_rule_passed": False,
        }

        return RankingResult(
            rank=0,
            quote_id=candidate.quote_id,
            quote_document=candidate.quote_document,
            partner_name=partner_name,
            partner_found=partner_found,
            is_premium=is_premium,
            success_rate=success_rate if partner_found else None,
            response_speed=response_speed,
            financial_status=financial_status,
            partner_specialty_tags=specialty_tags,
            business_rule_passed=False,
            business_stage="scored",
            business_sort_key=[],
            filter_reasons=[],
            final_score=score_breakdown["final_score"],
            spec_score=score_breakdown["spec_score"],
            price_score=score_breakdown["price_score"],
            delivery_score=score_breakdown["delivery_score"],
            warranty_score=score_breakdown["warranty_score"],
            installation_score=score_breakdown["installation_score"],
            cosine_similarity=cosine_similarity,
            check_required=check_required,
            score_breakdown=score_breakdown,
            metadata={
                **candidate.metadata,
                "matched_rules": matched_rules,
                "vendor_snapshot_source": (
                    vendor_snapshot.source if vendor_snapshot is not None else None
                ),
                "is_excluded": (
                    vendor_snapshot.is_excluded
                    if vendor_snapshot is not None
                    else partner.is_excluded if partner else False
                ),
            },
        )

    def _apply_business_rules(
        self,
        *,
        requirement: RequirementInfo,
        result: RankingResult,
        candidate_price: int | None,
        lowest_price: int | None,
        highest_spec_score: float,
    ) -> None:
        filter_reasons: list[str] = []
        rule_warnings: list[str] = []
        business_rule_passed = True
        business_stage = "quote_ranking"

        specialty_score = self._specialty_match_score(
            requirement=requirement,
            specialty_tags=result.partner_specialty_tags,
        )

        if not result.partner_found:
            rule_warnings.append("파트너 마스터 미등록")
        elif self._find_partner(result.quote_document.vendor_name).is_excluded:
            rule_warnings.append("제외 파트너 견적서")

        price_gap_rate = self._price_gap_rate(candidate_price, lowest_price)
        if price_gap_rate is not None and price_gap_rate > 0.05:
            self._append_check(
                result.comparison_risks,
                "최저가 대비 가격 차이 5% 초과",
            )
            rule_warnings.append("가격 차이 5% 초과")

        response_score = self._response_speed_score(result.response_speed)
        financial_score = self._financial_status_score(result.financial_status)
        success_rate = result.success_rate or 0.0

        sort_key = [
            1 if business_rule_passed else 0,
            result.final_score,
            result.price_score,
            result.spec_score,
            1 if result.is_premium else 0,
            success_rate,
            response_score,
            financial_score,
        ]

        result.business_rule_passed = business_rule_passed
        result.business_stage = business_stage
        result.business_sort_key = sort_key
        result.filter_reasons = filter_reasons
        result.metadata["rule_warnings"] = rule_warnings
        result.score_breakdown.update(
            {
                "specialty_match_score": round(specialty_score, 2),
                "is_premium": result.is_premium,
                "success_rate": success_rate,
                "response_speed_score": response_score,
                "financial_status_score": financial_score,
                "business_rule_passed": business_rule_passed,
            }
        )

    def _calculate_spec_score(
        self,
        *,
        requirement_embedding_vector: list[float] | None,
        quote_embedding_vector: list[float] | None,
        check_required: list[str],
    ) -> tuple[float, float | None]:
        if requirement_embedding_vector is None:
            check_required.append("요구사항 임베딩 없음")
            return 50.0, None

        if quote_embedding_vector is None:
            check_required.append("견적서 임베딩 없음")
            return 50.0, None

        try:
            result = self.similarity_provider.calculate(
                requirement_embedding_vector,
                quote_embedding_vector,
            )
            cosine_raw = result.metadata.get("cosine")
            cosine_similarity = float(cosine_raw) if cosine_raw is not None else None
            return self._clamp_score(result.score), cosine_similarity
        except Exception:
            check_required.append("스펙 유사도 계산 실패")
            return 50.0, None

    def _build_candidate_price_map(
        self,
        candidates: list[RankingCandidate],
    ) -> dict[str, int | None]:
        return {
            candidate.quote_id: self._get_comparable_price(candidate.quote_document)
            for candidate in candidates
        }

    def _get_comparable_price(self, quote: QuoteDocument) -> int | None:
        if quote.total_supply_price and quote.total_supply_price > 0:
            return quote.total_supply_price

        total = 0
        has_price = False
        included_categories = {
            LineItemCategory.DISPLAY,
            LineItemCategory.MOUNT,
            LineItemCategory.CABLE,
            LineItemCategory.INSTALL,
            LineItemCategory.ETC,
            LineItemCategory.PLAYER,
            LineItemCategory.SOFTWARE,
        }

        for item in quote.line_items:
            if item.is_optional or item.category not in included_categories:
                continue
            if item.total_price is None:
                continue
            total += item.total_price
            has_price = True

        return total if has_price else None

    def _calculate_price_score(
        self,
        *,
        requirement: RequirementInfo,
        candidate_price: int | None,
        lowest_price: int | None,
        check_required: list[str],
    ) -> float:
        if not candidate_price or candidate_price <= 0 or not lowest_price:
            check_required.append("가격 비교 정보 부족")
            return 50.0

        score = lowest_price / candidate_price * 100.0

        if requirement.budget_max is not None and candidate_price > requirement.budget_max:
            check_required.append("예산 초과")
            score -= 10.0

        return self._clamp_score(score)

    def _calculate_delivery_score(
        self,
        *,
        requirement: RequirementInfo,
        quote: QuoteDocument,
        check_required: list[str],
    ) -> float:
        if not requirement.install_schedule_text:
            return 100.0

        required_weeks = self._extract_required_weeks(requirement.install_schedule_text)
        if required_weeks is None:
            check_required.append("요구 납기 정규화 필요")
            return 70.0

        if (quote.delivery_basis_raw or "").strip() == "별도협의":
            self._append_check(check_required, "납기 별도협의")
            return 70.0

        if quote.delivery_weeks is None:
            check_required.append("견적 납기 미기재")
            return 50.0

        if quote.delivery_weeks <= required_weeks:
            return 100.0

        return self._clamp_score(required_weeks / quote.delivery_weeks * 100.0)

    def _extract_required_weeks(self, value: str) -> int | None:
        text = value.replace(" ", "")

        match = re.search(r"(\d+(?:\.\d+)?)주(?:이내|내외|까지)?", text)
        if match:
            return max(1, round(float(match.group(1))))

        match = re.search(r"(\d+(?:\.\d+)?)개월(?:이내|내외|까지)?", text)
        if match:
            return max(1, round(float(match.group(1)) * 4))

        return None

    def _calculate_warranty_score(
        self,
        *,
        requirement: RequirementInfo,
        quote: QuoteDocument,
        check_required: list[str],
    ) -> float:
        target_months = self._extract_required_warranty_months(requirement) or 12

        if quote.warranty_months is None:
            check_required.append("보증기간 미기재")
            return 50.0

        if quote.warranty_months >= target_months:
            return 100.0

        return self._clamp_score(quote.warranty_months / target_months * 100.0)

    def _extract_required_warranty_months(
        self,
        requirement: RequirementInfo,
    ) -> int | None:
        keyword_text = " ".join(requirement.required_keywords)
        text = f"{requirement.raw_text or ''} {keyword_text}"

        if not any(keyword in text for keyword in ["보증", "무상보증", "A/S"]):
            return None

        year_match = re.search(r"보증\s*(\d+)\s*년\s*이상|(\d+)\s*년\s*이상\s*보증", text)
        if year_match:
            value = next(group for group in year_match.groups() if group)
            return int(value) * 12

        month_match = re.search(
            r"보증\s*(\d+)\s*개월\s*이상|(\d+)\s*개월\s*이상\s*보증",
            text,
        )
        if month_match:
            value = next(group for group in month_match.groups() if group)
            return int(value)

        return None

    def _calculate_installation_score(
        self,
        *,
        quote: QuoteDocument,
        check_required: list[str],
    ) -> float:
        notes = quote.notes_raw or ""
        compact_notes = re.sub(r"[\s|]+", "", notes)
        has_install_item = any(
            item.category == LineItemCategory.INSTALL
            for item in quote.line_items
        )

        if has_install_item and any(
            keyword in compact_notes
            for keyword in [
                "설치비:미포함",
                "설치비미포함",
                "설치비:별도",
                "설치비별도",
                "시공비별도",
            ]
        ):
            self._append_check(check_required, "설치비 포함 여부 문서 내 상충 확인 필요")
            return 100.0

        if "설치비 별도" in notes or "시공비 별도" in notes:
            check_required.append("설치비 별도")
            return 0.0

        if has_install_item:
            return 100.0

        if "설치" in notes or "시공" in notes:
            check_required.append("설치 범위 확인 필요")

        return 0.0

    def _find_partner(self, vendor_name: str) -> PartnerProfile | None:
        normalized = self._normalize_company_name(vendor_name)
        return self.partner_index.get(normalized)

    def _normalize_company_name(self, value: str) -> str:
        text = value or ""
        text = re.sub(r"\(주\)|㈜|주식회사|주\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[\s()\[\]{}.,·ㆍ/-]+", "", text)
        text = re.sub(r"[^0-9A-Za-z가-힣]", "", text)
        return text.lower()

    def _specialty_match_score(
        self,
        *,
        requirement: RequirementInfo,
        specialty_tags: list[str],
    ) -> float:
        requirement_text = self._build_requirement_keyword_text(requirement)
        score = 0.0

        for tag in specialty_tags:
            normalized_tag = self._normalize_keyword(tag)
            if normalized_tag and normalized_tag in requirement_text:
                score += 1.0

        return score

    def _build_requirement_keyword_text(self, requirement: RequirementInfo) -> str:
        parts = [
            requirement.request_summary or "",
            " ".join(requirement.required_keywords),
        ]
        for product in requirement.products:
            parts.extend(
                [
                    product.product_type or "",
                    product.display_type or "",
                    product.name or "",
                    product.raw_text or "",
                ]
            )
        return self._normalize_keyword(" ".join(parts))

    def _normalize_keyword(self, value: str) -> str:
        return re.sub(r"\s+", "", value or "").lower()

    def _price_gap_rate(
        self,
        candidate_price: int | None,
        lowest_price: int | None,
    ) -> float | None:
        if not candidate_price or not lowest_price:
            return None

        if lowest_price <= 0:
            return None

        return (candidate_price - lowest_price) / lowest_price

    def _response_speed_score(self, value: str | None) -> int:
        return {"fast": 3, "normal": 2, "slow": 1}.get((value or "").lower(), 0)

    def _financial_status_score(self, value: str | None) -> int:
        return {"good": 3, "normal": 2, "caution": 1, "bad": 0}.get((value or "").lower(), 0)

    def _clamp_score(self, score: float) -> float:
        return max(0.0, min(100.0, score))

    def _round_score(self, score: float) -> float:
        return round(self._clamp_score(score), 2)

    def _append_check(self, check_required: list[str], message: str) -> None:
        if message and message not in check_required:
            check_required.append(message)

    def _build_matched_rules(
        self,
        *,
        is_premium: bool,
        success_rate: float,
        response_speed: str | None,
    ) -> list[str]:
        rules = []
        if is_premium:
            rules.append("premium_partner")
        if success_rate >= 0.10:
            rules.append("high_success_rate")
        if (response_speed or "").lower() == "fast":
            rules.append("fast_response")
        return rules
