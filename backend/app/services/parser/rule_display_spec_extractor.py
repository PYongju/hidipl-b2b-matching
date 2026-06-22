import re
from dataclasses import dataclass, field
from typing import Any


SPEC_KEYWORDS = [
    "화면사이즈", "스크린 크기", "display size", "전체 크기", "전체화면 크기", "제안사이즈",
    "해상도", "제안해상도", "전체화면 해상도", "pixel pitch", "led pitch", "pitch",
    "밝기", "nit", "cd", "refresh rate", "전기용량", "최대전력", "최대소비전력",
    "베젤", "bezel", "규격", "panel size", "cabinet", "module", "fhd", "uhd", "4k",
]
STOP_KEYWORDS = ["합계", "소계", "부가세", "vat 합계", "총금액", "은행", "계좌"]


@dataclass
class DisplaySpecExtraction:
    spec_raw: str = ""
    spec_parsed: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)


def extract_display_specs(source_text: str, item_name: str, existing_spec_raw: str = "") -> DisplaySpecExtraction:
    spec_raw = existing_spec_raw.strip() or collect_spec_block(source_text, item_name)
    parsed, evidence = parse_display_specs(spec_raw)
    return DisplaySpecExtraction(spec_raw=spec_raw, spec_parsed=parsed, evidence=evidence)


def collect_spec_block(source_text: str, item_name: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in source_text.splitlines()]
    lines = [line for line in lines if line]
    lowered_name = (item_name or "").lower().strip()
    indexes = [idx for idx, line in enumerate(lines) if lowered_name and lowered_name in line.lower()]
    if not indexes:
        return ""

    collected = []
    for anchor in indexes[:2]:
        block = lines[max(0, anchor - 2):anchor + 24]
        for position, line in enumerate(block):
            lowered = line.lower()
            if any(token in lowered for token in STOP_KEYWORDS):
                continue
            if any(token in lowered for token in SPEC_KEYWORDS):
                collected.append(line)
                if position + 1 < len(block) and _looks_like_label_value_continuation(block[position + 1]):
                    collected.append(block[position + 1])
    return " ".join(dict.fromkeys(collected))[:3000]


