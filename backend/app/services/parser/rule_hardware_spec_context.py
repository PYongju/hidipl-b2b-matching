from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from services.parser.rule_display_spec_extractor import (
    parse_display_specs,
    sanitize_display_spec_parsed,
)


@dataclass
class HardwareSpecContext:
    spec_raw: str | None = None
    spec_parsed: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)


SPEC_KEYWORDS = [
    "화면 크기",
    "화면크기",
    "스크린 크기",
    "전체 크기",
    "전체화면",
    "display size",
    "screen size",
    "제안사이즈",
    "구현",
    "해상도",
    "resolution",
    "제안해상도",
    "pixel pitch",
    "pitch",
    "밝기",
    "brightness",
    "nit",
    "cd/m2",
    "평균전력",
    "소비전력",
    "최대전력",
    "전기용량",
    "power",
    "w",
    "kw",
    "refresh",
    "hz",
    "주사율",
    "cabinet size",
    "module size",
    "베젤",
    "bezel",
    "smd",
    "cob",
    "flexible",
    "die-casting",
    "fhd",
    "uhd",
    "4k",
]

STOP_KEYWORDS = [
    "합계",
    "소계",
    "공급가",
    "부가세",
    "vat",
    "총금액",
    "견적금액",
    "cost breakdown",
]

CONTROLLER_CONTEXT_TOKENS = [
    "s-box",
    "novastar",
    "colorlight",
    "vx1000",
    "vx600",
    "mx40",
    "x16",
    "z6",
    "controller",
    "scaler",
    "컨트롤러",
    "스케일러",
]


def collect_hardware_spec_context(
    *values: Any,
    product_group_hint: str | None = None,
    max_chars: int = 3000,
) -> HardwareSpecContext:
    lines: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                lines.extend(_split_lines(item))
            continue
        lines.extend(_split_lines(value))

    candidates = _collect_candidate_lines(lines)
    selected_text = select_hardware_spec_context_text(
        " ".join(candidates),
        product_group_hint=product_group_hint,
    )
    if selected_text:
        candidates = _split_lines(selected_text)
    spec_raw = " ".join(dict.fromkeys(candidates))[:max_chars]
    display_spec_raw = _remove_controller_spec_segments(spec_raw)
    parsed, evidence = parse_display_specs(display_spec_raw)
    additional = _parse_additional_specs(display_spec_raw)
    parsed.update(additional)
    parsed = sanitize_display_spec_parsed(parsed, spec_raw=display_spec_raw)
    for key, value in additional.items():
        if value is not None and key not in parsed:
            parsed[key] = value
    evidence.update(_evidence_from_parsed(parsed))
    if evidence:
        parsed["_evidence"] = {**(parsed.get("_evidence") or {}), **evidence}
    return HardwareSpecContext(
        spec_raw=spec_raw or None,
        spec_parsed=parsed,
        evidence=evidence,
    )


def merge_hardware_spec_context(item: Any, context: HardwareSpecContext, *, source: str) -> bool:
    if not context.spec_raw and not context.spec_parsed:
        return False

    before_raw = getattr(item, "spec_raw", "") or ""
    before_parsed = dict(getattr(item, "spec_parsed", {}) or {})
    merged_parsed = dict(before_parsed)
    for key, value in (context.spec_parsed or {}).items():
        if value is not None and key not in merged_parsed:
            merged_parsed[key] = value
    if context.evidence:
        merged_parsed["_evidence"] = {
            **(before_parsed.get("_evidence") or {}),
            **context.evidence,
        }
    if context.spec_raw and (
        not before_raw
        or before_raw == "summary amount reconciliation"
        or not _has_hardware_signal(before_raw)
    ):
        item.spec_raw = context.spec_raw
    item.spec_parsed = sanitize_display_spec_parsed(merged_parsed, spec_raw=item.spec_raw or "")
    item.spec_parsed["hardware_spec_source"] = source
    return before_raw != item.spec_raw or before_parsed != item.spec_parsed


