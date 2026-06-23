import os
from pathlib import Path

from dotenv import load_dotenv

from config.paths import DATA_DIR
from services.api_demo.response_builders import _build_hardware_section
from services.test_rule_parser_baseline_on_data_quotes import create_rule_pipeline


def main() -> None:
    load_dotenv(Path(".env"))
    os.environ["QUOTE_PARSER_PROVIDER"] = "rule"
    os.environ["ENABLE_LEGACY_SAMPLE_PATCHES"] = "false"

    file_path = _find_hyosung_pdf()
    results = create_rule_pipeline().process_file_to_results(
        file_path,
        request_id="rule_hyosung_multi_section_parser",
    )
    split_results = [
        result
        for result in results
        if (result.metadata or {}).get("split_from_multi_option")
    ]
    assert len(split_results) == 2, f"expected 2 split quotes, got {len(split_results)}"

    led = _by_option_index(split_results, 1)
    video = _by_option_index(split_results, 2)

    _assert_led_quote(led)
    _assert_video_wall_quote(video)
    print("rule hyosung multi-section parser tests: ok")


def _find_hyosung_pdf() -> Path:
    for path in DATA_DIR.glob("*.pdf"):
        if "itx" in path.name.lower():
            return path
    raise AssertionError("Hyosung ITX PDF fixture not found")


def _by_option_index(results, option_index: int):
    for result in results:
        if (result.metadata or {}).get("option_index") == option_index:
            return result
    raise AssertionError(f"split option not found: {option_index}")


def _assert_led_quote(result) -> None:
    quote = result.quote
    assert len(quote.line_items) == 6, [item.name for item in quote.line_items]
    assert not _residual_items(quote), [item.name for item in _residual_items(quote)]

    display = _find_item(quote, "LED Display")
    assert display.quantity == 20
    assert display.unit_price == 200000
    assert display.total_price == 4000000
    assert _category(display) == "DISPLAY"
    assert display.spec_parsed.get("screen_size_mm") == "3200 x 1920"
    assert display.spec_parsed.get("resolution") == "2080 x 1248"
    assert display.spec_parsed.get("pixel_pitch_mm") == 1.538

    assert _find_item(quote, "VX400Pro").total_price == 2606000
    spare = _find_item(quote, "모듈")
    assert spare.total_price == 120000
    assert _category(spare) != "DISPLAY"
    assert _find_item(quote, "SMPS").total_price == 10000
    assert _find_item(quote, "수신카드").total_price == 12000
    assert _find_item(quote, "설치비").total_price == 7725000
    assert sum(item.total_price or 0 for item in quote.line_items) == 14473000

    hardware = _build_hardware_section(quote)
    assert hardware["type"] in {"LED Display", "LED Display (전광판)"}
    assert hardware["screen_size_mm"] == "3200 x 1920"
    assert hardware["resolution"] == "2080 x 1248"
    assert hardware["pixel_pitch"] == 1.538
    assert hardware["source_spec_raw_preview"]


def _assert_video_wall_quote(result) -> None:
    quote = result.quote
    assert len(quote.line_items) == 4, [item.name for item in quote.line_items]
    assert not _residual_items(quote), [item.name for item in _residual_items(quote)]

    assert _find_item(quote, "비디오월").total_price == 13500000
    assert _find_item(quote, "브라켓").total_price == 2700000
    assert _find_item(quote, "설치").total_price == 4500000
    travel = _find_item(quote, "체류비")
    assert travel.total_price == 100000
    assert (travel.spec_parsed or {}).get("normalized_cost_type") == "TRAVEL"
    assert sum(item.total_price or 0 for item in quote.line_items) == 20800000


def _find_item(quote, token: str):
    for item in quote.line_items:
        if token.lower() in item.name.lower():
            return item
    raise AssertionError(f"line item not found: {token}; items={[item.name for item in quote.line_items]}")


def _residual_items(quote):
    return [
        item
        for item in quote.line_items
        if (item.spec_parsed or {}).get("reconciliation_residual")
    ]


def _category(item) -> str:
    return getattr(item.category, "value", item.category)


if __name__ == "__main__":
    main()
