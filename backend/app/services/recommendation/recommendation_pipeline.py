from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any

from services.quote_ingestion.schemas import QuoteIngestionResult
from services.ranking.schemas import RankingCandidate, RankingResult
from services.recommendation.schemas import (
    RecommendationItem,
    RecommendationPipelineResult,
)
from services.requirement_ingestion.schemas import RequirementIngestionResult


class RecommendationPipeline:
    def __init__(
        self,
        ranking_provider,
    ) -> None:
        self.ranking_provider = ranking_provider

    def recommend(
        self,
        requirement_result: RequirementIngestionResult,
        quote_results: list[QuoteIngestionResult],
        *,
        selected_partner_names: list[str] | None = None,
        top_n: int = 3,
    ) -> RecommendationPipelineResult:
        if not quote_results:
            raise ValueError("추천 대상 견적서 결과가 없습니다.")

        requirement = requirement_result.requirement
        candidates: list[RankingCandidate] = []
        failed_candidates: list[dict[str, str]] = []

        selected_normalized = {
            self._normalize_company_name(name)
            for name in (selected_partner_names or [])
            if name
        }
        filtered_quote_results = quote_results
        if selected_normalized:
            matched_quote_results = [
                quote_result
                for quote_result in quote_results
                if self._normalize_company_name(quote_result.quote.vendor_name)
                in selected_normalized
            ]
            if matched_quote_results:
                filtered_quote_results = matched_quote_results

        for quote_result in filtered_quote_results:
            try:
                candidate = self._quote_result_to_candidate(quote_result)
                candidates.append(candidate)
            except Exception as e:
                failed_candidates.append(
                    {
                        "quote_id": str(getattr(quote_result, "quote_id", "") or ""),
                        "source_file_path": str(
                            getattr(quote_result, "source_file_path", "") or ""
                        ),
                        "error": str(e),
                    }
                )

        if not candidates:
            raise ValueError("ranking 가능한 견적 후보가 없습니다.")

        ranking_summary = self.ranking_provider.rank(
            requirement=requirement,
            requirement_embedding_vector=requirement_result.embedding_vector,
            candidates=candidates,
            top_n=top_n,
        )

        all_items = [
            self._ranking_result_to_item(result)
            for result in ranking_summary.all_results
        ]
        filtered_candidates = [
            {
                "quote_id": item.quote_id,
                "vendor_name": str(item.vendor_name or ""),
                "filter_reasons": ", ".join(item.filter_reasons),
            }
            for item in all_items
            if not item.business_rule_passed
        ]

        return RecommendationPipelineResult(
            request_id=requirement_result.request_id,
            customer_name=requirement.customer_name,
            top_n=top_n,
            items=[
                self._ranking_result_to_item(result)
                for result in ranking_summary.results
            ],
            all_items=all_items,
            failed_candidates=failed_candidates,
            filtered_candidates=filtered_candidates,
            metadata={
                "ranking_provider": self.ranking_provider.__class__.__name__,
                "candidate_count": len(candidates),
                "failed_candidate_count": len(failed_candidates),
                "filtered_candidate_count": len(filtered_candidates),
                "selected_partner_names": selected_partner_names or [],
                "selected_partner_filter_applied": (
                    bool(selected_normalized)
                    and len(filtered_quote_results) < len(quote_results)
                ),
            },
        )

    def to_storage_dict(self, result: RecommendationPipelineResult) -> dict[str, Any]:
        return self._to_jsonable(asdict(result))

    def _quote_result_to_candidate(
        self,
        quote_result: QuoteIngestionResult,
    ) -> RankingCandidate:
        quote_document = quote_result.quote

        if quote_document is None:
            raise ValueError("QuoteDocument가 없습니다.")

        quote_id = quote_result.quote_id or quote_document.quote_id
        if not quote_id:
            raise ValueError("quote_id가 없습니다.")

        if not quote_document.vendor_name and not quote_document.line_items:
            raise ValueError("유효하지 않은 QuoteDocument입니다.")

        return RankingCandidate(
            quote_id=quote_id,
            quote_document=quote_document,
            quote_embedding_vector=quote_result.embedding_vector,
            source_file_path=quote_result.source_file_path,
            metadata=quote_result.metadata,
        )

    def _ranking_result_to_item(self, result: RankingResult) -> RecommendationItem:
        quote = result.quote_document

        return RecommendationItem(
            rank=result.rank,
            quote_id=result.quote_id,
            partner_name=result.partner_name,
            partner_found=result.partner_found,
            is_premium=result.is_premium,
            success_rate=result.success_rate,
            response_speed=result.response_speed,
            financial_status=result.financial_status,
            business_rule_passed=result.business_rule_passed,
            business_stage=result.business_stage,
            filter_reasons=result.filter_reasons,
            business_sort_key=result.business_sort_key,
            vendor_name=quote.vendor_name,
            project_name=quote.project_name,
            source_file_path=quote.source_file_path or result.metadata.get("source_file_path"),
            final_score=result.final_score,
            spec_score=result.spec_score,
            price_score=result.price_score,
            delivery_score=result.delivery_score,
            warranty_score=result.warranty_score,
            installation_score=result.installation_score,
            cosine_similarity=result.cosine_similarity,
            total_supply_price=quote.total_supply_price,
            total_with_vat=quote.total_with_vat,
            delivery_weeks=quote.delivery_weeks,
            delivery_basis_raw=quote.delivery_basis_raw,
            warranty_months=quote.warranty_months,
            line_item_count=len(quote.line_items),
            check_required=result.check_required,
            score_breakdown=result.score_breakdown,
            rule_warnings=list(result.metadata.get("rule_warnings", [])),
            matched_rules=list(result.metadata.get("matched_rules", [])),
            vendor_snapshot_source=result.metadata.get("vendor_snapshot_source"),
            vendor_snapshot_summary=self._vendor_snapshot_summary(quote),
            metadata=result.metadata,
        )

    def _vendor_snapshot_summary(self, quote) -> dict[str, Any]:
        snapshot = getattr(quote, "vendor_snapshot", None)
        if snapshot is None:
            return {}
        return {
            "vendor_name": snapshot.vendor_name,
            "is_premium_partner": snapshot.is_premium_partner,
            "past_success_rate": snapshot.past_success_rate,
            "response_speed_score": snapshot.response_speed_score,
            "response_speed": snapshot.response_speed,
            "financial_status": snapshot.financial_status,
            "is_excluded": snapshot.is_excluded,
            "specialty_tags": snapshot.specialty_tags,
            "source": snapshot.source,
        }

    def _normalize_company_name(self, value: str | None) -> str:
        import re

        text = value or ""
        text = text.replace("㈜", "")
        text = re.sub(r"\(주\)|주식회사|주\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[^0-9A-Za-z가-힣]", "", text)
        return text.lower()

    def _to_jsonable(self, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, dict):
            return {key: self._to_jsonable(item) for key, item in value.items()}

        if isinstance(value, list):
            return [self._to_jsonable(item) for item in value]

        return value
