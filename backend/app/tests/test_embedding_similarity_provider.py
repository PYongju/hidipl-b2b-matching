import os
from datetime import datetime

from dotenv import load_dotenv

from services.embedding.factory import create_embedding_provider
from services.embedding.text_builder import (
    build_quote_embedding_text,
    build_requirement_embedding_text,
)
from services.parser.schemas import LineItem, LineItemCategory, QuoteDocument
from services.requirement.schemas import RequirementInfo, RequirementProduct
from services.similarity.factory import create_similarity_provider


def main() -> None:
    load_dotenv()

    missing = [
        name
        for name in [
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        ]
        if not os.getenv(name)
    ]
    if missing:
        print("Azure OpenAI Embedding 설정이 없어 테스트를 건너뜁니다.")
        print("필요한 환경변수: " + ", ".join(missing))
        return

    requirement = _build_sample_requirement()
    quote_a = _build_quote_a()
    quote_b = _build_quote_b()

    requirement_text = build_requirement_embedding_text(requirement)
    quote_a_text = build_quote_embedding_text(quote_a)
    quote_b_text = build_quote_embedding_text(quote_b)

    print("\n========== Requirement embedding text ==========")
    print(requirement_text)
    print("\n========== Quote A embedding text ==========")
    print(quote_a_text)
    print("\n========== Quote B embedding text ==========")
    print(quote_b_text)

    try:
        embedding_provider = create_embedding_provider("azure_openai")
    except RuntimeError as e:
        print(f"\nEmbeddingProvider를 생성할 수 없어 테스트를 건너뜁니다: {e}")
        return

    similarity_provider = create_similarity_provider("cosine")

    try:
        requirement_vector = embedding_provider.embed_text(requirement_text)
        quote_a_vector = embedding_provider.embed_text(quote_a_text)
        quote_b_vector = embedding_provider.embed_text(quote_b_text)
    except RuntimeError as e:
        print(f"\nEmbedding API 호출에 실패해 테스트를 건너뜁니다: {e}")
        return

    score_a = similarity_provider.calculate(requirement_vector, quote_a_vector)
    score_b = similarity_provider.calculate(requirement_vector, quote_b_vector)

    print(f"\nSimilarity score A: {score_a.score:.2f}")
    print(f"Similarity score B: {score_b.score:.2f}")
    print(f"A가 B보다 높은지 여부: {score_a.score > score_b.score}")


def _build_sample_requirement() -> RequirementInfo:
    return RequirementInfo(
        raw_text="",
        customer_name="스노우스페이스",
        request_summary="커브드 LED전광판 + 평면 LED전광판",
        products=[
            RequirementProduct(
                product_type="LED 전광판",
                display_type="커브드",
                name="커브드 LED 전광판",
                width_mm=12000,
                height_mm=3000,
                pitch_max_mm=2.5,
                raw_text="커브드 LED 전광판 12000x3000 Pitch 2.5 이하",
            ),
            RequirementProduct(
                product_type="LED 전광판",
                display_type="플랫",
                name="플랫 LED 전광판",
                width_mm=7150,
                height_mm=2700,
                pitch_max_mm=2.5,
                raw_text="플랫 LED 전광판 7150x2700 Pitch 2.5 이하",
            ),
        ],
        region="서울 홍대(동교동)",
        install_schedule_text="2월말~3월초",
        required_keywords=["LED 전광판", "커브드", "평면", "설치"],
    )


def _build_quote_a() -> QuoteDocument:
    return QuoteDocument(
        vendor_name="A파트너",
        quote_id="quote_a",
        received_at=datetime(2026, 5, 26),
        project_name="스노우스페이스 LED 구축",
        total_supply_price=80000000,
        total_with_vat=None,
        delivery_weeks=None,
        warranty_months=12,
        notes_raw="설치 포함",
        line_items=[
            LineItem(
                name="커브드 LED 전광판",
                category=LineItemCategory.DISPLAY,
                quantity=1,
                unit="식",
                unit_price=None,
                total_price=50000000,
                spec_raw="12,000 x 3,000 Pitch 2.5 이하 설치 포함",
                spec_parsed={
                    "full_screen_size_mm": "12,000 x 3,000",
                    "pitch_mm": 2.5,
                },
            ),
            LineItem(
                name="플랫 LED 전광판",
                category=LineItemCategory.DISPLAY,
                quantity=1,
                unit="식",
                unit_price=None,
                total_price=30000000,
                spec_raw="7,150 x 2,700 Pitch 2.5 이하 설치 포함",
                spec_parsed={
                    "full_screen_size_mm": "7,150 x 2,700",
                    "pitch_mm": 2.5,
                },
            ),
        ],
    )


def _build_quote_b() -> QuoteDocument:
    return QuoteDocument(
        vendor_name="B파트너",
        quote_id="quote_b",
        received_at=datetime(2026, 5, 26),
        project_name="회의실 프로젝터 설치",
        total_supply_price=30000000,
        total_with_vat=None,
        delivery_weeks=None,
        warranty_months=None,
        line_items=[
            LineItem(
                name="회의실 프로젝터",
                category=LineItemCategory.ETC,
                quantity=1,
                unit="식",
                unit_price=None,
                total_price=30000000,
                spec_raw="프로젝터 및 스크린 설치",
            )
        ],
    )


if __name__ == "__main__":
    main()
