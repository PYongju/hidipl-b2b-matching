import json
import os
from dataclasses import asdict
from typing import Any

from dotenv import load_dotenv

from services.explanation.base import ExplanationProvider
from services.explanation.explanation_input_builder import build_explanation_input
from services.explanation.explanation_text_policy import (
    clean_text,
    decision_weaknesses,
    has_risk,
    is_parser_quality_issue,
    split_comparison_risks,
    trim_sentence,
)
from services.explanation.schemas import (
    RecommendationExplanationResult,
    SupplierExplanation,
)
from services.explanation.template_explanation_provider import TemplateExplanationProvider
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
                            "아래 추천 결과만 근거로 견적 비교 대시보드용 설명 JSON을 작성하세요.\n"
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

        overall_summary = self._sanitize_overall_summary(
            str(parsed.get("overall_summary", ""))
        )
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
        check_required, comparison_risks = split_comparison_risks(
            item.check_required,
            item.comparison_risks,
            item.rule_warnings,
        )
        return SupplierExplanation(
            quote_id=item.quote_id,
            vendor_name=item.vendor_name,
            rank=item.rank,
            card_summary=self._build_card_summary(
                item,
                str(raw_supplier.get("card_summary", "")),
            ),
            strengths=self._sanitize_strengths(
                self._clean_list(raw_supplier.get("strengths", []), default=None),
                item,
            ),
            weaknesses=self._merge_weaknesses(
                llm_weaknesses=self._clean_list(
                    raw_supplier.get("weaknesses", []),
                    default=None,
                ),
                item=item,
            ),
            check_required=check_required,
            metadata=self._build_supplier_metadata(
                item,
                provider="azure_openai",
                llm_used=True,
                fallback_used=False,
                comparison_risks=comparison_risks,
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
        comparison_risks: list[str] | None = None,
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
            "comparison_risks": comparison_risks or [],
        }

    def _merge_weaknesses(self, *, llm_weaknesses: list[str], item) -> list[str]:
        return decision_weaknesses(
            llm_weaknesses=llm_weaknesses,
            check_required=item.check_required,
            comparison_risks=item.comparison_risks,
            filter_reasons=item.filter_reasons,
            limit=2,
        )

    def _system_prompt(self) -> str:
        return (
            "당신은 견적 비교 대시보드의 추천 근거를 작성합니다.\n"
            "반드시 지킬 것:\n"
            "- 입력된 ranking 결과와 점수를 다시 계산하지 마세요.\n"
            "- 순위를 바꾸지 마세요.\n"
            "- 입력에 없는 사실을 만들지 마세요.\n"
            "- check_required는 견적서 자체의 확인 필요 항목입니다.\n"
            "- comparison_risks는 후보 간 상대 비교에서 생긴 리스크입니다.\n"
            "- parser_quality_notes는 설명에 사용하지 마세요.\n"
            "- '프로젝트명이 파일명 기준으로 보정됨' 같은 Parser 내부 메시지는 summary, card_summary, strengths, weaknesses에 쓰지 마세요.\n"
            "- '가격 차이 5% 초과'는 check_required가 아니라 comparison_risks로 해석하세요.\n"
            "- 납기 정보가 미기재이거나 별도협의이면 '납기 우수', '납기 명확'이라고 쓰지 마세요.\n"
            "- 설치 범위 확인이 필요하면 '설치 조건 우수'라고 단정하지 마세요.\n"
            "- comparison_risks는 weaknesses 후보로 사용할 수 있습니다.\n"
            "- overall_summary는 2~3문장으로 간결하게 작성하세요.\n"
            "- card_summary는 1문장으로 작성하세요.\n"
            "- strengths는 최대 2개, weaknesses는 최대 2개로 작성하세요.\n"
            "- 사용자가 한눈에 비교할 수 있도록 가격, 사양, 납기, 보증, 설치 조건 중심으로 작성하세요.\n"
            "- JSON만 반환하세요.\n"
            "출력 스키마: "
            '{"overall_summary":"...","supplier_explanations":[{"quote_id":"...",'
            '"vendor_name":"...","rank":1,"card_summary":"...","strengths":["..."],'
            '"weaknesses":["..."]}]}'
        )

    def _clean_list(self, value: Any, *, default: str | None) -> list[str]:
        if not isinstance(value, list):
            return [default] if default else []

        cleaned = [self._clean_text(str(item))[:120] for item in value if str(item).strip()]
        if cleaned:
            return cleaned[:2]
        return [default] if default else []

    def _clean_text(self, text: str) -> str:
        return clean_text(text)

    def _sanitize_strengths(self, strengths: list[str], item) -> list[str]:
        result: list[str] = []
        delivery_uncertain = has_risk(item.check_required, "납기 정보 미기재") or has_risk(
            item.check_required, "납기 별도협의"
        )
        installation_uncertain = any(
            "설치" in message and "확인" in message for message in item.check_required
        )
        for strength in strengths:
            cleaned = self._clean_text(strength)
            if not cleaned or is_parser_quality_issue(cleaned):
                continue
            if delivery_uncertain and self._claims_uncertain_advantage(cleaned, "납기"):
                continue
            if installation_uncertain and self._claims_uncertain_advantage(cleaned, "설치"):
                continue
            if cleaned not in result:
                result.append(cleaned)
            if len(result) >= 2:
                break
        return result or ["비교 검토 가능"]

    def _build_card_summary(self, item, llm_summary: str) -> str:
        summary = self._clean_text(llm_summary)
        if is_parser_quality_issue(summary):
            summary = ""
        if (
            has_risk(item.check_required, "납기 정보 미기재")
            or has_risk(item.check_required, "납기 별도협의")
        ) and self._claims_uncertain_advantage(summary, "납기"):
            summary = ""
        if not summary:
            if item.rank == 1:
                summary = "종합 점수가 가장 높은 추천 견적입니다."
            elif item.delivery_weeks and not has_risk(item.check_required, "납기 정보 미기재"):
                summary = "납기는 명확하지만 조건 확인이 필요합니다."
            else:
                summary = "가격과 조건 확인이 필요한 비교 후보입니다."
        return trim_sentence(summary, max_chars=55)

    def _claims_uncertain_advantage(self, text: str, subject: str) -> bool:
        return subject in text and any(
            token in text for token in ["우수", "최고", "명확", "경쟁력", "강점"]
        )

    def _sanitize_overall_summary(self, summary: str) -> str:
        cleaned = self._clean_text(summary)
        if not cleaned or is_parser_quality_issue(cleaned):
            return ""
        sentences = [
            sentence.strip()
            for sentence in cleaned.replace("?", "?.").split(".")
            if sentence.strip() and not is_parser_quality_issue(sentence)
        ]
        if not sentences:
            return ""
        return ". ".join(sentences[:3]).rstrip(".") + "."
