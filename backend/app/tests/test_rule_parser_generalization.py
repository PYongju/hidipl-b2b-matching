from pathlib import Path

from services.parser.rule_amount_extractor import extract_summary_amounts
from services.parser.rule_display_spec_extractor import extract_display_specs
from services.parser.rule_line_item_parser import remove_summary_rows
from services.parser.quote_parser_validator import normalize_line_item_category
from services.parser.rule_line_item_parser import assign_amount_pairs_by_order
from services.parser.schemas import LineItem, LineItemCategory, QuoteItem


REPORT_PATH = Path("data/demo_outputs/rule_parser_baseline/rule_parser_generalization_report.md")


def main() -> None:
    cases = [
        test_new_led_quote(),
        test_new_video_wall_quote(),
        test_alternate_summary_labels(),
        test_summary_row_removal(),
        test_label_value_specs(),
        test_ordered_amount_pair_assignment(),
        test_display_category_name_priority(),
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "# Rule Parser Generalization Report\n\n"
        "- legacy_sample_patches: false\n"
        "- LLM Parser: not used\n\n"
        + "\n".join(f"- {name}: pass" for name in cases)
        + "\n",
        encoding="utf-8",
    )
    print("rule parser generalization tests: ok")


def test_new_led_quote() -> str:
    text = """
    NEW-LED-X9
    전체화면 크기 : 4200 x 2363 mm
    전체화면 해상도 : 2688 x 1512
    Pixel Pitch : 1.5625mm
    밝기 : 800 nit
    Refresh Rate : 3840 Hz
    최대전력 : 3.2 kW
    """
    result = extract_display_specs(text, "NEW-LED-X9")
    assert result.spec_parsed["screen_size_mm"] == "4200 x 2363"
    assert result.spec_parsed["resolution"] == "2688 x 1512"
    assert result.spec_parsed["pixel_pitch_mm"] == 1.5625
    assert result.spec_parsed["brightness_cd_m2"] == 800
    assert result.spec_parsed["refresh_rate_hz"] == 3840
    assert result.spec_parsed["power_consumption_kw"] == 3.2
    return "new LED quote with unseen vendor/model/amount"


def test_new_video_wall_quote() -> str:
    text = """
    VX-NEW-55
    전체 크기 : 3660 x 2058 mm
    해상도 : 1920 x 1080
    밝기 : 550nit
    베젤 두께 합 : 0.9mm
    규격(WxHxD) : 1220 x 686 x 80 mm
    최대소비전력 : 1200 W
    """
    result = extract_display_specs(text, "VX-NEW-55")
    assert result.spec_parsed["screen_size_mm"] == "3660 x 2058"
    assert result.spec_parsed["resolution"] == "1920 x 1080"
    assert result.spec_parsed["brightness_cd_m2"] == 550
    assert result.spec_parsed["panel_size_mm"] == "1220 x 686 x 80"
    assert result.spec_parsed["power_consumption_kw"] == 1.2
    return "new video-wall quote with different spec order"


def test_alternate_summary_labels() -> str:
    text = """
    공급금액 18,500,000
    세액 1,850,000
    VAT 포함 총금액 20,350,000
    """
    result = extract_summary_amounts(text)
    assert result.supply_amount == 18_500_000
    assert result.tax_amount == 1_850_000
    assert result.total_amount == 20_350_000
    return "alternate amount summary labels"


def test_summary_row_removal() -> str:
    items = [
        QuoteItem(item_name="NEW DISPLAY", quantity=1, unit_price=1_000_000, amount=1_000_000),
        QuoteItem(item_name="부가세", quantity=0, amount=100_000),
        QuoteItem(item_name="총금액", quantity=0, amount=1_100_000),
    ]
    result = remove_summary_rows(items)
    assert [item.item_name for item in result] == ["NEW DISPLAY"]
    return "generic summary row removal"


def test_label_value_specs() -> str:
    text = """
    NEW-X
    스크린 크기 | 가로: 3,000 × 세로: 2,025 | mm
    해상도 | 1,960 × 1,320 | pixels
    Pixel Pitch | P1.53mm | mm
    밝기 | 600 | cd/m2
    Refresh Rate | 3840 | Hz
    전기용량 | 5kW
    """
    result = extract_display_specs(text, "NEW-X")
    assert result.spec_parsed["screen_size_mm"] == "3000 x 2025"
    assert result.spec_parsed["resolution"] == "1960 x 1320"
    assert result.spec_parsed["pixel_pitch_mm"] == 1.53
    assert result.spec_parsed["brightness_cd_m2"] == 600
    assert result.spec_parsed["refresh_rate_hz"] == 3840
    return "split label-value display spec parsing"


def test_ordered_amount_pair_assignment() -> str:
    items = [
        QuoteItem(item_name="DISPLAY-X", quantity=2),
        QuoteItem(item_name="설치비", quantity=1),
    ]
    evidence = assign_amount_pairs_by_order(
        items,
        "₩1,000,000 ₩2,000,000\n₩500,000 ₩500,000",
        2_500_000,
    )
    assert evidence and [item.amount for item in items] == [2_000_000, 500_000]
    return "ordered amount pair assignment"


def test_display_category_name_priority() -> str:
    item = LineItem(
        name="LED Screen Die Casting 방식",
        category=LineItemCategory.DISPLAY,
        quantity=1,
        unit="SET",
        unit_price=1,
        total_price=1,
        spec_raw="소프트웨어 세팅 포함",
    )
    normalize_line_item_category(item)
    assert item.category == LineItemCategory.DISPLAY
    assert item.spec_parsed["normalized_cost_type"] == "DISPLAY"
    return "item-name priority category normalization"


if __name__ == "__main__":
    main()
