from services.explanation.azure_openai_explanation_provider import (
    AzureOpenAIExplanationProvider,
)
from services.explanation.base import ExplanationProvider
from services.explanation.template_explanation_provider import TemplateExplanationProvider


def create_explanation_provider(
    provider_type: str = "template",
    settings=None,
) -> ExplanationProvider:
    if provider_type == "template":
        return TemplateExplanationProvider()

    if provider_type in {"azure_openai", "azure"}:
        return AzureOpenAIExplanationProvider(settings=settings)

    raise ValueError(f"지원하지 않는 ExplanationProvider 타입입니다: {provider_type}")
