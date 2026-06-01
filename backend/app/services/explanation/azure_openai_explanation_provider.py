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
        fallback_to_template: bool = True,
    ) -> None:
        load_dotenv()

        self.endpoint = endpoint or getattr(settings, "azure_openai_endpoint", None) or os.getenv(
            "AZURE_OPENAI_ENDPOINT"
        )
        self.api_key = api_key or getattr(settings, "azure_openai_api_key", None) or os.getenv(
            "AZURE_OPENAI_API_KEY"
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
        self.fallback_to_template = fallback_to_template
        self.template_provider = TemplateExplanationProvider()

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
                "Azure OpenAI Chat 설정이 없습니다: " + ", ".join(missing)
            )

        try:
            from openai import AzureOpenAI
        except ImportError as e:
            raise RuntimeError(
                "openai 패키지가 설치되어 있지 않아 Azure OpenAI Chat을 사용할 수 없습니다."
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
                max_tokens=1000,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {
                        "role": "user",
                        "content": (
                            "다음 추천 결과만 근거로 대시보드용 추천 사유 JSON을 작성하세요.\n"
                            + json.dumps(payload, ensure_ascii=False)
                        ),
                    },
                ],
            )
            content = response.choices[0].message.content or ""
            parsed = json.loads(content)
            return self._to_result(
                parsed=parsed,
                recommendation_result=recommendation_result,
                raw_response=content,
            )
        except Exception as e:
            if self.fallback_to_template:
                fallback = self.template_provider.generate(recommendation_result)
                fallback.provider = "azure_openai_fallback_template"
                fallback.warnings.append(
                    f"Azure OpenAI 추천 사유 생성 실패로 템플릿 결과를 사용했습니다: {e}"
                )
                return fallback

            raise RuntimeError(f"Azure OpenAI 추천 사유 생성 실패: {e}") from e

    def _to_result(
        self,
        *,
        parsed: dict[str, Any],
        recommendation_result: RecommendationPipelineResult,
        raw_response: str,
    ) -> RecommendationExplanationResult:
        items_by_quote_id = {
            item.quote_id: item
            for item in recommendation_result.items[:3]
        }
        supplier_explanations = []

        for raw_supplier in parsed.get("supplier_explanations", []):
            quote_id = str(raw_supplier.get("quote_id", ""))
            item = items_by_quote_id.get(quote_id)
            if item is None:
                continue

            supplier_explanations.append(
                SupplierExplanation(
                    quote_id=item.quote_id,
                    vendor_name=item.vendor_name,
                    rank=item.rank,
                    card_summary=self._clean_text(
                        str(raw_supplier.get("card_summary", ""))
                    )[:300],
                    strengths=self._clean_list(
                        raw_supplier.get("strengths", []),
                        default="비교 검토 가능",
                    ),
                    weaknesses=self._clean_list(
                        raw_supplier.get("weaknesses", []),
                        default="특이 리스크 없음",
                    ),
                    check_required=item.check_required,
                    metadata={
                        "provider": "azure_openai",
                        "filter_reasons": item.filter_reasons,
                    },
                )
            )

        if len(supplier_explanations) != len(recommendation_result.items[:3]):
            template_result = self.template_provider.generate(recommendation_result)
            existing_quote_ids = {item.quote_id for item in supplier_explanations}
            for supplier in template_result.supplier_explanations:
                if supplier.quote_id not in existing_quote_ids:
                    supplier_explanations.append(supplier)

        return RecommendationExplanationResult(
            request_id=recommendation_result.request_id,
            customer_name=recommendation_result.customer_name,
            overall_summary=self._clean_text(
                str(parsed.get("overall_summary", ""))
            )[:1200],
            supplier_explanations=supplier_explanations[:3],
            provider="azure_openai",
            warnings=[],
            metadata={
                "deployment": self.deployment,
                "api_version": self.api_version,
                "raw_response_preview": raw_response[:500],
            },
        )

    def _system_prompt(self) -> str:
        return (
            "너는 견적 비교 대시보드의 추천 사유 작성 도우미다.\n"
            "너는 점수 계산을 하지 않는다.\n"
            "너는 순위를 변경하지 않는다.\n"
            "너는 입력에 없는 스펙, 금액, 납기, 보증 정보를 추정하지 않는다.\n"
            "미기재 또는 확인 필요 항목은 반드시 확인 필요로 표현한다.\n"
            "응답은 반드시 JSON 형식으로만 작성한다.\n"
            "supplier_explanations의 quote_id, vendor_name, rank는 입력과 동일해야 한다.\n"
            "입력에 없는 업체를 추가하지 않는다.\n"
            "items 순서를 바꾸지 않는다.\n"
            "점수 수치를 바꾸지 않는다.\n"
            "완벽한, 압도적, 최고 같은 과장 표현은 쓰지 않는다.\n"
            "overall_summary는 Top 3 업체 비교 요약 3~5문장으로 제한한다.\n"
            "card_summary는 1문장으로 제한한다.\n"
            "strengths와 weaknesses는 각각 최대 3개다.\n"
            "출력 스키마: "
            '{"overall_summary":"...","supplier_explanations":[{"quote_id":"...",'
            '"vendor_name":"...","rank":1,"card_summary":"...","strengths":["..."],'
            '"weaknesses":["..."]}]}'
        )

    def _clean_list(self, value: Any, *, default: str) -> list[str]:
        if not isinstance(value, list):
            return [default]

        cleaned = [
            self._clean_text(str(item))[:120]
            for item in value
            if str(item).strip()
        ]
        return cleaned[:3] or [default]

    def _clean_text(self, text: str) -> str:
        replacements = {
            "완벽한": "높은",
            "완벽하게": "높게",
            "완벽": "충분",
            "완전한": "높은",
            "완전": "높음",
            "최고 수준": "높은 수준",
            "최고의": "높은",
            "만점": "100점",
            "압도적": "우수",
        }
        cleaned = text.strip()
        for source, target in replacements.items():
            cleaned = cleaned.replace(source, target)
        return cleaned
