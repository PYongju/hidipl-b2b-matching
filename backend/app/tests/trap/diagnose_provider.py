"""
진단: 채점기가 조용히 폴백한 '진짜 이유'를 꺼내 본다.
실행: (backend/app 에서)  python -m tests.trap.diagnose_provider
"""
from tests.trap.baseline_loader import get_normal_result
from services.explanation.factory import create_explanation_provider
from services.config import get_settings


def main() -> None:
    settings = get_settings()
    # 올바른 호출: (provider_type 문자열, settings, capture_raw_output)
    provider = create_explanation_provider(
        "azure_openai",
        settings,
        capture_raw_output=True,
    )
    print("provider type:", type(provider).__name__)

    # M-02 정상본으로 직접 1회 호출
    result = get_normal_result("M-02")
    explanation = provider.generate(result)

    print("\n=== 결과 ===")
    print("provider 필드:", getattr(explanation, "provider", "?"))
    md = getattr(explanation, "metadata", {}) or {}
    print("fallback_reason     :", md.get("fallback_reason"))
    print("fallback_error_type :", md.get("fallback_error_type"))
    for w in (getattr(explanation, "warnings", []) or []):
        print("warning:", w)

    text = getattr(explanation, "text", None) or getattr(explanation, "explanation", None)
    if text:
        print("\n=== 생성 텍스트(앞 300자) ===")
        print(text[:300])


if __name__ == "__main__":
    main()
