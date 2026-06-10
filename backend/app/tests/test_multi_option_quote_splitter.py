from __future__ import annotations

from datetime import datetime

from services.quote_ingestion.multi_option_splitter import (
    MULTI_OPTION_SPLIT_FAILED_MESSAGE,
    split_multi_option_result,
)
from services.quote_ingestion.quote_ingestion_pipeline import QuoteIngestionPipeline
from services.quote_ingestion.schemas import QuoteIngestionResult
from services.parser.schemas import LineItem, LineItemCategory, QuoteDocument


class FakeEmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        return [0.1] * 3072


def main() -> None:
    test_hyosung_multi_option_split()
    test_single_quote_is_not_split()
    test_split_failure_keeps_single_result_with_check_required()
    test_split_embedding_text_is_separated()
    print("Multi-option quote splitter tests passed")


def test_hyosung_multi_option_split() -> None:
    result = build_hyosung_result()
    split_results = split_multi_option_result(result)

    assert len(split_results) == 2
    led, video = split_results

    assert led.metadata["option_label"] == "LED전광판"
    assert led.quote.total_supply_price == 14_473_000
    assert led.quote.tax_amount == 1_447_300
    assert led.quote.total_with_vat == 15_920_300
    assert len(led.quote.line_items) == 6
    assert led.parser_raw_matches["amount_validation"]["line_items_difference"] == 0
    assert led.parser_raw_matches["amount_validation"]["validation_status"] == "normal"
    led_display = led.quote.line_items[0]
    vx400pro = led.quote.line_items[1]
    assert led_display.name == "LED Display"
    assert led_display.quantity == 20.0
    assert led_display.unit_price == 200_000
    assert led_display.total_price == 4_000_000
    assert "VX400Pro" in vx400pro.name
    assert vx400pro.quantity == 1.0
    assert vx400pro.unit_price == 2_606_000
    assert vx400pro.total_price == 2_606_000
    assert len(led.parser_raw_matches["line_item_corrections"]) == 2
    assert not any("line_items 합계" in item for item in led.metadata["parser_check_required"])

    assert video.metadata["option_label"] == "비디오월"
    assert video.quote.total_supply_price == 20_800_000
    assert video.quote.tax_amount == 2_080_000
    assert video.quote.total_with_vat == 22_880_000
    assert len(video.quote.line_items) == 4
    assert video.parser_raw_matches["amount_validation"]["line_items_difference"] == 0
    assert video.parser_raw_matches.get("line_item_corrections") == []

    assert result.quote_id not in {item.quote_id for item in split_results}
    assert all(item.metadata["split_from_multi_option"] is True for item in split_results)
    assert all("복수 옵션" not in " ".join(item.metadata.get("parser_check_required") or []) for item in split_results)


def test_single_quote_is_not_split() -> None:
    result = build_single_result()
    split_results = split_multi_option_result(result)

    assert split_results == [result]
    assert not result.metadata.get("split_from_multi_option")


def test_split_failure_keeps_single_result_with_check_required() -> None:
    result = build_hyosung_result()
    result.parser_raw_matches["multi_option_detection"]["option_total_candidates"][0]["supply_price"] = 1
    result.parser_raw_matches["multi_option_detection"]["product_groups"] = []
    split_results = split_multi_option_result(result)

    assert split_results == [result]
    assert MULTI_OPTION_SPLIT_FAILED_MESSAGE in result.metadata["parser_check_required"]
    assert result.metadata["split_failed_reason"]


def test_split_embedding_text_is_separated() -> None:
    result = build_hyosung_result()
    split_results = split_multi_option_result(result)
    pipeline = QuoteIngestionPipeline(
        ocr_provider=None,
        parser_provider=None,
        embedding_provider=FakeEmbeddingProvider(),
    )
    for item in split_results:
        pipeline._refresh_embedding(item)

    led, video = split_results
    assert led.embedding_dim == 3072
    assert video.embedding_dim == 3072
    assert "46\" 비디오월" not in led.embedding_text
    assert "LED Display" not in video.embedding_text


