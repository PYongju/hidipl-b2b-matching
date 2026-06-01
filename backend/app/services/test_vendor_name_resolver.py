from datetime import datetime

from config.paths import DATA_DIR
from services.parser.schemas import QuoteDocument
from services.parser.vendor_name_resolver import (
    VendorNameResolver,
    is_invalid_vendor_name,
    normalize_company_name,
)
from services.quote_ingestion.quote_ingestion_pipeline import QuoteIngestionPipeline


def test_hyosung_itx() -> None:
    source_text = """HYOSUNG ITX
서울시 ...
효성ITX 주식회사
대표이사 ...
"""
    resolver = VendorNameResolver()
    vendor_name, debug = resolver.resolve(
        current_vendor_name="",
        source_text=source_text,
        source_file_path=str(DATA_DIR / "스노우스페이스_FlatLED&커브드LED_효성itx.pdf"),
    )
    assert vendor_name == "효성ITX", (vendor_name, debug)
    print("효성ITX:", vendor_name, debug)


def test_youzone() -> None:
    source_text = """주식회사 유어존
...
공급자
사업자등록번호
715-87-00933
법인명
(주)유어존
대표자
이희숙
"""
    resolver = VendorNameResolver()
    vendor_name, debug = resolver.resolve(
        current_vendor_name="사업자",
        source_text=source_text,
        source_file_path=str(DATA_DIR / "스노우스페이스_FlatLED_유어존.pdf"),
    )
    assert vendor_name == "유어존", (vendor_name, debug)
    assert vendor_name != "사업자"
    print("유어존:", vendor_name, debug)


def test_guidesamjung() -> None:
    source_text = """상호명
㈜가이드삼정
"""
    resolver = VendorNameResolver()
    vendor_name, debug = resolver.resolve(
        current_vendor_name=None,
        source_text=source_text,
        source_file_path=str(DATA_DIR / "스노우스페이스_커브드LED_가이드삼정.xlsx"),
    )
    assert normalize_company_name(vendor_name or "") == "가이드삼정", (vendor_name, debug)
    print("가이드삼정:", vendor_name, debug)


def test_invalid_vendor_name() -> None:
    assert is_invalid_vendor_name("사업자")
    resolver = VendorNameResolver()
    vendor_name, debug = resolver.resolve(
        current_vendor_name="사업자",
        source_text="회사명\n효성ITX 주식회사",
    )
    assert vendor_name == "효성ITX", (vendor_name, debug)
    print("invalid fallback:", vendor_name, debug)


def test_quote_id_uniqueness() -> None:
    pipeline = QuoteIngestionPipeline(
        ocr_provider=None,
        parser_provider=None,
        embedding_provider=None,
    )
    received_at = datetime(2026, 1, 19)

    flat_quote = _quote_document("유어존", received_at)
    curved_quote = _quote_document("유어존", received_at)

    pipeline._enrich_quote_document(
        quote_document=flat_quote,
        path=DATA_DIR / "스노우스페이스_FlatLED_유어존.pdf",
        short_hash="13584d41",
        explicit_quote_id=None,
    )
    pipeline._enrich_quote_document(
        quote_document=curved_quote,
        path=DATA_DIR / "스노우스페이스_커브드LED_유어존.pdf",
        short_hash="2e559147",
        explicit_quote_id=None,
    )

    assert flat_quote.quote_id != curved_quote.quote_id
    assert flat_quote.quote_id.endswith("_13584d41")
    assert curved_quote.quote_id.endswith("_2e559147")
    print("quote_id uniqueness:", flat_quote.quote_id, curved_quote.quote_id)


def _quote_document(vendor_name: str, received_at: datetime) -> QuoteDocument:
    return QuoteDocument(
        vendor_name=vendor_name,
        quote_id=f"{vendor_name}_{received_at:%Y%m%d}",
        received_at=received_at,
        project_name="",
        total_supply_price=0,
        total_with_vat=None,
        delivery_weeks=None,
        warranty_months=None,
    )


def main() -> None:
    test_hyosung_itx()
    test_youzone()
    test_guidesamjung()
    test_invalid_vendor_name()
    test_quote_id_uniqueness()


if __name__ == "__main__":
    main()
