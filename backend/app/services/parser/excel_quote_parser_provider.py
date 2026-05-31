import posixpath
import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from services.parser.schemas import LineItem, LineItemCategory, QuoteDocument


XML_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}


class ExcelQuoteParserProvider:
    def parse(self, file_path: str | Path) -> QuoteDocument:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Excel 견적서 파일을 찾을 수 없습니다: {path}")

        workbook = self._read_workbook(path)
        sheets = workbook["sheets"]

        if not sheets:
            raise ValueError(f"Excel 견적서에 시트가 없습니다: {path}")

        summary_rows = sheets[0]["rows"]
        detail_rows_by_sheet = [sheet["rows"] for sheet in sheets[1:]]

        vendor_name = self._extract_vendor_name(summary_rows)
        received_at = self._extract_received_at(summary_rows)
        project_name = self._extract_project_name(summary_rows)
        total_supply_price = self._extract_total_supply_price(summary_rows)
        total_with_vat = self._extract_total_with_vat(summary_rows)
        notes_raw = self._extract_notes(summary_rows)
        warranty_months = self._extract_warranty_months(notes_raw)
        delivery_weeks, delivery_basis_raw = self._extract_delivery(notes_raw)
        line_items = self._extract_line_items(detail_rows_by_sheet)
        quote_id = self._extract_quote_id(summary_rows) or (
            f"{vendor_name}_{received_at:%Y%m%d}"
        )

        if total_supply_price == 0:
            total_supply_price = sum(
                item.total_price or 0
                for item in line_items
                if not item.is_optional
            )

        return QuoteDocument(
            vendor_name=vendor_name,
            quote_id=quote_id,
            received_at=received_at,
            project_name=project_name,
            total_supply_price=total_supply_price,
            total_with_vat=total_with_vat,
            currency="KRW",
            delivery_weeks=delivery_weeks,
            delivery_basis_raw=delivery_basis_raw,
            warranty_months=warranty_months,
            notes_raw=notes_raw,
            extraction_confidence=0.85,
            line_items=line_items,
        )

    def extract_text_preview(
        self,
        file_path: str | Path,
        max_chars: int = 1000,
    ) -> str:
        workbook = self._read_workbook(Path(file_path))
        lines: list[str] = []

        for sheet in workbook["sheets"]:
            lines.append(f"[{sheet['name']}]")
            for row in sheet["rows"]:
                values = [str(value) for value in row if value not in (None, "")]
                if values:
                    lines.append(" | ".join(values))
                if len("\n".join(lines)) >= max_chars:
                    return "\n".join(lines)[:max_chars]

        return "\n".join(lines)[:max_chars]

    def _read_workbook(self, path: Path) -> dict[str, Any]:
        with zipfile.ZipFile(path) as archive:
            shared_strings = self._read_shared_strings(archive)
            sheet_defs = self._read_sheet_defs(archive)
            sheets = []

            for sheet_def in sheet_defs:
                rows = self._read_sheet_rows(
                    archive=archive,
                    sheet_path=sheet_def["path"],
                    shared_strings=shared_strings,
                )
                sheets.append({"name": sheet_def["name"], "rows": rows})

        return {"sheets": sheets}

    def _read_shared_strings(self, archive: zipfile.ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in archive.namelist():
            return []

        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = []

        for item in root.findall("a:si", XML_NS):
            strings.append(
                "".join(text.text or "" for text in item.findall(".//a:t", XML_NS))
            )

        return strings

    def _read_sheet_defs(self, archive: zipfile.ZipFile) -> list[dict[str, str]]:
        workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
        rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_root.findall("r:Relationship", REL_NS)
        }
        sheets = []

        for sheet in workbook_root.findall(".//a:sheet", XML_NS):
            rel_id = sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            target = rel_targets.get(rel_id or "", "")
            if not target:
                continue

            sheet_path = posixpath.normpath(posixpath.join("xl", target))
            sheets.append({"name": sheet.attrib.get("name", ""), "path": sheet_path})

        return sheets

    def _read_sheet_rows(
        self,
        *,
        archive: zipfile.ZipFile,
        sheet_path: str,
        shared_strings: list[str],
    ) -> list[list[Any]]:
        root = ET.fromstring(archive.read(sheet_path))
        rows: list[list[Any]] = []

        for row in root.findall(".//a:row", XML_NS):
            values_by_column: dict[int, Any] = {}
            max_column = -1

            for cell in row.findall("a:c", XML_NS):
                ref = cell.attrib.get("r", "")
                column = self._column_index(ref)
                max_column = max(max_column, column)
                values_by_column[column] = self._cell_value(cell, shared_strings)

            if max_column >= 0:
                rows.append(
                    [values_by_column.get(column, "") for column in range(max_column + 1)]
                )

        return rows

    def _cell_value(self, cell: ET.Element, shared_strings: list[str]) -> Any:
        cell_type = cell.attrib.get("t")

        if cell_type == "inlineStr":
            return "".join(text.text or "" for text in cell.findall(".//a:t", XML_NS))

        value = cell.find("a:v", XML_NS)
        if value is None:
            return ""

        raw = value.text or ""

        if cell_type == "s" and raw.isdigit():
            return shared_strings[int(raw)]

        if cell_type == "b":
            return raw == "1"

        return self._parse_number(raw)

    def _parse_number(self, value: str) -> Any:
        try:
            number = float(value)
        except ValueError:
            return value

        if number.is_integer():
            return int(number)

        return number

    def _column_index(self, cell_ref: str) -> int:
        letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
        index = 0

        for letter in letters:
            index = index * 26 + (ord(letter) - ord("A") + 1)

        return index - 1

    def _extract_vendor_name(self, rows: list[list[Any]]) -> str:
        for row in rows:
            if self._row_contains(row, "상 호 명"):
                value = self._value_after_label(row, "상 호 명")
                if value:
                    return value

        return ""

    def _extract_quote_id(self, rows: list[list[Any]]) -> str | None:
        for row in rows:
            for value in row:
                text = self._clean_text(value)
                match = re.search(r"No\s*:\s*(.+)", text, flags=re.IGNORECASE)
                if match:
                    return match.group(1).strip()

        return None

    def _extract_received_at(self, rows: list[list[Any]]) -> datetime:
        for row in rows:
            if self._row_contains(row, "견 적 일"):
                value = self._value_after_label(row, "견 적 일")
                parsed = self._parse_excel_date(value)
                if parsed:
                    return parsed

        return datetime.now()

    def _extract_project_name(self, rows: list[list[Any]]) -> str:
        for row in rows:
            if self._row_contains(row, "건"):
                value = self._value_after_label(row, "건")
                if value:
                    return value

        return ""

    def _extract_total_with_vat(self, rows: list[list[Any]]) -> int | None:
        for row in rows:
            if self._row_contains(row, "합 계 금 액"):
                amounts = self._amounts_from_row(row)
                if amounts:
                    return max(amounts)

        return None

    def _extract_total_supply_price(self, rows: list[list[Any]]) -> int:
        for row in rows:
            first = self._clean_text(row[0] if row else "")
            if first == "계":
                amounts = self._amounts_from_row(row)
                if amounts:
                    return max(amounts)

        return 0

    def _extract_notes(self, rows: list[list[Any]]) -> str:
        for idx, row in enumerate(rows):
            if self._row_contains(row, "특"):
                notes = []
                for next_row in rows[idx + 1 : idx + 4]:
                    text = " ".join(
                        self._clean_text(value)
                        for value in next_row
                        if self._clean_text(value)
                    )
                    if text:
                        notes.append(text)
                return "\n".join(notes).strip()

        return ""

    def _extract_delivery(self, notes: str) -> tuple[int | None, str]:
        match = re.search(r"납기일은\s*기본\s*(\d+)\s*일", notes)
        if not match:
            return None, ""

        days = int(match.group(1))
        return max(1, round(days / 7)), match.group(0)

    def _extract_warranty_months(self, notes: str) -> int | None:
        match = re.search(r"(\d+)\s*년\s*무상보증", notes)
        if match:
            return int(match.group(1)) * 12

        match = re.search(r"(\d+)\s*개월\s*무상보증", notes)
        if match:
            return int(match.group(1))

        return None

    def _extract_line_items(self, sheets: list[list[list[Any]]]) -> list[LineItem]:
        items: list[LineItem] = []

        for rows in sheets:
            display_spec_raw = self._extract_display_spec_raw(rows)
            for row in rows:
                item = self._row_to_line_item(row)
                if item:
                    if item.category == LineItemCategory.DISPLAY and "디스플레이" in item.name:
                        item.spec_raw = " ".join(
                            value for value in [item.spec_raw, display_spec_raw] if value
                        )
                        item.spec_parsed = self._extract_spec_parsed(
                            item.spec_raw,
                            item.category,
                        )
                    items.append(item)

        return items

    def _extract_display_spec_raw(self, rows: list[list[Any]]) -> str:
        spec_labels = {
            "스크린 크기",
            "해상도",
            "Pixel Pitch",
            "Module size",
            "Cabinet Size",
            "밝기",
        }
        specs = []

        for row in rows:
            label = self._clean_text(row[1] if len(row) > 1 else "")
            value = self._clean_text(row[5] if len(row) > 5 else "")

            if label in spec_labels and value:
                specs.append(f"{label}: {value}")

        return " / ".join(specs)

    def _row_to_line_item(self, row: list[Any]) -> LineItem | None:
        if len(row) < 2:
            return None

        first_cell = self._clean_text(row[0])
        name = self._clean_text(row[1] if len(row) > 1 else "")

        if not name or name in {"품 명", "특 이 사 항"} or first_cell == "계":
            return None

        if name in {"스크린 크기", "해상도", "LED Lamp", "Pixel Pitch", "Module size", "Cabinet", "Cabinet Size", "밝기", "밝기/시야각", "Refresh Rate", "전기 용량", "Maintenance", "유지보수 품목"}:
            return None

        quantity = self._float_at(row, 8)
        unit = self._clean_text(row[10] if len(row) > 10 else "")
        unit_price = self._int_at(row, 11)
        total_price = self._int_at(row, 15)
        tax_amount = self._int_at(row, 19)
        spec_raw = self._clean_text(row[5] if len(row) > 5 else "")
        note = self._clean_text(row[22] if len(row) > 22 else "")

        if quantity is None and total_price is None and unit_price is None:
            return None

        if note:
            spec_raw = " ".join(value for value in [spec_raw, note] if value)

        text = " ".join(value for value in [name, spec_raw] if value)
        category = self._classify_category(text)
        spec_parsed = self._extract_spec_parsed(text, category)
        is_optional = bool(re.search(r"옵션|선택|별도|발주시 수량 변경", text, re.IGNORECASE))
        extraction_confidence = 0.85

        if not spec_raw:
            extraction_confidence = 0.65

        return LineItem(
            name=name,
            category=category,
            quantity=quantity if quantity is not None else 0.0,
            unit=unit,
            unit_price=unit_price,
            total_price=total_price,
            is_optional=is_optional,
            spec_raw=spec_raw,
            spec_parsed=spec_parsed,
            extraction_confidence=extraction_confidence,
        )

    def _classify_category(self, text: str) -> LineItemCategory:
        normalized = text.lower()

        if any(keyword.lower() in normalized for keyword in ["플레이어", "player", "colorlight", "processor", "프로세서", "controller", "pc"]):
            return LineItemCategory.PLAYER
        if any(keyword.lower() in normalized for keyword in ["led", "전광판", "비디오월", "dled", "lcd", "display", "디스플레이"]):
            return LineItemCategory.DISPLAY
        if any(keyword.lower() in normalized for keyword in ["브라켓", "마운트", "거치대", "구조물", "보강대", "함체"]):
            return LineItemCategory.MOUNT
        if any(keyword.lower() in normalized for keyword in ["케이블", "잡자재", "cable", "배관", "배선", "전기"]):
            return LineItemCategory.CABLE
        if any(keyword.lower() in normalized for keyword in ["설치", "시공", "시운전", "교육", "인건비"]):
            return LineItemCategory.INSTALL
        if any(keyword.lower() in normalized for keyword in ["software", "소프트웨어", "라이선스"]):
            return LineItemCategory.SOFTWARE

        return LineItemCategory.ETC

    def _extract_spec_parsed(
        self,
        text: str,
        category: LineItemCategory,
    ) -> dict[str, Any]:
        spec: dict[str, Any] = {}

        pitch = self._extract_pitch(text)
        if pitch is not None:
            spec["pitch_mm"] = pitch

        size = self._extract_size(text)
        if size:
            if category == LineItemCategory.MOUNT:
                spec["cabinet_size_mm"] = size
            else:
                spec["full_screen_size_mm"] = size

        brightness = self._extract_brightness(text)
        if brightness is not None:
            spec["brightness_nit"] = brightness

        if category == LineItemCategory.PLAYER:
            model = self._extract_model(text)
            if model:
                spec["model"] = model
            elif text:
                spec["spec"] = text

        if category == LineItemCategory.INSTALL and text:
            spec["scope"] = text

        return spec

    def _extract_pitch(self, text: str) -> float | None:
        match = re.search(r"\bP\s*(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))

        match = re.search(r"Pitch\s*[:：]?\s*(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))

        return None

    def _extract_size(self, text: str) -> str | None:
        match = re.search(
            r"\d{1,3}(?:,\d{3})*\s*mm?\s*[xX×]\s*\d{1,3}(?:,\d{3})*\s*mm?",
            text,
        )
        if match:
            return match.group(0)

        match = re.search(
            r"\d{3,5}\s*[xX×]\s*\d{3,5}",
            text,
        )
        if match:
            return match.group(0)

        return None

    def _extract_brightness(self, text: str) -> int | None:
        match = re.search(r"(\d{3,5})\s*(?:nit|cd/㎡)", text, flags=re.IGNORECASE)
        if not match:
            return None

        return int(match.group(1))

    def _extract_model(self, text: str) -> str | None:
        colorlight_match = re.search(r"Colorlight\s+[A-Za-z0-9_-]+", text, flags=re.IGNORECASE)
        if colorlight_match:
            return colorlight_match.group(0)

        match = re.search(r"(Colorlight\s+[A-Za-z0-9_-]+|[A-Z][A-Za-z0-9_-]{2,})", text)
        if not match:
            return None

        return match.group(1)

    def _parse_excel_date(self, value: Any) -> datetime | None:
        if isinstance(value, (int, float)):
            return datetime(1899, 12, 30) + timedelta(days=float(value))

        text = self._clean_text(value)
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return datetime(1899, 12, 30) + timedelta(days=float(text))

        match = re.search(r"(\d{4})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", text)
        if not match:
            return None

        year, month, day = match.groups()
        return datetime(int(year), int(month), int(day))

    def _value_after_label(self, row: list[Any], label: str) -> Any:
        for index, value in enumerate(row):
            text = self._clean_text(value)
            if label in text:
                inline = text.split(":", 1)[1].strip() if ":" in text else ""
                if inline:
                    return inline
                for next_value in row[index + 1 :]:
                    cleaned = self._clean_text(next_value)
                    if cleaned:
                        return next_value
        return ""

    def _row_contains(self, row: list[Any], needle: str) -> bool:
        return any(needle in self._clean_text(value) for value in row)

    def _amounts_from_row(self, row: list[Any]) -> list[int]:
        amounts = []
        for value in row:
            amount = self._to_int(value)
            if amount is not None and amount > 0:
                amounts.append(amount)
        return amounts

    def _float_at(self, row: list[Any], index: int) -> float | None:
        if index >= len(row):
            return None

        value = row[index]
        if isinstance(value, (int, float)):
            return float(value)

        text = self._clean_text(value).replace(",", "")
        if not text:
            return None

        try:
            return float(text)
        except ValueError:
            return None

    def _int_at(self, row: list[Any], index: int) -> int | None:
        if index >= len(row):
            return None

        return self._to_int(row[index])

    def _to_int(self, value: Any) -> int | None:
        if isinstance(value, bool):
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return int(value)

        text = self._clean_text(value).replace(",", "")
        if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
            return None

        return int(float(text))

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""

        return re.sub(r"\s+", " ", str(value)).strip()
