import json
from pathlib import Path
from types import SimpleNamespace

from services.api_demo.response_builders import _build_hardware_section
from services.parser.schemas import LineItem, LineItemCategory


BASELINE_PATH = Path("data/demo_outputs/rule_parser_baseline/rule_parser_baseline_after_v4.json")


def main() -> None:
    test_hardware_alias_mapping()
    test_v4_baseline_hardware()
    print("hardware spec extraction tests: ok")


def test_hardware_alias_mapping() -> None:
    item = LineItem(
        name="TEST-DISPLAY",
        category=LineItemCategory.DISPLAY,
        quantity=1,
        unit="SET",
        unit_price=1,
        total_price=1,
        spec_raw="Panel Size 1211 x 681.7 x 95mm",
        spec_parsed={
            "full_screen_size_mm": "3633 x 2045",
            "resolution": "1920 x 1080",
            "pixel_pitch_mm": 1.56,
            "power_consumption_w": 934,
            "brightness_nit": 500,
            "refresh_rate_hz": 3840,
            "panel_size_mm": "1211 x 681.7 x 95",
        },
    )
    quote = SimpleNamespace(line_items=[item], notes_raw="", warranty_months=12)
    hardware = _build_hardware_section(quote)
    assert hardware["screen_size_mm"] == "3633 x 2045"
    assert hardware["resolution"] == "1920 x 1080"
    assert hardware["pixel_pitch"] == 1.56
    assert hardware["power_consumption_kw"] == 0.934
    assert hardware["brightness_cd_m2"] == 500
    assert hardware["refresh_rate"] == 3840
    assert hardware["free_maintenance_period"] == "12개월"


def test_v4_baseline_hardware() -> None:
    if not BASELINE_PATH.exists():
        raise AssertionError(f"baseline file missing: {BASELINE_PATH}")
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    rows = payload["results"]

    assert_hardware(rows, "LED전광판(p1_5)_다올씨앤씨", "DLED-C", "3200 x 1920", "2080 x 1254", 600)
    assert_hardware(rows, "LED전광판(p1_5)_딥사이닝", "LED Screen Die Cast ing 방식", "3000 x 1687.5", "1920 x 1080", 600)
    assert_hardware(rows, "LED전광판(p1_5)_시스메이트", "Model : DS-D4015CW-2F", "3000 x 1688", "1920 x 1080", 600)
    assert_hardware(rows, "LED전광판(p1_5)_오리온", "LED 디스플레이", "3000 x 2025", "1960 x 1320", 600)
    assert_hardware(rows, "55인치_다올씨앤씨_3안", "LH55VMCRBGBXKR", "3633 x 2045", "1920 x 1080", 500)
    assert_hardware(rows, "55인치_다올씨앤씨_4안", "LC-5502", "3633 x 2045", "1920 x 1080", 500)
    assert_hardware(rows, "55인치_시스메이트", "VW550R-5LW_경량2", "1362.4 x 2421.0", "FHD", 500)

    deep49 = find_row(rows, "49인치_딥사이닝")
    assert deep49["hardware"]["screen_size_mm"] is None


def assert_hardware(rows, file_token, expected_type, screen_size, resolution, brightness) -> None:
    hardware = find_row(rows, file_token)["hardware"]
    assert hardware["type"] == expected_type
    assert hardware["screen_size_mm"] == screen_size
    assert hardware["resolution"] == resolution
    assert hardware["brightness_cd_m2"] == brightness
    assert hardware["source_spec_raw_preview"]


def find_row(rows, file_token):
    for row in rows:
        if file_token in row["source_file_name"]:
            return row
    raise AssertionError(f"row not found: {file_token}")


if __name__ == "__main__":
    main()