def parse_display_specs(text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    parsed: dict[str, Any] = {"normalized_cost_type": "DISPLAY"}
    evidence: dict[str, Any] = {}
    if not text:
        return parsed, evidence

    screen = _labeled_dimensions(text, ["전체화면 크기", "스크린 크기", "display size", "screen size", "제안사이즈", "화면사이즈", "전체 크기", "화면 크기", "크기"])
    resolution = _labeled_dimensions(text, ["전체화면 해상도", "제안해상도", "해상도", "resolution"])
    panel = _labeled_dimensions(text, ["규격(wxhxd)", "panel size", "패널 크기"])
    cabinet = _labeled_dimensions(text, ["cabinet size", "cabinet 크기"])
    module = _labeled_dimensions(text, ["module size", "module 크기"])
    cabinet_resolution = _labeled_dimensions(text, ["cabinet 해상도"])
    module_resolution = _labeled_dimensions(text, ["module 해상도"])

    _put(parsed, evidence, "screen_size_mm", screen)
    _put(parsed, evidence, "full_screen_size_mm", screen)
    _put(parsed, evidence, "resolution", resolution)
    _put(parsed, evidence, "panel_size_mm", panel)
    _put(parsed, evidence, "cabinet_size_mm", cabinet)
    _put(parsed, evidence, "module_size_mm", module)
    _put(parsed, evidence, "cabinet_resolution", cabinet_resolution)
    _put(parsed, evidence, "module_resolution", module_resolution)

    pitch = _number(text, r"(?:pixel\s*pitch|led\s*pitch|pitch|p)\s*[: ]?\s*(\d+(?:\.\d+)?)")
    if pitch is None:
        pitch = _number(text, r"(\d+(?:\.\d+)?)\s*p\b")
    if pitch is None:
        pitch = _number(text, r"(\d+(?:\.\d+)?)\s*(?:mm\s*)?(?:pixel\s*pitch|led\s*pitch|pitch)")
    brightness = _number(text, r"(?:밝기[^0-9]{0,30})?(\d{2,5})[^a-z0-9]{0,10}(?:nit|cd(?:/m2)?)")
    refresh = _number(text, r"refresh\s*rate[^0-9]{0,30}(\d+(?:\.\d+)?)")
    bezel = _number(text, r"(?:베젤|bezel)[^0-9]{0,20}(\d+(?:\.\d+)?)\s*mm")
    power_kw = _number(
        text,
        r"(?:전기용량|최대전력|최대소비전력|소비전력|차단기)[^0-9]{0,30}"
        r"(\d+(?:\.\d+)?)[^a-z0-9]{0,10}kW\b",
    )
    power_w = _number(
        text,
        r"(?:전기용량|최대전력|최대소비전력|소비전력|차단기)[^0-9]{0,30}"
        r"(\d+(?:\.\d+)?)[^a-z0-9]{0,10}W\b",
    )
    size_inch = _number(text, r"(\d+(?:\.\d+)?)\s*(?:inch|인치|\")")

    for key, value in [
        ("pixel_pitch_mm", pitch), ("pitch_mm", pitch), ("brightness_cd_m2", brightness),
        ("brightness_nit", brightness), ("refresh_rate_hz", refresh), ("bezel_mm", bezel),
        ("power_consumption_kw", power_kw), ("power_consumption_w", power_w), ("size_inch", size_inch),
    ]:
        _put(parsed, evidence, key, value)
    if power_kw is None and power_w is not None:
        parsed["power_consumption_kw"] = round(power_w / 1000, 3)
    resolution_type = re.search(r"\b(FHD|UHD|4K|8K)\b", text, re.IGNORECASE)
    if resolution_type:
        parsed["resolution_type"] = resolution_type.group(1).upper()
    parsed = sanitize_display_spec_parsed(parsed, spec_raw=text)
    parsed["_evidence"] = evidence
    return parsed, evidence


def sanitize_display_spec_parsed(
    spec_parsed: dict[str, Any],
    *,
    spec_raw: str = "",
) -> dict[str, Any]:
    result = dict(spec_parsed or {})
    sanitization = list(result.get("spec_sanitization") or [])
    size_values = {
        key: result.get(key)
        for key in ["panel_size_mm", "cabinet_size_mm", "module_size_mm"]
        if result.get(key)
    }
    for field in ["screen_size_mm", "full_screen_size_mm"]:
        value = result.get(field)
        if not value:
            continue
        reason = None
        if value in size_values.values() or any(
            _dimensions_equivalent(value, size_value)
            for size_value in size_values.values()
        ):
            reason = "value belongs to panel/cabinet/module size"
        else:
            pair = _dimension_pair(value)
            if pair and (pair[0] < 1000 or pair[1] < 500):
                reason = "screen size below display-level threshold"
        if reason:
            sanitization.append({"field": field, "removed_value": value, "reason": reason})
            result.pop(field, None)

    resolution = result.get("resolution")
    if resolution:
        reason = None
        related_values = [
            result.get("cabinet_resolution"),
            result.get("module_resolution"),
            *size_values.values(),
        ]
        if resolution in related_values or any(
            _dimensions_equivalent(resolution, related)
            for related in related_values
            if related
        ):
            reason = "value belongs to cabinet/module/panel field"
        else:
            pair = _dimension_pair(resolution)
            if pair and (pair in {(600.0, 400.0), (300.0, 168.0)} or pair[0] < 640 or pair[1] < 480):
                reason = "resolution below valid display threshold or known VESA/module size"
        if reason:
            sanitization.append({"field": "resolution", "removed_value": resolution, "reason": reason})
            result.pop("resolution", None)

    bezel = _to_float(result.get("bezel_mm"))
    if bezel is not None and not (0.1 <= bezel <= 50):
        sanitization.append({"field": "bezel_mm", "removed_value": result.get("bezel_mm"), "reason": "bezel outside valid range"})
        result.pop("bezel_mm", None)
    power_evidence = bool(
        re.search(
            r"(?:전기용량|최대전력|최대소비전력|소비전력|차단기)|"
            r"\b\d+(?:\.\d+)?\s*(?:kW|W)\b",
            spec_raw or "",
            re.IGNORECASE,
        )
    )
    if not power_evidence:
        for field in ["power_consumption_kw", "power_consumption_w"]:
            if field not in result:
                continue
            sanitization.append(
                {
                    "field": field,
                    "removed_value": result.get(field),
                    "reason": "power value has no W/kW or labeled power evidence",
                }
            )
            result.pop(field, None)
    if sanitization:
        result["spec_sanitization"] = sanitization
    return result


def _labeled_dimensions(text: str, labels: list[str]) -> str | None:
    dims = r"(?:가로\s*[:：]?\s*|\(W\)\s*)?(\d{1,5}(?:,\d{3})?(?:\.\d+)?)\s*(?:mm\s*)?[xX×]\s*(?:세로\s*[:：]?\s*|\(H\)\s*)?(\d{1,5}(?:,\d{3})?(?:\.\d+)?)(?:\s*[xX×]\s*(\d{1,5}(?:\.\d+)?))?"
    for label in labels:
        match = re.search(rf"{re.escape(label)}[^0-9]{{0,80}}{dims}", text, re.IGNORECASE)
        if match:
            parts = [part.replace(",", "") for part in match.groups() if part is not None]
            return " x ".join(parts)
    return None


def _number(text: str, pattern: str) -> float | int | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    return int(value) if value.is_integer() else value


def _put(parsed: dict[str, Any], evidence: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    parsed[key] = value
    evidence[key] = {"source": "display_spec_block", "label": key, "value": value}


def _looks_like_label_value_continuation(line: str) -> bool:
    return bool(re.search(r"\d", line)) and (
        bool(re.search(r"[xX×|]", line))
        or bool(re.search(r"\b(?:mm|pixels?|nit|cd/m2|hz|kw|w)\b", line, re.IGNORECASE))
    )


def _dimension_pair(value: Any) -> tuple[float, float] | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)", str(value).replace(",", ""))
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def _dimensions_equivalent(left: Any, right: Any, tolerance: float = 1.0) -> bool:
    left_pair = _dimension_pair(left)
    right_pair = _dimension_pair(right)
    if not left_pair or not right_pair:
        return False
    return (
        abs(left_pair[0] - right_pair[0]) <= tolerance
        and abs(left_pair[1] - right_pair[1]) <= tolerance
    )


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
