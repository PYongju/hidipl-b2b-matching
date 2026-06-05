import json
import os
from dataclasses import asdict
from typing import Any

from dotenv import load_dotenv

from services.explanation.base import ExplanationProvider
from services.explanation.explanation_input_builder import build_explanation_input
from services.explanation.schemas import (
    RecommendationExplanationResult,
    SupplierExplanation,
)
from services.explanation.template_explanation_provider import (
    TemplateExplanationProvider,
)
from services.recommendation.schemas import RecommendationPipelineResult


class AzureOpenAIExplanationProvider(ExplanationProvider):
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
        *,
        settings=None,
        client=None,
        fallback_to_template: bool = True,
        max_tokens: int | None = None,
    ) -> None:
        load_dotenv()

        self.endpoint = (
            endpoint
            or getattr(settings, "azure_openai_endpoint", None)
            or os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.api_key = (
            api_key
            or getattr(settings, "azure_openai_api_key", None)
            or os.getenv("AZURE_OPENAI_API_KEY")
        )
        self.deployment = (
            deployment
            or getattr(settings, "azure_openai_chat_deployment", None)
            or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
        )
        self.api_version = (
            api_version
            or getattr(settings, "azure_openai_chat_api_version", None)
            or os.getenv("AZURE_OPENAI_CHAT_API_VERSION")
            or os.getenv("AZURE_OPENAI_API_VERSION")
            or "2025-01-01-preview"
        )
        self.max_tokens = int(
            max_tokens
            or getattr(settings, "azure_openai_explanation_max_tokens", None)
            or os.getenv("AZURE_OPENAI_EXPLANATION_MAX_TOKENS")
            or 2000
        )
        self.fallback_to_template = fallback_to_template
        self.template_provider = TemplateExplanationProvider()

        if client is not None:
            self.client = client
            return

        missing = [
            name
            for name, value in [
                ("AZURE_OPENAI_ENDPOINT", self.endpoint),
                ("AZURE_OPENAI_API_KEY", self.api_key),
                ("AZURE_OPENAI_CHAT_DEPLOYMENT", self.deployment),
            ]
            if not value
        ]
        if missing:
            raise ValueError(
                "Azure OpenAI Chat settings are missing: " + ", ".join(missing)
            )

        try:
            from openai import AzureOpenAI
        except ImportError as e:
            raise RuntimeError(
                "openai package is required for Azure OpenAI Chat."
            ) from e

        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
        )

    def generate(
        self,
        recommendation_result: RecommendationPipelineResult,
    ) -> RecommendationExplanationResult:
        explanation_input = build_explanation_input(recommendation_result)
        payload = asdict(explanation_input)

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                temperature=0.2,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {
                        "role": "user",
                        "content": (
                            "Create dashboard-facing recommendation explanation JSON "
                            "from this recommendation result only.\n"
                            + json.dumps(payload, ensure_ascii=False)
                        ),
                    },
                ],
            )
            choice = response.choices[0]
            finish_reason = getattr(choice, "finish_reason", None)
            if finish_reason == "length":
                raise RuntimeError(
                    "Azure OpenAI response truncated: finish_reason=length"
                )

            content = choice.message.content or ""
            parsed = json.loads(content)
            return self._to_result(
                parsed=parsed,
                recommendation_result=recommendation_result,
                raw_response=content,
                finish_reason=finish_reason,
            )
        except Exception as e:
            if self.fallback_to_template:
                fallback = self.template_provider.generate(recommendation_result)
                fallback.provider = "azure_openai_fallback_template"
                fallback.warnings.append(
                    f"Azure OpenAI explanation generation failed; template fallback used: {e}"
                )
                fallback.metadata["fallback_reason"] = str(e)
                fallback.metadata["max_tokens"] = self.max_tokens
                return fallback

            raise RuntimeError(
                f"Azure OpenAI explanation generation failed: {e}"
            ) from e

    def _to_result(
        self,
        *,
        parsed: dict[str, Any],
        recommendation_result: RecommendationPipelineResult,
        raw_response: str,
        finish_reason: str | None = None,
    ) -> RecommendationExplanationResult:
        expected_items = recommendation_result.items[:3]
        expected_quote_ids = {item.quote_id for item in expected_items}
        template_result = self.template_provider.generate(recommendation_result)
        template_by_quote_id = {
            supplier.quote_id: supplier
            for supplier in template_result.supplier_explanations
        }

        parsed_suppliers_by_quote_id: dict[str, dict[str, Any]] = {}
        duplicate_quote_ids: list[str] = []
        unknown_quote_ids: list[str] = []

        for raw_supplier in parsed.get("supplier_explanations", []):
            if not isinstance(raw_supplier, dict):
                continue
            quote_id = str(raw_supplier.get("quote_id", "")).strip()
            if not quote_id:
                continue
            if quote_id not in expected_quote_ids:
                unknown_quote_ids.append(quote_id)
                continue
            if quote_id in parsed_suppliers_by_quote_id:
                duplicate_quote_ids.append(quote_id)
                continue
            parsed_suppliers_by_quote_id[quote_id] = raw_supplier

        supplier_explanations: list[SupplierExplanation] = []
        missing_quote_ids: list[str] = []
        for item in expected_items:
            raw_supplier = parsed_suppliers_by_quote_id.get(item.quote_id)
            if raw_supplier:
                supplier_explanations.append(
                    self._build_supplier_from_llm(item, raw_supplier)
                )
                continue

            missing_quote_ids.append(item.quote_id)
            template_supplier = template_by_quote_id.get(item.quote_id)
            if template_supplier is not None:
                supplier_explanations.append(
                    self._mark_template_supplier_fallback(
                        template_supplier,
                        "missing_llm_supplier_explanation",
                    )
                )

        warnings = []
        if duplicate_quote_ids:
            warnings.append(
                "Duplicate LLM supplier quote_ids ignored: "
                + ", ".join(dict.fromkeys(duplicate_quote_ids))
            )
        if unknown_quote_ids:
            warnings.append(
                "Unknown LLM supplier quote_ids ignored: "
                + ", ".join(dict.fromkeys(unknown_quote_ids))
            )
        if missing_quote_ids:
            warnings.append(
                "Missing LLM supplier explanations filled by template: "
                + ", ".join(missing_quote_ids)
            )
        if finish_reason:
            warnings.append(f"Azure OpenAI finish_reason: {finish_reason}")

        overall_summary = self._clean_text(str(parsed.get("overall_summary", "")))[
            :1200
        ]
        if len(overall_summary) < 10:
            overall_summary = template_result.overall_summary
            warnings.append("LLM overall_summary was empty; template summary used.")

        return RecommendationExplanationResult(
            request_id=recommendation_result.request_id,
            customer_name=recommendation_result.customer_name,
            overall_summary=overall_summary,
            supplier_explanations=supplier_explanations[:3],
            provider="azure_openai",
            warnings=warnings,
            metadata={
                "deployment": self.deployment,
                "api_version": self.api_version,
                "max_tokens": self.max_tokens,
                "finish_reason": finish_reason,
                "duplicate_quote_ids": list(dict.fromkeys(duplicate_quote_ids)),
                "unknown_quote_ids": list(dict.fromkeys(unknown_quote_ids)),
                "missing_quote_ids": missing_quote_ids,
                "raw_response_preview": raw_response[:500],
            },
        )

    def _build_supplier_from_llm(
        self, item, raw_supplier: dict[str, Any]
    ) -> SupplierExplanation:
        return SupplierExplanation(
            quote_id=item.quote_id,
            vendor_name=item.vendor_name,
            rank=item.rank,
            card_summary=self._clean_text(str(raw_supplier.get("card_summary", "")))[
                :300
            ],
            strengths=self._clean_list(
                raw_supplier.get("strengths", []),
                default="비교 검토 가능",
            ),
            weaknesses=self._merge_weaknesses(
                llm_weaknesses=self._clean_list(
                    raw_supplier.get("weaknesses", []),
                    default=None,
                ),
                item=item,
            ),
            check_required=item.check_required,
            metadata=self._build_supplier_metadata(
                item,
                provider="azure_openai",
                llm_used=True,
                fallback_used=False,
            ),
        )

    def _mark_template_supplier_fallback(
        self,
        supplier: SupplierExplanation,
        fallback_reason: str,
    ) -> SupplierExplanation:
        metadata = {
            **supplier.metadata,
            "provider": "template",
            "llm_used": False,
            "fallback_used": True,
            "fallback_reason": fallback_reason,
        }
        return SupplierExplanation(
            quote_id=supplier.quote_id,
            vendor_name=supplier.vendor_name,
            rank=supplier.rank,
            card_summary=supplier.card_summary,
            strengths=supplier.strengths,
            weaknesses=supplier.weaknesses,
            check_required=supplier.check_required,
            metadata=metadata,
        )

    def _build_supplier_metadata(
        self,
        item,
        *,
        provider: str,
        llm_used: bool,
        fallback_used: bool,
    ) -> dict[str, Any]:
        return {
            "provider": provider,
            "final_score": item.final_score,
            "spec_score": item.spec_score,
            "price_score": item.price_score,
            "delivery_score": item.delivery_score,
            "warranty_score": item.warranty_score,
            "installation_score": item.installation_score,
            "business_rule_passed": item.business_rule_passed,
            "filter_reasons": item.filter_reasons,
            "llm_used": llm_used,
            "fallback_used": fallback_used,
        }

    def _merge_weaknesses(self, *, llm_weaknesses: list[str], item) -> list[str]:
        candidates = [
            *llm_weaknesses,
            *item.check_required,
            *item.filter_reasons,
        ]
        deduped = []
        for weakness in candidates:
            cleaned = self._clean_text(str(weakness))[:120]
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)
        return deduped[:3] or ["특이 리스크 없음"]

    def _system_prompt(self) -> str:
        return (
            "당신은 대시보드에 표시될 견적 추천 설명을 작성하는 역할입니다.\n"
            "점수, 순위, 가격, 납기, 보증기간, 설치 조건과 관련된 사실을 다시 계산하지 마세요.\n"
            "입력에 없는 업체명, 금액, 점수, 납기, 보증기간, 설치 조건을 새로 만들어내지 마세요.\n"
            "추천 순서를 변경하지 마세요. 입력으로 제공된 quote_id, vendor_name, rank만 사용하세요.\n"
            "quote_id는 입력으로 제공된 값만 사용하고, 중복하거나 누락하지 마세요.\n"
            "반드시 JSON만 반환하세요.\n"
            "입력 데이터에 check_required 또는 filter_reasons가 있는 경우, 해당 내용을 weaknesses에 반영하세요.\n"
            "overall_summary는 상위 3개 업체를 3~5개의 한국어 문장으로 요약해야 합니다.\n"
            "card_summary는 간결한 한국어 한 문장으로 작성해야 합니다.\n"
            "strengths와 weaknesses는 각각 최대 3개 항목까지만 작성하세요.\n"
            "출력 스키마: "
            '{"overall_summary":"...","supplier_explanations":[{"quote_id":"...",'
            '"vendor_name":"...","rank":1,"card_summary":"...","strengths":["..."],'
            '"weaknesses":["..."]}]}'
        )

    def _clean_list(self, value: Any, *, default: str | None) -> list[str]:
        if not isinstance(value, list):
            return [default] if default else []

        cleaned = [
            self._clean_text(str(item))[:120] for item in value if str(item).strip()
        ]
        if cleaned:
            return cleaned[:3]
        return [default] if default else []

    def _clean_text(self, text: str) -> str:
        replacements = {
            "과도히": "높이",
            "과도하게": "높게",
            "과도": "충분",
            "완전히": "높이",
            "완전": "높음",
            "최고 수준": "높은 수준",
            "최고의": "높은",
            "만점": "100점",
            "정도도": "점수",
        }
        cleaned = text.strip()
        for source, target in replacements.items():
            cleaned = cleaned.replace(source, target)
        return cleaned
