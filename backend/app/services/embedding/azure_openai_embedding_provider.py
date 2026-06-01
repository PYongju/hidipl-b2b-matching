import os

from services.embedding.base import EmbeddingProvider


class AzureOpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
    ) -> None:
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment = deployment or os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        self.api_version = (
            api_version
            or os.getenv("AZURE_OPENAI_API_VERSION")
            or "2025-01-01-preview"
        )

        missing = [
            name
            for name, value in [
                ("AZURE_OPENAI_ENDPOINT", self.endpoint),
                ("AZURE_OPENAI_API_KEY", self.api_key),
                ("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", self.deployment),
            ]
            if not value
        ]
        if missing:
            raise ValueError(
                "Azure OpenAI Embedding 설정이 없습니다: " + ", ".join(missing)
            )

        try:
            from openai import AzureOpenAI
        except ImportError as e:
            raise RuntimeError(
                "openai 패키지가 설치되어 있지 않아 Azure OpenAI Embedding을 사용할 수 없습니다."
            ) from e

        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
        )

    def embed_text(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("Embedding 대상 text가 비어 있습니다.")

        try:
            response = self.client.embeddings.create(
                model=self.deployment,
                input=text,
            )
            return list(response.data[0].embedding)
        except Exception as e:
            raise RuntimeError(f"Azure OpenAI Embedding API 호출 실패: {e}") from e