def build_hyosung_result() -> QuoteIngestionResult:
    quote = QuoteDocument(
        vendor_name="효성ITX",
        quote_id="효성ITX_20260605_142127_eb487781",
        received_at=datetime(2026, 6, 5, 14, 21, 27),
        project_name="충북 음성 회의실 내 디스플레이 견적",
        total_supply_price=35_273_000,
        total_with_vat=38_800_600,
        warranty_months=12,
        line_items=[
            line("LED Display", LineItemCategory.DISPLAY, 4_000_000, quantity=1, unit_price=4_000_000),
            line("All-in-one VX400Pro", LineItemCategory.PLAYER, 5_212_000, quantity=2, unit_price=2_606_000),
            line("LED 모듈 예비품", LineItemCategory.DISPLAY, 120_000),
            line("SMPS", LineItemCategory.DISPLAY, 10_000),
            line("수신카드", LineItemCategory.DISPLAY, 12_000),
            line("설치비", LineItemCategory.INSTALL, 7_725_000),
            line('46" 비디오월 3 x 3', LineItemCategory.DISPLAY, 13_500_000),
            line("브라켓", LineItemCategory.MOUNT, 2_700_000),
            line("제품 설치비", LineItemCategory.INSTALL, 4_500_000),
            line("출장 및 체류비", LineItemCategory.ETC, 100_000),
        ],
    )
    return QuoteIngestionResult(
        quote_id=quote.quote_id,
        request_id="test",
        source_file_path="data/일강_비디오월&LED전광판(p1_5)_효성itx.pdf",
        quote=quote,
        embedding_text="parent embedding",
        embedding_vector=[0.0] * 3072,
        embedding_dim=3072,
        ocr_text_preview="",
        parser_warnings=[],
        parser_raw_matches={
            "parser_check_required": ["문서 내 복수 옵션 견적 확인 필요"],
            "multi_option_detection": {
                "is_multi_option_possible": True,
                "option_total_candidates": [
                    {
                        "label": None,
                        "supply_price": 14_473_000,
                        "tax_amount": 1_447_300,
                        "total_with_vat": 15_920_300,
                    },
                    {
                        "label": "비디오월",
                        "supply_price": 20_800_000,
                        "tax_amount": 2_080_000,
                        "total_with_vat": 22_880_000,
                    },
                ],
                "product_groups": ["LED전광판", "비디오월"],
                "auto_split": False,
            },
        },
        ingestion_warnings=[],
        metadata={"parser_check_required": ["문서 내 복수 옵션 견적 확인 필요"]},
    )


def build_single_result() -> QuoteIngestionResult:
    quote = QuoteDocument(
        vendor_name="다올씨앤씨",
        quote_id="다올씨앤씨_quote",
        received_at=datetime(2026, 6, 5),
        project_name="일강 비디오월 46인치",
        total_supply_price=9_440_000,
        total_with_vat=10_384_000,
        line_items=[
            line('46" 비디오월 3 x 3', LineItemCategory.DISPLAY, 9_440_000),
        ],
    )
    return QuoteIngestionResult(
        quote_id=quote.quote_id,
        request_id="test",
        source_file_path="data/일강_비디오월_46인치_다올씨앤씨.pdf",
        quote=quote,
        embedding_text="",
        embedding_vector=None,
        embedding_dim=None,
        ocr_text_preview="",
        parser_warnings=[],
        parser_raw_matches={
            "multi_option_detection": {
                "is_multi_option_possible": False,
                "option_total_candidates": [],
            }
        },
        ingestion_warnings=[],
        metadata={},
    )


def line(
    name: str,
    category: LineItemCategory,
    total_price: int,
    *,
    quantity: float = 1,
    unit_price: int | None = None,
) -> LineItem:
    return LineItem(
        name=name,
        category=category,
        quantity=quantity,
        unit="식",
        unit_price=unit_price if unit_price is not None else total_price,
        total_price=total_price,
        spec_raw=name,
    )


if __name__ == "__main__":
    main()