def extract_screen_size_mm(text: str | None) -> str | None:
    if not text:
        return None
    labeled = _labeled_dimension(
        text,
        [
            "화면 크기",
            "화면크기",
            "스크린 크기",
            "전체 크기",
            "전체화면 크기",
            "display size",
            "screen size",
            "제안사이즈",
            "구현",
        ],
    )
    if labeled:
        return labeled
    for match in re.finditer(
        r"(\d{1,3}(?:,\d{3})+|\d{3,5})(?:\.\d+)?\s*(?:mm\s*)?"
        r"[xX×*]\s*(\d{1,3}(?:,\d{3})+|\d{3,5})(?:\.\d+)?\s*(?:mm)?",
        text,
        re.IGNORECASE,
    ):
        start = max(0, match.start() - 60)
        end = min(len(text), match.end() + 60)
        context = text[start:end].lower()
        before = text[max(0, match.start() - 25):match.start()].lower()
        if any(token in before for token in ["cabinet", "module", "vesa", "브라켓", "캐비닛", "모듈"]):
            continue
        if any(token in before for token in ["해상도", "resolution", "px", "pixel"]):
            continue
        if not (
            any(
                token in context
                for token in [
                    "화면",
                    "전체",
                    "screen",
                    "display",
                    "led",
                    "비디오월",
                    "구현",
                    "제안",
                ]
            )
            or "mm" in match.group(0).lower()
        ):
            continue
        width = float(match.group(1).replace(",", ""))
        height = float(match.group(2).replace(",", ""))
        if width < 1000 or height < 500:
            continue
        return f"{_format_number(width)} x {_format_number(height)}"
    return None


