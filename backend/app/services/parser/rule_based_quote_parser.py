import re
from datetime import datetime
from math import ceil
from typing import Any

from services.ocr.schemas import OCRResult, OCRTable
from services.parser.base import ParserProvider
from services.parser.schemas import (
    LineItem,
    LineItemCategory,
    ParsedQuoteResult,
    QuoteDocument,
    QuoteItem,
)
from services.parser.vendor_name_resolver import VendorNameResolver


class RuleBasedQuoteParser(ParserProvider):
    """
    규칙 기반 견적서 Parser.

    처리 우선순위:
    1. ocr_result.key_values
    2. ocr_result.tables
    3. ocr_result.text 정규식
    4. fallback 계산 / 추론
    """

    def parse(self, ocr_result: OCRResult) -> ParsedQuoteResult:
        source_text = self._build_source_text(ocr_result)
        normalized_text = self._normalize_text(source_text)
        key_values = getattr(ocr_result, "key_values", {}) or {}

        warnings: list[str] = []
        raw_matches: dict[str, Any] = {}

        vendor_name = self._extract_vendor_name(
            normalized_text, raw_matches
        ) or self._extract_vendor_name_from_header(normalized_text, raw_matches)
        vendor_name, vendor_debug = VendorNameResolver().resolve(
            current_vendor_name=vendor_name,
            source_text=source_text,
        )
        if vendor_name:
            raw_matches["vendor_name"] = vendor_name
            raw_matches["vendor_name_debug"] = vendor_debug

        quote_date = self._extract_quote_date_from_key_values(
            key_values, raw_matches
        ) or self._extract_quote_date(normalized_text, raw_matches)

        total_amount = self._extract_total_amount_from_key_values(
            key_values, raw_matches
        ) or self._extract_total_amount(normalized_text, raw_matches)

        supply_amount = self._extract_supply_amount_from_key_values(
            key_values, raw_matches
        ) or self._extract_supply_amount(normalized_text, raw_matches)

        tax_amount = self._extract_tax_amount_from_key_values(
            key_values, raw_matches
        ) or self._extract_tax_amount(normalized_text, raw_matches)

        delivery_days = self._extract_delivery_days(normalized_text, raw_matches)
        delivery_basis_raw = self._extract_delivery_basis_raw(normalized_text, raw_matches)

        quote_validity_days = self._extract_quote_validity_days(
            normalized_text,
            raw_matches,
        )

        warranty_months = self._extract_warranty_months(
            normalized_text,
            raw_matches,
        )

        maintenance_included = self._extract_inclusion_flag(
            text=normalized_text,
            include_patterns=[
                r"유지\s*보수\s*포함",
                r"유지\s*관리\s*포함",
                r"무상\s*유지\s*보수",
                r"A/S\s*포함",
                r"AS\s*포함",
            ],
            exclude_patterns=[
                r"유지\s*보수\s*별도",
                r"유지\s*관리\s*별도",
                r"A/S\s*별도",
                r"AS\s*별도",
            ],
        )

        installation_fee_included = self._extract_inclusion_flag(
            text=normalized_text,
            include_patterns=[
                r"설치\s*비\s*포함",
                r"설치\s*포함",
                r"시공\s*비\s*포함",
                r"시공\s*포함",
            ],
            exclude_patterns=[
                r"설치\s*비\s*별도",
                r"설치\s*별도",
                r"시공\s*비\s*별도",
                r"시공\s*별도",
            ],
        )

        delivery_fee_included = self._extract_inclusion_flag(
            text=normalized_text,
            include_patterns=[
                r"운송\s*비\s*포함",
                r"배송\s*비\s*포함",
                r"납품\s*비\s*포함",
            ],
            exclude_patterns=[
                r"운송\s*비\s*별도",
                r"배송\s*비\s*별도",
                r"납품\s*비\s*별도",
            ],
        )

        payment_terms = self._extract_payment_terms(normalized_text, raw_matches)
        special_terms = self._extract_special_terms(normalized_text)

        items = self._extract_items_from_tables(ocr_result.tables)

        if not items:
            items = self._extract_items_from_text(normalized_text)

        items = self._filter_valid_items(items)

        if (
            supply_amount is None
            and total_amount is not None
            and tax_amount is not None
        ):
            supply_amount = total_amount - tax_amount
            raw_matches["supply_amount_calculated"] = supply_amount

        if installation_fee_included is None:
            installation_fee_included = self._infer_installation_fee_from_items(items)

        special_terms = self._deduplicate_terms(special_terms)

        if vendor_name is None:
            warnings.append("업체명을 추출하지 못했습니다.")

        if total_amount is None:
            warnings.append("총 견적 금액을 추출하지 못했습니다.")

        if delivery_days is None and not delivery_basis_raw:
            warnings.append(
                "납기 정보가 문서에 명시되어 있지 않거나 추출되지 않았습니다."
            )
        elif delivery_days is None and delivery_basis_raw == "별도협의":
            warnings.append("납기 별도협의")

        quote_document = self._build_quote_document(
            vendor_name=vendor_name,
            quote_date=quote_date,
            total_amount=total_amount,
            supply_amount=supply_amount,
            tax_amount=tax_amount,
            delivery_days=delivery_days,
            warranty_months=warranty_months,
            payment_terms=payment_terms,
            special_terms=special_terms,
            maintenance_included=maintenance_included,
            installation_fee_included=installation_fee_included,
            delivery_fee_included=delivery_fee_included,
            items=items,
            key_values=key_values,
            text=normalized_text,
            raw_matches=raw_matches,
        )

        return ParsedQuoteResult(
            quote_document=quote_document,
            source_text=source_text,
            warnings=warnings,
            raw_matches=raw_matches,
        )

    def _build_quote_document(
        self,
        *,
        vendor_name: str | None,
        quote_date: str | None,
        total_amount: int | None,
        supply_amount: int | None,
        tax_amount: int | None,
        delivery_days: int | None,
        warranty_months: int | None,
        payment_terms: str | None,
        special_terms: list[str],
        maintenance_included: bool | None,
        installation_fee_included: bool | None,
        delivery_fee_included: bool | None,
        items: list[QuoteItem],
        key_values: dict[str, str],
        text: str,
        raw_matches: dict[str, Any],
    ) -> QuoteDocument:
        received_at = self._parse_received_at(quote_date)
        safe_vendor_name = vendor_name or ""
        quote_id = self._extract_quote_id(key_values, text) or (
            f"{safe_vendor_name}_{received_at:%Y%m%d}"
        )
        project_name = self._extract_project_name(key_values, text, raw_matches) or ""
        total_supply_price = self._resolve_total_supply_price(
            supply_amount=supply_amount,
            total_amount=total_amount,
            tax_amount=tax_amount,
        )
        delivery_weeks = ceil(delivery_days / 7) if delivery_days is not None else None
        notes_raw = self._build_notes_raw(
            payment_terms=payment_terms,
            special_terms=special_terms,
            maintenance_included=maintenance_included,
            installation_fee_included=installation_fee_included,
            delivery_fee_included=delivery_fee_included,
        )
        line_items = [self._quote_item_to_line_item(item) for item in items]

        confidence = 0.8
        if not safe_vendor_name or total_supply_price == 0 or not line_items:
            confidence = 0.5

        return QuoteDocument(
            vendor_name=safe_vendor_name,
            quote_id=quote_id,
            received_at=received_at,
            project_name=project_name,
            total_supply_price=total_supply_price,
            total_with_vat=total_amount,
            currency="KRW",
            delivery_weeks=delivery_weeks,
            delivery_basis_raw=raw_matches.get("delivery_basis_raw") or str(delivery_days or ""),
            warranty_months=warranty_months,
            notes_raw=notes_raw,
            source_file_path="",
            source_file_hash="",
            extraction_confidence=confidence,
            line_items=line_items,
        )

    def _parse_received_at(self, quote_date: str | None) -> datetime:
        if quote_date:
            try:
                return datetime.strptime(quote_date, "%Y-%m-%d")
            except ValueError:
                pass

        return datetime.now()

    def _resolve_total_supply_price(
        self,
        *,
        supply_amount: int | None,
        total_amount: int | None,
        tax_amount: int | None,
    ) -> int:
        if supply_amount is not None:
            return supply_amount

        if total_amount is not None and tax_amount is not None:
            return total_amount - tax_amount

        if total_amount is not None:
            return total_amount

        return 0

    def _extract_quote_id(
        self,
        key_values: dict[str, str],
        text: str,
    ) -> str | None:
        label_patterns = [
            r"견적\s*(?:번호|No\.?|NO\.?)",
            r"quote\s*(?:id|no\.?|number)",
        ]
        return self._extract_labeled_text_value(key_values, text, label_patterns)

    def _extract_project_name(
        self,
        key_values: dict[str, str],
        text: str,
        raw_matches: dict[str, Any],
    ) -> str | None:
        korean_project_name = self._extract_korean_project_name(text, raw_matches)
        if korean_project_name:
            return korean_project_name

        label_patterns = [
            r"건명",
            r"프로젝트\s*명",
            r"프로젝트명",
            r"공사명",
        ]
        project_name = self._extract_labeled_text_value(key_values, text, label_patterns)

        if project_name:
            raw_matches["project_name"] = project_name

        return project_name

    def _extract_korean_project_name(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> str | None:
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        for index, line in enumerate(lines):
            compact = line.replace(" ", "")
            if "견적명" in compact:
                value = self._value_after_project_label(line, "견적명")
                if value:
                    raw_matches["project_name"] = value
                    return value

                value = self._join_project_value_lines(lines, index + 1)
                if value:
                    raw_matches["project_name"] = value
                    return value

            if compact in {"건명", "건명:"} or compact.startswith("건명/"):
                value = self._value_after_project_label(line, "건명")
                if value:
                    raw_matches["project_name"] = value
                    return value

                value = self._join_project_value_lines(lines, index + 1)
                if value:
                    raw_matches["project_name"] = value
                    return value

        return None

    def _value_after_project_label(self, line: str, label: str) -> str | None:
        compact_label_pattern = r"\s*".join(re.escape(char) for char in label)
        match = re.search(
            rf"{compact_label_pattern}\s*[:：/\-|]?\s*(?P<value>.+)$",
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        value = match.group("value").strip(" :：/-|")
        return self._clean_project_name(value)

    def _join_project_value_lines(self, lines: list[str], start_index: int) -> str | None:
        values = []
        stop_labels = {
            "견적금액",
            "날짜",
            "담당자",
            "문서번호",
            "공급자",
            "사업자등록번호",
            "대표자",
            "사업장주소",
            "LED디스플레이견적",
            "견적일",
            "작성자",
        }

        for line in lines[start_index : start_index + 3]:
            compact = line.replace(" ", "")
            if any(compact.startswith(label) for label in stop_labels):
                break
            cleaned = self._clean_project_name(line)
            if cleaned:
                values.append(cleaned)

        return self._clean_project_name(" ".join(values))

    def _clean_project_name(self, value: str | None) -> str | None:
        if not value:
            return None

        value = re.sub(r"\s+", " ", value).strip(" :：/-|")
        if not value:
            return None

        if value in {"-", "해당없음"}:
            return None

        return value[:200]

    def _extract_labeled_text_value(
        self,
        key_values: dict[str, str],
        text: str,
        label_patterns: list[str],
    ) -> str | None:
        for key, value in key_values.items():
            if any(re.search(pattern, key, flags=re.IGNORECASE) for pattern in label_patterns):
                cleaned = self._clean_field_value(value)
                if cleaned:
                    return cleaned

        label_pattern = "|".join(label_patterns)
        match = re.search(
            rf"(?:{label_pattern})\s*[:：]?\s*(?P<value>[^\n|]+)",
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        return self._clean_field_value(match.group("value"))

    def _build_notes_raw(
        self,
        *,
        payment_terms: str | None,
        special_terms: list[str],
        maintenance_included: bool | None,
        installation_fee_included: bool | None,
        delivery_fee_included: bool | None,
    ) -> str:
        notes: list[str] = []

        if payment_terms:
            notes.append(f"결제조건: {payment_terms}")

        notes.extend(special_terms)

        for label, value in [
            ("유지보수 포함 여부", maintenance_included),
            ("설치비 포함 여부", installation_fee_included),
            ("배송비 포함 여부", delivery_fee_included),
        ]:
            if value is not None:
                notes.append(f"{label}: {value}")

        return "\n".join(self._deduplicate_terms(notes))

    def _quote_item_to_line_item(self, item: QuoteItem) -> LineItem:
        spec_raw = " ".join(
            value
            for value in [item.spec, item.note]
            if value
        )
        category = self._classify_line_item_category(item, spec_raw)
        spec_parsed = self._extract_spec_parsed(category, item, spec_raw)

        confidence = 0.8
        if not item.item_name or item.quantity is None:
            confidence = 0.5

        return LineItem(
            name=item.item_name or "",
            category=category,
            quantity=item.quantity if item.quantity is not None else 0.0,
            unit=item.unit or "",
            unit_price=item.unit_price,
            total_price=item.amount if item.amount is not None else item.supply_amount,
            is_optional=self._is_optional_line_item(item, spec_raw),
            spec_raw=spec_raw,
            spec_parsed=spec_parsed,
            extraction_confidence=confidence,
        )

    def _classify_line_item_category(
        self,
        item: QuoteItem,
        spec_raw: str,
    ) -> LineItemCategory:
        text = " ".join(
            value
            for value in [item.item_name, item.spec, item.note, spec_raw]
            if value
        )
        normalized = text.lower()

        if any(
            keyword.lower() in normalized
            for keyword in ["LED", "전광판", "비디오월", "DLED", "LCD", "Display"]
        ):
            return LineItemCategory.DISPLAY

        if any(keyword in normalized for keyword in ["브라켓", "마운트", "거치대", "구조물", "보강대"]):
            return LineItemCategory.MOUNT

        if any(
            keyword.lower() in normalized
            for keyword in [
                "플레이어",
                "player",
                "Colorlight",
                "processor",
                "프로세서",
                "controller",
            ]
        ):
            return LineItemCategory.PLAYER

        if any(keyword.lower() in normalized for keyword in ["케이블", "잡자재", "cable"]):
            return LineItemCategory.CABLE

        if any(keyword in normalized for keyword in ["설치", "시공", "시운전", "교육"]):
            return LineItemCategory.INSTALL

        if any(keyword.lower() in normalized for keyword in ["software", "소프트웨어", "라이선스"]):
            return LineItemCategory.SOFTWARE

        return LineItemCategory.ETC

    def _extract_spec_parsed(
        self,
        category: LineItemCategory,
        item: QuoteItem,
        spec_raw: str,
    ) -> dict[str, Any]:
        text = " ".join(
            value
            for value in [item.item_name, item.spec, item.note, spec_raw]
            if value
        )
        spec_parsed: dict[str, Any] = {}

        if category == LineItemCategory.DISPLAY:
            pitch = self._extract_pitch_mm(text)
            size = self._extract_size_raw(text)
            brightness = self._extract_brightness_nit(text)
            panel_size = self._extract_panel_size_inch(text)
            resolution = self._extract_resolution(text)

            if pitch is not None:
                spec_parsed["pitch_mm"] = pitch
            if size:
                spec_parsed["full_screen_size_mm"] = size
            if brightness is not None:
                spec_parsed["brightness_nit"] = brightness
            if panel_size is not None:
                spec_parsed["panel_size_inch"] = panel_size
            if resolution:
                spec_parsed["resolution"] = resolution

        elif category == LineItemCategory.PLAYER:
            model = self._extract_player_model(text)
            if model:
                spec_parsed["model"] = model
            else:
                spec_parsed["spec"] = text.strip()

        elif category == LineItemCategory.INSTALL:
            scope = self._extract_install_scope(text)
            if scope:
                spec_parsed["scope"] = scope

        return spec_parsed

    def _extract_pitch_mm(self, text: str) -> float | None:
        patterns = [
            r"\bP\s*(?P<value>\d+(?:\.\d+)?)",
            r"Pitch\s*[:：]?\s*(?:\(mm\)\s*)?(?P<value>\d+(?:\.\d+)?)",
            r"pitch\s*\(mm\)\s*(?P<value>\d+(?:\.\d+)?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return float(match.group("value"))

        return None

    def _extract_size_raw(self, text: str) -> str | None:
        full_size_match = re.search(
            r"(?P<size>\d{1,3}(?:,\d{3})+|\d{3,5})\s*[xX×]\s*(?:\d{1,3}(?:,\d{3})+|\d{3,5})",
            text,
        )

        if full_size_match:
            return full_size_match.group(0)

        return None

    def _extract_brightness_nit(self, text: str) -> int | None:
        match = re.search(r"(?P<value>\d{3,5})\s*nit", text, flags=re.IGNORECASE)
        if not match:
            return None

        return int(match.group("value"))

    def _extract_panel_size_inch(self, text: str) -> float | None:
        match = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*(?:\"|인치)", text)
        if not match:
            return None

        return float(match.group("value"))

    def _extract_resolution(self, text: str) -> str | None:
        match = re.search(
            r"(?P<resolution>(?:\d{3,5}\s*[xX×]\s*\d{3,5})|(?:FHD|UHD|4K|8K))",
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        return match.group("resolution")

    def _extract_player_model(self, text: str) -> str | None:
        match = re.search(
            r"\b(?P<model>[A-Z][A-Za-z0-9_-]{2,})\b",
            text,
        )

        if match:
            return match.group("model")

        return None

    def _extract_install_scope(self, text: str) -> str | None:
        for keyword in ["설치", "시공", "시운전", "교육"]:
            if keyword in text:
                return text.strip()

        return None

    def _is_optional_line_item(self, item: QuoteItem, spec_raw: str) -> bool:
        text = " ".join(value for value in [item.item_name, spec_raw] if value)
        return bool(re.search(r"옵션|선택|별도", text, flags=re.IGNORECASE))

    def _build_source_text(self, ocr_result: OCRResult) -> str:
        text_parts: list[str] = []

        if ocr_result.text:
            text_parts.append(ocr_result.text)

        for table in ocr_result.tables:
            for row in table.cells:
                text_parts.append(" | ".join(row))

        return "\n".join(text_parts)

    def _normalize_text(self, text: str) -> str:
        text = text.replace(":unselected:", " ")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # ---------------------------------------------------------------------
    # Key-Value 기반 추출
    # ---------------------------------------------------------------------

    def _extract_quote_date_from_key_values(
        self,
        key_values: dict[str, str],
        raw_matches: dict[str, Any],
    ) -> str | None:
        for key, value in key_values.items():
            compact_key = key.replace(" ", "")

            if compact_key in {"견적일자", "견적일", "견적일시"}:
                normalized = self._normalize_date(value)

                if normalized:
                    raw_matches["quote_date_from_key_value"] = f"{key}: {value}"
                    return normalized

        return None

    def _extract_total_amount_from_key_values(
        self,
        key_values: dict[str, str],
        raw_matches: dict[str, Any],
    ) -> int | None:
        priority_keywords = [
            "전체합계",
            "VAT포함",
            "총액",
            "총금액",
            "합계금액",
            "공급대가",
        ]

        for keyword in priority_keywords:
            for key, value in key_values.items():
                compact_key = key.replace(" ", "")

                if keyword in compact_key:
                    amount = self._parse_amount(value)

                    if amount is not None:
                        raw_matches["total_amount_from_key_value"] = f"{key}: {value}"
                        return amount

        return None

    def _extract_supply_amount_from_key_values(
        self,
        key_values: dict[str, str],
        raw_matches: dict[str, Any],
    ) -> int | None:
        for key, value in key_values.items():
            compact_key = key.replace(" ", "")

            if "부가" in compact_key or "VAT" in compact_key or "전체" in compact_key:
                continue

            if compact_key in {"합계", "공급가액", "공급금액", "공급액"}:
                amount = self._parse_amount(value)

                if amount is not None:
                    raw_matches["supply_amount_from_key_value"] = f"{key}: {value}"
                    return amount

        return None

    def _extract_tax_amount_from_key_values(
        self,
        key_values: dict[str, str],
        raw_matches: dict[str, Any],
    ) -> int | None:
        for key, value in key_values.items():
            compact_key = key.replace(" ", "")

            is_tax_key = (
                "부가가치세" in compact_key
                or "부가세" in compact_key
                or "세액" in compact_key
                or compact_key == "VAT"
            )

            if not is_tax_key:
                continue

            amount = self._parse_amount(value)

            if amount is not None:
                raw_matches["tax_amount_from_key_value"] = f"{key}: {value}"
                return amount

        return None

    # ---------------------------------------------------------------------
    # 기본 필드 추출
    # ---------------------------------------------------------------------

    def _extract_vendor_name(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> str | None:
        patterns = [
            r"(?:상호\s*\(?법인명\)?|상호\(법인명\)|업체명|공급자|공급업체|회사명|견적업체)\s*[:：]?\s*([^\n|]+)",
            r"(?:Vendor|Company)\s*[:：]?\s*([^\n|]+)",
        ]

        value = self._find_first_group(text, patterns)

        if value:
            cleaned = self._clean_company_value(value)

            if cleaned and cleaned not in {"법인명", "(법인명", "상호", "업체명"}:
                raw_matches["vendor_name"] = cleaned
                return cleaned

        return None

    def _extract_vendor_name_from_header(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> str | None:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidates: list[str] = []

        for line in lines[:25]:
            if "견 적 서" in line or "견적서" in line or "Quotation" in line:
                continue

            if "대표이사" in line:
                break

            if "(주)" in line or "㈜" in line:
                cleaned = self._clean_company_value(line)
                cleaned = cleaned.replace("南", "").strip()

                if cleaned:
                    candidates.append(cleaned)

        if candidates:
            vendor_name = candidates[-1]
            raw_matches["vendor_name_from_header"] = vendor_name
            return vendor_name

        return None

    def _clean_company_value(self, value: str) -> str:
        value = value.strip()

        stop_words = [
            "성명",
            "대표이사",
            "사업장주소",
            "사업자주소",
            "사업장",
            "주소",
            "업태",
            "종목",
            "Tel",
            "TEL",
            "전화",
            "Fax",
            "FAX",
            "귀하",
            "등록번호",
        ]

        for stop_word in stop_words:
            if stop_word in value:
                value = value.split(stop_word)[0]

        value = value.strip(" :：,-|")
        value = value.strip()
        if value.startswith("주)"):
            value = "(" + value

        return value.strip()

    def _extract_quote_date(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> str | None:
        labeled_patterns = [
            r"(?:견적일|견적일자|작성일|발행일|견적일시)\s*[:：]?\s*(\d{4}[.\-/년\s]+\d{1,2}[.\-/월\s]+\d{1,2})",
        ]

        value = self._find_first_group(text, labeled_patterns)

        if value:
            normalized = self._normalize_date(value)
            raw_matches["quote_date"] = value
            return normalized

        general_date_pattern = r"(\d{4})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})"

        match = re.search(general_date_pattern, text)

        if match:
            year, month, day = match.groups()
            raw_matches["quote_date"] = match.group(0)
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

        return None

    def _extract_total_amount(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> int | None:
        labeled_patterns = [
            r"(?:전체\s*합\s*계|합\s*계\s*금\s*액|합계금액|총\s*견적\s*금액|총\s*금액|견적\s*금액|총액|공급대가)\s*(?:\(.*?\))?\s*[:：]?\s*([₩￦Ww\(\)\d,.\s]+(?:원|만원|천만원|백만원|억원|억)?)",
            r"(?:Total|Amount)\s*[:：]?\s*([₩￦Ww\(\)\d,.\s]+(?:KRW|원)?)",
        ]

        value = self._find_first_group(text, labeled_patterns)

        if value:
            amount = self._parse_amount(value)

            if amount is not None:
                raw_matches["total_amount"] = value
                return amount

        amount_candidates = self._find_amount_candidates(text)

        if amount_candidates:
            max_amount = max(amount_candidates)
            raw_matches["total_amount_fallback_max"] = max_amount
            return max_amount

        return None

    def _extract_supply_amount(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> int | None:
        patterns = [
            r"(?:공급\s*가\s*액|공급가액|공급\s*금액|공급액)\s*[:：]?\s*([₩￦Ww\(\)\d,.\s]+(?:원)?)",
        ]

        value = self._find_first_group(text, patterns)

        if value:
            amount = self._parse_amount(value)

            if amount is not None:
                raw_matches["supply_amount"] = value
                return amount

        for line in text.splitlines():
            compact_line = line.replace(" ", "")

            if "합계" not in compact_line:
                continue

            if "전체합계" in compact_line or "VAT포함" in compact_line:
                continue

            amounts = self._extract_amounts_from_line(line)

            if amounts:
                raw_matches["supply_amount_fallback"] = line
                return amounts[-1]

        return None

    def _extract_tax_amount(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> int | None:
        patterns = [
            r"(?:세\s*액|세액|부가\s*가치\s*세|부가\s*세|부가세)\s*[:：]?\s*([₩￦Ww\(\)\d,.\s]+(?:원)?)",
        ]

        value = self._find_first_group(text, patterns)

        if value:
            amount = self._parse_amount(value)

            if amount is not None:
                raw_matches["tax_amount"] = value
                return amount

        for line in text.splitlines():
            compact_line = line.replace(" ", "")

            is_tax_line = (
                "부가가치세" in compact_line
                or "부가세" in compact_line
                or "세액" in compact_line
            )

            if not is_tax_line:
                continue

            amounts = self._extract_amounts_from_line(line)

            if amounts:
                raw_matches["tax_amount_fallback_vat_line"] = line
                return amounts[-1]

        return None

    def _extract_delivery_days(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> int | None:
        patterns = [
            r"(?:납기|납품\s*기간|배송\s*기간|리드타임|소요\s*기간)\s*[:：]?\s*(?:계약\s*후|발주\s*후)?\s*(\d+)\s*(영업일|일|주|개월|달)",
            r"(?:계약\s*후|발주\s*후)\s*(\d+)\s*(영업일|일|주|개월|달)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)

            if match:
                number = int(match.group(1))
                unit = match.group(2)
                days = self._duration_to_days(number, unit)

                raw_matches["delivery_days"] = match.group(0)
                return days

        return None

    def _extract_delivery_basis_raw(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> str | None:
        for line in text.splitlines():
            cleaned = re.sub(r"\s+", " ", line).strip(" -*•\t|")
            compact = cleaned.replace(" ", "")
            if "도입가능일" not in compact:
                continue

            if "별도협의" in compact:
                raw_matches["delivery_basis_raw"] = "별도협의"
                raw_matches["delivery_basis_raw_source"] = cleaned
                return "별도협의"

            match = re.search(r"도\s*입\s*가\s*능\s*일\s*[:：]?\s*(?P<value>.+)$", cleaned)
            if match:
                value = match.group("value").strip(" :：|-")
                if value:
                    raw_matches["delivery_basis_raw"] = value
                    raw_matches["delivery_basis_raw_source"] = cleaned
                    return value

        return None

    def _extract_quote_validity_days(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> int | None:
        patterns = [
            r"(?:견적\s*유효\s*기간|유효\s*기간)\s*[:：]?\s*(?:견적일로부터)?\s*(\d+)\s*(일|주|개월|달)",
            r"견적일로부터\s*(\d+)\s*(일|주|개월|달)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)

            if match:
                number = int(match.group(1))
                unit = match.group(2)
                days = self._duration_to_days(number, unit)

                raw_matches["quote_validity_days"] = match.group(0)
                return days

        return None

    def _extract_warranty_months(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> int | None:
        korean_warranty_months = self._extract_korean_free_warranty_months(
            text,
            raw_matches,
        )
        if korean_warranty_months is not None:
            return korean_warranty_months

        patterns = [
            r"(?:제품\s*)?(?:무상\s*)?(?:보증\s*기간|보증기간|하자\s*보증|Warranty)\s*[:：]?\s*(?:준공일로부터|납품일로부터|설치일로부터)?\s*(\d+)\s*(년|개월|달)",
            r"(?:제품\s*)?무상\s*보증\s*기간\s*[:：]?\s*(?:준공일로부터|납품일로부터|설치일로부터)?\s*(\d+)\s*(년|개월|달)",
            r"(?:준공일로부터|납품일로부터|설치일로부터)\s*(\d+)\s*(년|개월|달)",
            r"(\d+)\s*(년|개월|달)\s*(?:무상\s*)?(?:보증|하자보증)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)

            if match:
                number = int(match.group(1))
                unit = match.group(2)
                months = self._duration_to_months(number, unit)

                raw_matches["warranty_months"] = match.group(0)
                return months

        return None

    def _extract_korean_free_warranty_months(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> int | None:
        warranty_keywords = [
            "유지보수",
            "무상보수",
            "무상보수기간",
            "무상보증",
            "보증기간",
            "제품무상보증기간",
            "A/S",
            "AS",
            "시공후",
            "시공 후",
            "설치완료일로부터",
            "설치완료 후",
            "납품일로부터",
            "납품완료후",
            "납품완료 후",
            "준공일로부터",
        ]

        for line in self._warranty_candidate_lines(text):
            compact = line.replace(" ", "")
            compact_upper = compact.upper()

            if "유상" in compact and "무상" not in compact:
                continue

            has_warranty_context = any(
                keyword in line or keyword.replace(" ", "") in compact
                for keyword in warranty_keywords
            )
            has_free_context = "무상" in compact
            has_warranty_label = any(
                keyword in line or keyword.replace(" ", "") in compact
                for keyword in ["무상보증", "보증기간", "제품무상보증기간"]
            ) or "무상보수기간" in compact or "AS" in compact_upper

            if not has_warranty_context:
                continue

            if not has_free_context and not has_warranty_label:
                continue

            months = self._extract_months_from_korean_duration(line)
            if months is None:
                continue

            raw_matches["warranty_months"] = line
            if "출장실비" in line and "별도" in line:
                raw_matches["warranty_condition_check_required"] = "출장실비 별도 조건 확인 필요"
            return months

        return None

    def _warranty_candidate_lines(self, text: str) -> list[str]:
        lines = []
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip(" -*•\t")
            if line:
                lines.append(line)
        return lines

    def _extract_months_from_korean_duration(self, text: str) -> int | None:
        year_match = re.search(r"(?P<number>\d+(?:\.\d+)?)\s*년", text)
        if year_match:
            return int(float(year_match.group("number")) * 12)

        month_match = re.search(r"(?P<number>\d+(?:\.\d+)?)\s*개월", text)
        if month_match:
            return int(float(month_match.group("number")))

        return None

    def _extract_payment_terms(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> str | None:
        patterns = [
            r"(?:결제\s*조건은|결제\s*조건|결재\s*조건|지급\s*조건|대금\s*지급|대금\s*결제\s*조건|대금\s*결재\s*조건|Payment Terms)\s*[:：]?\s*([^\n]+)",
            r"\d+\.\s*(?:결제|결재|대금결제|대금결재)\s*조건\s*[:：은]?\s*([^\n]+)",
        ]

        value = self._find_first_group(text, patterns)

        if value:
            cleaned = self._clean_payment_terms(value)
            raw_matches["payment_terms"] = cleaned
            return cleaned

        for line in text.splitlines():
            stripped = line.strip()

            if any(
                keyword in stripped
                for keyword in ["결제", "결재", "대금결제", "대금결재"]
            ):
                cleaned = re.sub(r"^\d+\.\s*", "", stripped).strip()
                cleaned = self._clean_payment_terms(cleaned)

                raw_matches["payment_terms_fallback"] = stripped
                return cleaned

        return None

    def _clean_payment_terms(self, value: str) -> str:
        value = value.strip()

        remove_tokens = [
            "결제조건은",
            "결제 조건은",
            "결제조건",
            "결제 조건",
            "결재조건은",
            "결재 조건은",
            "결재조건",
            "결재 조건",
            "대금결제조건",
            "대금 결제 조건",
            "대금결재조건",
            "대금 결재 조건",
        ]

        for token in remove_tokens:
            value = value.replace(token, "")

        value = re.split(r"\s+\d+\.\s+", value)[0]
        value = value.strip(" :：,-")

        return value

    def _extract_special_terms(self, text: str) -> list[str]:
        terms: list[str] = []

        keywords = [
            "별도",
            "포함",
            "무상",
            "유상",
            "추가 비용",
            "계약 전 확인",
            "VAT",
            "부가세",
            "부가가치세",
            "운송비",
            "배송비",
            "납품비",
            "설치비",
            "시공비",
            "유지보수",
            "A/S",
            "AS",
            "견적유효기간",
            "유효기간",
            "결제조건",
            "결재조건",
            "대금결재조건",
            "대금결제조건",
            "제품무상보증기간",
            "보증기간",
        ]

        for line in text.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            if any(keyword in stripped for keyword in keywords):
                terms.append(stripped)

        return terms[:30]

    def _extract_inclusion_flag(
        self,
        text: str,
        include_patterns: list[str],
        exclude_patterns: list[str],
    ) -> bool | None:
        for pattern in exclude_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return False

        for pattern in include_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True

        return None

    # ---------------------------------------------------------------------
    # 품목 추출
    # ---------------------------------------------------------------------

    def _extract_items_from_tables(self, tables: list[OCRTable]) -> list[QuoteItem]:
        items: list[QuoteItem] = []

        for table in tables:
            if not table.cells:
                continue

            header_index = self._find_header_row_index(table.cells)

            if header_index is None:
                continue

            headers = table.cells[header_index]
            column_map = self._build_column_map(headers)

            for row in table.cells[header_index + 1 :]:
                item = self._row_to_quote_item(row, column_map)

                if item:
                    items.append(item)

        return items

    def _extract_items_from_text(self, text: str) -> list[QuoteItem]:
        items: list[QuoteItem] = []

        item_pattern = re.compile(
            r"(?P<item_name>.+?)\s+"
            r"(?P<spec>\d+(?:\.\d+)?\s*[xX×]\s*\d+(?:\.\d+)?\s*m?)\s+"
            r"(?P<quantity>\d+(?:\.\d+)?)\s+"
            r"(?P<unit>[^\s]+)\s+"
            r"(?P<unit_price>\d{1,3}(?:,\d{3})+|\d+)\s+"
            r"(?P<supply_amount>\d{1,3}(?:,\d{3})+|\d+)\s+"
            r"(?P<tax_amount>\d{1,3}(?:,\d{3})+|\d+)"
            r"(?:\s+(?P<note>.*))?"
        )

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            if any(
                keyword in line
                for keyword in [
                    "품 명",
                    "품명",
                    "규 격",
                    "규격",
                    "수 량",
                    "수량",
                    "단 위",
                    "단위",
                    "단 가",
                    "단가",
                    "공 급 가 액",
                    "공급가액",
                    "세 액",
                    "세액",
                    "비 고",
                    "비고",
                    "합 계",
                    "합계",
                    "소계",
                    "총계",
                    "특기사항",
                    "***",
                    "太太太",
                ]
            ):
                continue

            match = item_pattern.search(line)

            if not match:
                continue

            note = match.group("note")

            item = QuoteItem(
                item_name=match.group("item_name").strip(),
                spec=match.group("spec").strip(),
                quantity=self._parse_number(match.group("quantity")),
                unit=match.group("unit").strip(),
                unit_price=self._parse_amount(match.group("unit_price")),
                supply_amount=self._parse_amount(match.group("supply_amount")),
                tax_amount=self._parse_amount(match.group("tax_amount")),
                amount=None,
                note=self._clean_note(note),
            )

            if item.supply_amount is not None and item.tax_amount is not None:
                item.amount = item.supply_amount + item.tax_amount

            items.append(item)

        return items

    def _find_header_row_index(self, rows: list[list[str]]) -> int | None:
        header_keywords = [
            "품목",
            "품 명",
            "제품",
            "항목",
            "수량",
            "수 량",
            "단가",
            "단 가",
            "금액",
            "금 액",
            "공급가액",
            "세액",
            "합계",
        ]

        for idx, row in enumerate(rows):
            joined = " ".join(row)

            if sum(keyword in joined for keyword in header_keywords) >= 2:
                return idx

        return None

    def _build_column_map(self, headers: list[str]) -> dict[str, int]:
        column_map: dict[str, int] = {}

        for idx, header in enumerate(headers):
            header_text = header.strip().replace(" ", "")

            if any(
                keyword in header_text
                for keyword in ["품명", "품목", "제품", "항목", "명칭"]
            ):
                column_map["item_name"] = idx

            elif "상세내역" in header_text or "상세" in header_text:
                column_map["note"] = idx

            elif "규격" in header_text or "사양" in header_text:
                column_map["spec"] = idx

            elif "수량" in header_text or "Qty" in header_text:
                column_map["quantity"] = idx

            elif "단위" in header_text:
                column_map["unit"] = idx

            elif "단가" in header_text:
                column_map["unit_price"] = idx

            elif "공급가액" in header_text or "공급액" in header_text:
                column_map["supply_amount"] = idx

            elif "세액" in header_text or "부가세" in header_text:
                column_map["tax_amount"] = idx

            elif "금액" in header_text or "합계" in header_text:
                column_map["amount"] = idx

            elif "비고" in header_text:
                column_map["note"] = idx

        return column_map

    def _row_to_quote_item(
        self,
        row: list[str],
        column_map: dict[str, int],
    ) -> QuoteItem | None:
        def get_value(key: str) -> str | None:
            index = column_map.get(key)

            if index is None:
                return None

            if index >= len(row):
                return None

            value = row[index].strip()

            return value or None

        item_name = get_value("item_name")
        spec = get_value("spec")
        quantity_text = get_value("quantity")
        unit = get_value("unit")
        unit_price_text = get_value("unit_price")
        supply_amount_text = get_value("supply_amount")
        tax_amount_text = get_value("tax_amount")
        amount_text = get_value("amount")
        note = get_value("note")

        compact_name = (item_name or "").replace(" ", "").strip()

        if compact_name in {"합계", "총계", "소계", "계"}:
            return None

        if not item_name and not amount_text and not supply_amount_text:
            return None

        supply_amount = self._parse_amount(supply_amount_text)
        tax_amount = self._parse_amount(tax_amount_text)
        amount = self._parse_amount(amount_text)

        if amount is None and supply_amount is not None and tax_amount is not None:
            amount = supply_amount + tax_amount

        item = QuoteItem(
            item_name=item_name,
            spec=spec,
            quantity=self._parse_number(quantity_text),
            unit=unit,
            unit_price=self._parse_amount(unit_price_text),
            supply_amount=supply_amount,
            tax_amount=tax_amount,
            amount=amount,
            note=self._clean_note(note),
        )

        if self._is_invalid_item(item):
            return None

        return item

    def _clean_note(self, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.replace(":unselected:", " ")
        value = re.sub(r"\s+", " ", value).strip()

        return value or None

    def _filter_valid_items(self, items: list[QuoteItem]) -> list[QuoteItem]:
        valid_items: list[QuoteItem] = []

        for item in items:
            if self._is_invalid_item(item):
                continue

            valid_items.append(item)

        return valid_items

    def _is_invalid_item(self, item: QuoteItem) -> bool:
        item_name = (item.item_name or "").strip()
        spec = (item.spec or "").strip()
        unit = (item.unit or "").strip()
        note = (item.note or "").strip()

        joined_text = " ".join([item_name, spec, unit, note]).strip()
        compact_name = item_name.replace(" ", "").strip()

        if not joined_text and item.amount is None and item.supply_amount is None:
            return True

        summary_keywords = {
            "합계",
            "총계",
            "소계",
            "계",
            "공급가액",
            "세액",
            "부가세",
            "부가가치세",
        }

        if compact_name in summary_keywords:
            return True

        dummy_patterns = [
            r"^\*+$",
            r"^[\*\-\_]+$",
            r"^[太大]{2,}$",
            r"^x\s*이하$",
            r"^\^+$",
        ]

        for pattern in dummy_patterns:
            if re.fullmatch(pattern, compact_name):
                return True

        meaningful_chars = re.findall(r"[가-힣A-Za-z0-9]", item_name)

        if len(meaningful_chars) < 2:
            return True

        has_amount_info = any(
            value is not None
            for value in [
                item.unit_price,
                item.supply_amount,
                item.tax_amount,
                item.amount,
            ]
        )

        if not has_amount_info:
            return True

        if item.quantity is None and item.supply_amount is None and item.amount is None:
            return True

        return False

    def _infer_installation_fee_from_items(
        self,
        items: list[QuoteItem],
    ) -> bool | None:
        for item in items:
            item_name = (item.item_name or "").replace(" ", "")

            if "설치" in item_name and (
                item.amount is not None or item.supply_amount is not None
            ):
                return True

        return None

    # ---------------------------------------------------------------------
    # 공통 유틸
    # ---------------------------------------------------------------------

    def _find_first_group(
        self,
        text: str,
        patterns: list[str],
    ) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)

            if match:
                return match.group(1)

        return None

    def _find_amount_candidates(self, text: str) -> list[int]:
        candidates: list[int] = []

        comma_amount_pattern = r"[₩￦Ww]?\s*\(?\d{1,3}(?:,\d{3})+\)?(?:\s*원)?"

        for match in re.finditer(comma_amount_pattern, text):
            amount = self._parse_amount(match.group(0))

            if amount is not None:
                candidates.append(amount)

        korean_unit_pattern = (
            r"\d+(?:\.\d+)?\s*(?:억원|억|천만원|천만|백만원|백만|만원|만)"
        )

        for match in re.finditer(korean_unit_pattern, text):
            amount = self._parse_amount(match.group(0))

            if amount is not None:
                candidates.append(amount)

        return candidates

    def _extract_amounts_from_line(self, line: str) -> list[int]:
        amounts: list[int] = []

        pattern = r"[₩￦Ww]?\s*\(?\d{1,3}(?:,\d{3})+\)?"

        for match in re.finditer(pattern, line):
            amount = self._parse_amount(match.group(0))

            if amount is not None:
                amounts.append(amount)

        return amounts

    def _parse_amount(self, value: str | None) -> int | None:
        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        text = text.replace("₩", "")
        text = text.replace("￦", "")
        text = text.replace("W", "")
        text = text.replace("w", "")
        text = text.replace("KRW", "")
        text = text.replace("krw", "")
        text = text.replace("(", "")
        text = text.replace(")", "")
        text = text.strip()

        comma_match = re.search(r"\d{1,3}(?:,\d{3})+", text)

        if comma_match:
            digits = comma_match.group(0).replace(",", "")
            return int(digits)

        plain_won_match = re.search(r"(\d{5,})\s*원?", text)

        if plain_won_match:
            return int(plain_won_match.group(1))

        unit_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(억원|억|천만원|천만|백만원|백만|만원|만|원)?",
            text,
        )

        if not unit_match:
            return None

        number = float(unit_match.group(1))
        unit = unit_match.group(2) or "원"

        multiplier_map = {
            "억원": 100_000_000,
            "억": 100_000_000,
            "천만원": 10_000_000,
            "천만": 10_000_000,
            "백만원": 1_000_000,
            "백만": 1_000_000,
            "만원": 10_000,
            "만": 10_000,
            "원": 1,
        }

        multiplier = multiplier_map.get(unit, 1)

        return int(number * multiplier)

    def _parse_number(self, value: str | None) -> float | None:
        if value is None:
            return None

        match = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))

        if not match:
            return None

        return float(match.group(0))

    def _duration_to_days(self, number: int, unit: str) -> int:
        if unit == "영업일":
            return round(number * 1.4)

        if unit == "일":
            return number

        if unit == "주":
            return number * 7

        if unit in {"개월", "달"}:
            return number * 30

        return number

    def _duration_to_months(self, number: int, unit: str) -> int:
        if unit == "년":
            return number * 12

        if unit in {"개월", "달"}:
            return number

        return number

    def _normalize_date(self, value: str) -> str | None:
        match = re.search(r"(\d{4})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", value)

        if not match:
            return None

        year, month, day = match.groups()

        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    def _clean_field_value(self, value: str) -> str:
        value = value.strip()
        value = re.split(r"\s{2,}|\|", value)[0]
        value = value.strip(" :：,-")
        return value

    def _deduplicate_terms(self, terms: list[str]) -> list[str]:
        deduplicated: list[str] = []
        seen: set[str] = set()

        for term in terms:
            cleaned = re.sub(r"\s+", " ", term).strip()
            compact = cleaned.replace(" ", "")

            if not cleaned:
                continue

            if compact in seen:
                continue

            seen.add(compact)
            deduplicated.append(cleaned)

        return deduplicated