def extract_power_consumption_kw(text: str | None) -> float | None:
    if not text:
        return None
    patterns = [
        r"(?:평균전력|소비전력|최대전력|전기용량|avg\s*power|max\s*power|power)"
        r"[^0-9]{0,30}(?:\(?\s*kw\s*\)?)?[^0-9]{0,10}"
        r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:kw)?\b",
        r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*kw\b",
    ]
    for pattern in patterns:
        value = _number(text, pattern)
        if value is not None and 0 < float(value) <= 500:
            return float(value)
    watts = _number(
        text,
        r"(?:평균전력|소비전력|최대전력|전기용량|avg\s*power|max\s*power|power)"
        r"[^0-9]{0,30}(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*w\b",
    )
    if watts is None:
        watts = _number(text, r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*w\b")
    if watts is not None:
        kw = round(float(watts) / 1000, 3)
        if 0 < kw <= 500:
            return kw
    return None


def extract_refresh_rate_hz(text: str | None) -> int | None:
    if not text:
        return None
    if _has_controller_context(text) and not _has_display_refresh_context(text):
        return None
    patterns = [
        r"(?:refresh\s*rate|주사율)[^0-9]{0,30}(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*hz",
        r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*hz",
    ]
    for pattern in patterns:
        value = _number(text, pattern)
        if value is not None and 30 <= float(value) <= 10000:
            return int(float(value))
    return None


def select_hardware_spec_context_text(
    text: str | None,
    *,
    product_group_hint: str | None = None,
) -> str:
    if not text:
        return ""
    chunks = _split_spec_chunks(text)
    if not chunks:
        return ""
    if not product_group_hint:
        return " ".join(chunks)
    scored = [
        (_product_group_context_score(chunk, product_group_hint), _spec_density_score(chunk), idx, chunk)
        for idx, chunk in enumerate(chunks)
    ]
    positive = [item for item in scored if item[0] > 0]
    if not positive:
        return " ".join(chunks)
    positive.sort(key=lambda item: (item[0], item[1], -item[2]), reverse=True)
    return _trim_chunk_for_group(positive[0][3], product_group_hint)


def clean_hardware_spec_preview(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = []
    for raw_line in _split_lines(text):
        raw_line = _remove_controller_spec_segments(raw_line)
        line = _strip_header_footer_noise(raw_line)
        if not line:
            continue
        line = _strip_amount_tail(line)
        if not line:
            continue
        if _looks_like_amount_line(line.lower()):
            continue
        if _has_hardware_signal(line) or _looks_like_continuation(line):
            cleaned.append(line)
    preview = " ".join(dict.fromkeys(cleaned))
    preview = re.sub(r"\s+", " ", preview).strip()
    preview = _cut_header_footer_tail(preview)
    return preview[:300] if preview else None


def _split_lines(value: Any) -> list[str]:
    text = str(value or "")
    lines = []
    for raw_line in re.split(r"[\r\n|]+", text):
        line = re.sub(r"\s+", " ", raw_line).strip(" :-\t")
        if line:
            lines.append(line)
    return lines


def _collect_candidate_lines(lines: list[str]) -> list[str]:
    candidates: list[str] = []
    for index, line in enumerate(lines):
        lower = line.lower()
        if _looks_like_amount_line(lower):
            continue
        has_keyword = _has_hardware_signal(line)
        has_pitch = bool(re.search(r"\bp\s*\d+(?:\.\d+)?\b", lower))
        has_size = bool(re.search(r"\d{3,5}\s*[xX×*]\s*\d{3,5}", line))
        has_inches = bool(re.search(r"\b(?:46|49|55|65|75|86)\s*(?:\"|인치|inch)\b", lower))
        if has_keyword or has_pitch or has_inches:
            candidates.append(line)
            if index + 1 < len(lines) and _looks_like_continuation(lines[index + 1]):
                candidates.append(lines[index + 1])
        elif has_size and any(token in lower for token in ["led", "display", "screen", "화면", "스크린"]):
            candidates.append(line)
    return candidates


def _parse_additional_specs(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    if not text:
        return parsed
    screen = extract_screen_size_mm(text)
    resolution = _labeled_dimension(
        text,
        ["해상도", "resolution", "제안해상도", "전체화면 해상도"],
    )
    if screen:
        parsed["screen_size_mm"] = screen
        parsed["full_screen_size_mm"] = screen
    if resolution:
        parsed["resolution"] = resolution
    pitch = _number(text, r"(?:pixel\s*pitch|led\s*pitch|pitch|p)\s*[: ]?\s*(\d+(?:\.\d+)?)")
    if pitch is not None:
        parsed["pixel_pitch_mm"] = pitch
        parsed["pitch_mm"] = pitch
    brightness = _number(text, r"(?:밝기|brightness)?[^0-9]{0,20}(\d{2,5})\s*(?:nit|cd/?m2)")
    if brightness is not None:
        parsed["brightness_cd_m2"] = brightness
        parsed["brightness_nit"] = brightness
    refresh = extract_refresh_rate_hz(text)
    if refresh is not None:
        parsed["refresh_rate_hz"] = refresh
    power_kw = extract_power_consumption_kw(text)
    if power_kw is not None:
        parsed["power_consumption_kw"] = power_kw
    power_w = _number(text, r"(?:소비전력|최대전력|평균전력|power)[^0-9]{0,30}(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*w\b")
    if power_w is not None and "power_consumption_kw" not in parsed:
        parsed["power_consumption_w"] = power_w
        parsed["power_consumption_kw"] = round(float(power_w) / 1000, 3)
    resolution_type = re.search(r"\b(FHD|UHD|4K|8K)\b", text, re.IGNORECASE)
    if resolution_type:
        parsed["resolution_type"] = resolution_type.group(1).upper()
        if "resolution" not in parsed and not _has_controller_context(text):
            parsed["resolution"] = parsed["resolution_type"]
    size_inch = _number(text, r"\b(\d{2,3})\s*(?:\"|인치|inch)\b")
    if size_inch is not None:
        parsed["size_inch"] = size_inch
    return parsed


def _labeled_dimension(text: str, labels: list[str]) -> str | None:
    dims = (
        r"(\d{2,5}(?:,\d{3})?(?:\.\d+)?)\s*(?:mm\s*)?"
        r"[xX×*]\s*(\d{2,5}(?:,\d{3})?(?:\.\d+)?)"
    )
    for label in labels:
        match = re.search(rf"{re.escape(label)}[^0-9]{{0,80}}{dims}", text, re.IGNORECASE)
        if match:
            return f"{match.group(1).replace(',', '')} x {match.group(2).replace(',', '')}"
    return None


def _number(text: str, pattern: str) -> float | int | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    return int(value) if value.is_integer() else value


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _evidence_from_parsed(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        key: {"source": "hardware_spec_context", "value": value}
        for key, value in parsed.items()
        if key
        in {
            "screen_size_mm",
            "full_screen_size_mm",
            "resolution",
            "pixel_pitch_mm",
            "pitch_mm",
            "brightness_cd_m2",
            "brightness_nit",
            "refresh_rate_hz",
            "power_consumption_kw",
            "power_consumption_w",
            "size_inch",
        }
        and value is not None
    }


def _has_hardware_signal(value: str | None) -> bool:
    if not value:
        return False
    lower = value.lower()
    return any(keyword.lower() in lower for keyword in SPEC_KEYWORDS)


def _looks_like_continuation(value: str) -> bool:
    lower = value.lower()
    return bool(re.search(r"\d", lower)) and not _looks_like_amount_line(lower)


def _looks_like_amount_line(lower: str) -> bool:
    has_stop = any(keyword in lower for keyword in STOP_KEYWORDS)
    has_money = bool(re.search(r"\d{1,3}(?:,\d{3})+\s*(?:원|₩)?", lower))
    has_amount_sequence = bool(
        re.search(r"\b\d{1,4}\s+\d{1,3}(?:,\d{3})+\s+\d{1,3}(?:,\d{3})+\b", lower)
    )
    return (has_stop and (has_money or re.search(r"\d", lower))) or has_amount_sequence


def _split_spec_chunks(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    parts = re.split(
        r"(?=(?:커브드\s*LED|플랫\s*LED|평면\s*LED|LED\s*(?:Display|Screen|디스플레이)|"
        r"비디오월|Video\s*Wall|DID|(?:46|49|55)\s*(?:\"|인치|inch)))",
        normalized,
        flags=re.IGNORECASE,
    )
    chunks = [part.strip(" ·;|") for part in parts if part.strip(" ·;|")]
    return chunks or [normalized]


def _product_group_context_score(text: str, product_group_hint: str) -> int:
    lower = text.lower()
    hint = product_group_hint.lower()
    if "비디오월" in hint:
        tokens = ["비디오월", "video wall", "did", "멀티비전", "베젤", "bezel", "46", "49", "55", "fhd", "3×3", "3x3"]
    elif "led" in hint or "전광판" in hint:
        tokens = ["led", "전광판", "pixel pitch", "pitch", "p1.", "p2.", "p3.", "smd", "cob", "cabinet", "module"]
    else:
        tokens = ["display", "디스플레이", "screen", "모니터", "프로젝터", "전자칠판"]
    return sum(1 for token in tokens if token in lower)


def _trim_chunk_for_group(chunk: str, product_group_hint: str) -> str:
    if not chunk:
        return ""
    hint = product_group_hint.lower()
    if "비디오월" in hint:
        has_video_signal = bool(
            re.search(
                r"(비디오월|Video\s*Wall|DID|멀티비전|베젤|bezel|(?:46|49|55)\s*(?:\"|인치|inch))",
                chunk,
                re.IGNORECASE,
            )
        )
        if not has_video_signal:
            return chunk.strip(" ·;|")
        split = re.split(
            r"\s+(?=LED\s|LED전광판|P\s*\d+(?:\.\d+)?\s*(?:SMD|COB|mm))",
            chunk,
            maxsplit=1,
            flags=re.IGNORECASE,
        )
        return split[0].strip(" ·;|")
    if "led" in hint or "전광판" in hint:
        split = re.split(
            r"\s+(?=비디오월|Video\s*Wall|DID|(?:46|49|55)\s*(?:\"|인치|inch))",
            chunk,
            maxsplit=1,
            flags=re.IGNORECASE,
        )
        return split[0].strip(" ·;|")
    return chunk.strip(" ·;|")


def _spec_density_score(text: str) -> int:
    score = 0
    if extract_screen_size_mm(text):
        score += 2
    if _labeled_dimension(text, ["해상도", "resolution", "제안해상도"]):
        score += 2
    if re.search(r"\bp\s*\d+(?:\.\d+)?\b", text.lower()):
        score += 1
    if re.search(r"\d{2,5}\s*(?:nit|cd/?m2)", text.lower()):
        score += 1
    if extract_power_consumption_kw(text):
        score += 1
    if extract_refresh_rate_hz(text):
        score += 1
    return score


def _strip_header_footer_noise(line: str) -> str:
    lower = line.lower()
    noise_tokens = [
        "주소",
        "tel",
        "fax",
        "email",
        "사업자",
        "대표",
        "등록번호",
        "문서번호",
        "견적번호",
        "bank",
        "계좌",
        "담당자",
        "수신",
        "귀중",
    ]
    if not any(token in lower for token in noise_tokens):
        return line
    spec_match = re.search(
        r"(?:\b(?:46|49|55)\s*(?:\"|인치|inch)|LED|비디오월|Video\s*Wall|DID|"
        r"P\s*\d+(?:\.\d+)?|해상도|전체\s*크기|화면\s*크기|밝기|Pixel\s*Pitch|"
        r"Screen\s*Size|Display\s*Size)",
        line,
        re.IGNORECASE,
    )
    if spec_match:
        return line[spec_match.start():].strip(" :-\t")
    return ""


def _cut_header_footer_tail(text: str) -> str:
    if not text:
        return ""
    parts = re.split(
        r"\s+(?=(?:COST\s+BREAKDOWN|견\s*적\s*서|QUOTATION|No\.|공급받는\s*자|공급자|발주처|상호|부서/담당|"
        r"대표/담당|주소|TEL|Fax|Email|사업자|대표이사|등록번호|문서번호|견적번호|Bank|계좌|"
        r"담당자|수신|귀중)\b)",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    return _strip_amount_tail(parts[0]).strip(" :-\t")


def _strip_amount_tail(text: str) -> str:
    if not text:
        return ""
    parts = re.split(
        r"\s+(?=(?:COST\s+BREAKDOWN|견적금액|공급가|합계|소계|VAT|₩|"
        r"\d{1,4}\s+\d{1,3}(?:,\d{3})+\s+\d{1,3}(?:,\d{3})+)\b)",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    return parts[0].strip(" :-\t")


def _remove_controller_spec_segments(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    controller_model = (
        r"(?:S-?Box|Nova\s*Star|Novastar|Colorlight|VX\s*\d+\w*|MX\s*\d+\w*|"
        r"X\s*\d+\w*|Z\s*\d+\w*|컨트롤러|스케일러|controller|scaler)"
    )
    cleaned = re.sub(
        rf"{controller_model}(?:\s*[\w+/.-]+){{0,8}}\s*(?:\(?\s*4K\s*@\s*60\s*Hz\s*\)?)?",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _has_controller_context(text: str) -> bool:
    lower = (text or "").lower()
    return any(token in lower for token in CONTROLLER_CONTEXT_TOKENS)


def _has_display_refresh_context(text: str) -> bool:
    lower = (text or "").lower()
    return any(
        token in lower
        for token in [
            "refresh rate",
            "주사율",
            "패널 주사율",
            "led refresh",
            "3840hz",
            "3,840 hz",
            "7680hz",
            "7,680 hz",
        ]
    )
