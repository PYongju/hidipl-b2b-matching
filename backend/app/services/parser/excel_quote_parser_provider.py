import posixpath
import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from services.parser.rule_hardware_spec_context import (
    collect_hardware_spec_context,
    merge_hardware_spec_context,
)
from services.parser.rule_display_spec_extractor import extract_display_specs
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
        all_sheet_rows = [sheet["rows"] for sheet in sheets]
        detail_rows_by_sheet = [sheet["rows"] for sheet in sheets[1:]]

        vendor_name = self._extract_vendor_name(summary_rows) or self._extract_vendor_name_from_file(path)
        received_at = self._extract_received_at(summary_rows)
        project_name = self._extract_project_name(summary_rows) or self._extract_project_name_from_file(path, vendor_name)
        total_supply_price = self._extract_total_supply_price(summary_rows)
        total_with_vat = self._extract_total_with_vat(summary_rows)
        notes_raw = self._extract_notes(summary_rows)
        warranty_months = self._extract_warranty_months(notes_raw)
        delivery_weeks, delivery_basis_raw = self._extract_delivery(notes_raw)
        line_items = self._extract_line_items(detail_rows_by_sheet)
        generic_line_items = self._extract_generic_line_items(all_sheet_rows)
        if generic_line_items:
            line_items = generic_line_items
        if total_supply_price == 0:
            total_supply_price = self._extract_generic_supply_amount(summary_rows)
        if total_with_vat is None:
            total_with_vat = self._extract_generic_total_with_vat(summary_rows)
        quote_id = self._extract_quote_id(summary_rows) or (
            f"{vendor_name}_{received_at:%Y%m%d}"
        )

        if total_supply_price == 0:
            total_supply_price = sum(
                item.total_price or 0
                for item in line_items
                if not item.is_optional
            )
        total_supply_price, total_with_vat = self._reconcile_excel_amounts(
            total_supply_price=total_supply_price,
            total_with_vat=total_with_vat,
            line_items=line_items,
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

    def _reconcile_excel_amounts(
        self,
        *,
        total_supply_price: int,
        total_with_vat: int | None,
        line_items: list[LineItem],
    ) -> tuple[int, int | None]:
        line_items_sum = sum(item.total_price or 0 for item in line_items)
        if not line_items_sum:
            return total_supply_price, total_with_vat

        tolerance = max(10_000, int(max(total_supply_price, line_items_sum) * 0.03))
        if total_supply_price == 0 or abs(total_supply_price - line_items_sum) > tolerance:
            total_supply_price = line_items_sum

        expected_total = round(total_supply_price * 1.1)
        if (
            total_with_vat is None
            or total_with_vat <= total_supply_price
            or abs(total_with_vat - expected_total) > max(50_000, int(total_supply_price * 0.15))
        ):
            total_with_vat = expected_total

        return total_supply_price, total_with_vat

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

            if target.startswith("/"):
                sheet_path = posixpath.normpath(target.lstrip("/"))
            else:
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
            for label in ["상호", "상호명", "공급자", "공급사"]:
                if self._row_contains(row, label):
                    value = self._value_after_label(row, label)
                    if value:
                        return self._clean_company_suffix(value)
            if self._row_contains(row, "상 호 명"):
                value = self._value_after_label(row, "상 호 명")
                if value:
                    return value

        return ""

    def _extract_vendor_name_from_file(self, path: Path) -> str:
        tokens = [token.strip() for token in re.split(r"[_\-\s]+", path.stem) if token.strip()]
        for token in reversed(tokens):
            lowered = token.lower()
            if lowered in {"견적서", "estimate", "quotation"}:
                continue
            if re.fullmatch(r"[qmvs]-?\d+|q\d+", token, flags=re.IGNORECASE):
                continue
            if any(keyword in lowered for keyword in ["led", "비디오월", "전광판", "옵션비교"]):
                continue
            return self._clean_company_suffix(token)
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
            for label in ["사업명", "건명", "프로젝트명", "공사명"]:
                if self._row_contains(row, label):
                    value = self._value_after_label(row, label)
                    if value:
                        return value
            if self._row_contains(row, "건"):
                value = self._value_after_label(row, "건")
                if value:
                    return value

        return ""

    def _extract_project_name_from_file(self, path: Path, vendor_name: str) -> str:
        text = path.stem
        for token in [vendor_name, "견적서"]:
            if token:
                text = re.sub(re.escape(token), " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\b[QMVS]-?\d+\b|Q\d+", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"[_\-]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _extract_total_with_vat(self, rows: list[list[Any]]) -> int | None:
        for row in rows:
            row_text = " ".join(self._clean_text(value) for value in row)
            if any(label in row_text for label in ["합계금액", "총금액", "VAT 포함", "VAT포함", "부가가치세 포함"]):
                amounts = self._amounts_from_row(row)
                if amounts:
                    return max(amounts)
            if self._row_contains(row, "합 계 금 액"):
                amounts = self._amounts_from_row(row)
                if amounts:
                    return max(amounts)

        return None

    def _extract_total_supply_price(self, rows: list[list[Any]]) -> int:
        for row in rows:
            first = self._clean_text(row[0] if row else "")
            if first in {"공급가액", "공급가", "소계", "Subtotal", "VAT 별도", "VAT별도"}:
                amounts = self._amounts_from_row(row)
                if amounts:
                    return max(amounts)
            if first == "계":
                amounts = self._amounts_from_row(row)
                if amounts:
                    return max(amounts)

        return 0

    def _extract_generic_supply_amount(self, rows: list[list[Any]]) -> int:
        for row in rows:
            row_text = " ".join(self._clean_text(value) for value in row)
            if any(label in row_text for label in ["공급가액", "공급가", "소계", "Subtotal", "VAT 별도", "VAT별도"]):
                amounts = self._amounts_from_row(row)
                if amounts:
                    return max(amounts)
        return 0

    def _extract_generic_total_with_vat(self, rows: list[list[Any]]) -> int | None:
        for row in rows:
            row_text = " ".join(self._clean_text(value) for value in row)
            if any(label in row_text for label in ["합계금액", "총금액", "VAT 포함", "VAT포함", "부가가치세 포함"]):
                amounts = self._amounts_from_row(row)
                if amounts:
                    return max(amounts)
        return None

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
            sheet_context = collect_hardware_spec_context(
                " ".join(self._clean_text(cell) for row in rows for cell in row)
            )
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
                    if item.category == LineItemCategory.DISPLAY:
                        merge_hardware_spec_context(
                            item,
                            sheet_context,
                            source="excel_sheet_spec_context",
                        )
                    items.append(item)

        return items

    def _extract_generic_line_items(self, sheets: list[list[list[Any]]]) -> list[LineItem]:
        table_groups: list[tuple[dict[str, int], list[LineItem]]] = []
        for rows in sheets:
            header_index, roles = self._find_generic_header_roles(rows)
            if header_index is None:
                continue
            sheet_context = collect_hardware_spec_context(
                " ".join(self._clean_text(cell) for row in rows for cell in row)
            )
            table_items: list[LineItem] = []
            for row in rows[header_index + 1 :]:
                row_text = " ".join(self._clean_text(value) for value in row)
                if not row_text or self._is_summary_text(row_text):
                    continue
                item = self._generic_row_to_line_item(row, roles)
                if item:
                    if item.category == LineItemCategory.DISPLAY:
                        merge_hardware_spec_context(
                            item,
                            sheet_context,
                            source="excel_sheet_spec_context",
                        )
                    table_items.append(item)
            if table_items:
                table_groups.append((roles, table_items))

        detailed_groups = [
            items
            for roles, items in table_groups
            if "quantity" in roles and "unit_price" in roles
        ]
        selected_groups = detailed_groups or [items for _, items in table_groups]
        return [item for items in selected_groups for item in items]

    def _find_generic_header_roles(
        self,
        rows: list[list[Any]],
    ) -> tuple[int | None, dict[str, int]]:
        aliases = {
            "item_name": ["구분", "품목", "품명", "제품", "모델명", "item", "description", "내역"],
            "spec": ["규격", "사양", "spec", "상세", "비고", "pitch", "밝기"],
            "quantity": ["수량", "qty", "q'ty"],
            "unit": ["단위", "unit"],
            "unit_price": ["단가", "unit price"],
            "amount": ["금액", "합계", "공급가", "vat별도", "vat 별도", "amount"],
            "tax_amount": ["세액", "부가세", "부가가치세", "vat"],
            "total_with_vat": ["vat포함", "vat 포함"],
        }
        best_index: int | None = None
        best_roles: dict[str, int] = {}
        for index, row in enumerate(rows[:20]):
            roles: dict[str, int] = {}
            for column, value in enumerate(row):
                compact = re.sub(r"\s+", "", self._clean_text(value).lower())
                if not compact:
                    continue
                for role, names in aliases.items():
                    if role in roles:
                        continue
                    if any(re.sub(r"\s+", "", name.lower()) in compact for name in names):
                        roles[role] = column
            explicit_item_column = self._find_explicit_item_name_column(row)
            if explicit_item_column is not None:
                roles["item_name"] = explicit_item_column
            if len(roles) > len(best_roles):
                best_index = index
                best_roles = roles
        if best_index is None or "item_name" not in best_roles or "amount" not in best_roles:
            return None, {}
        return best_index, best_roles

    def _find_explicit_item_name_column(self, row: list[Any]) -> int | None:
        explicit_labels = ["품목", "품명", "제품", "모델명", "item", "description", "내역"]
        for column, value in enumerate(row):
            compact = re.sub(r"\s+", "", self._clean_text(value).lower())
            if any(re.sub(r"\s+", "", label.lower()) in compact for label in explicit_labels):
                return column
        return None

    def _generic_row_to_line_item(
        self,
        row: list[Any],
        roles: dict[str, int],
    ) -> LineItem | None:
        name = self._clean_text(self._cell(row, roles.get("item_name")))
        if not name or self._is_summary_text(name):
            return None
        spec_parts = [self._clean_text(self._cell(row, roles.get("spec")))]
        for role in ["tax_amount", "total_with_vat"]:
            value = self._clean_text(self._cell(row, roles.get(role)))
            if value and not self._looks_numeric(value):
                spec_parts.append(value)
        spec_raw = " / ".join(part for part in spec_parts if part)
        quantity = self._float_at(row, roles.get("quantity", 10_000))
        unit = self._clean_text(self._cell(row, roles.get("unit")))
        unit_price = self._int_at(row, roles.get("unit_price", 10_000))
        total_price = self._int_at(row, roles.get("amount", 10_000))
        if total_price is None:
            total_price = self._int_at(row, roles.get("total_with_vat", 10_000))
        if quantity is None and unit_price is None and total_price is None:
            return None
        text = " ".join(value for value in [name, spec_raw] if value)
        category = self._classify_category(text)
        spec_parsed = self._extract_spec_parsed(text, category)
        spec_parsed.update(extract_display_specs(text, name, spec_raw).spec_parsed)
        return LineItem(
            name=name,
            category=category,
            quantity=quantity if quantity is not None else 1.0,
            unit=unit,
            unit_price=unit_price,
            total_price=total_price,
            is_optional=bool(re.search(r"옵션|선택|별도|option", text, re.IGNORECASE)),
            spec_raw=spec_raw,
            spec_parsed=spec_parsed,
            extraction_confidence=0.8,
        )

    def _cell(self, row: list[Any], index: int | None) -> Any:
        if index is None or index >= len(row):
            return ""
        return row[index]

    def _is_summary_text(self, text: str) -> bool:
        compact = re.sub(r"\s+", "", self._clean_text(text).lower())
        return any(
            token in compact
            for token in [
                "합계",
                "합계금액",
                "공급가액",
                "부가가치세",
                "부가세",
                "vat",
                "subtotal",
                "total",
            ]
        )

    def _looks_numeric(self, value: str) -> bool:
        return bool(
            re.fullmatch(
                r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?",
                self._clean_text(value),
            )
        )

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

        if any(keyword in normalized for keyword in ["플레이어", "프로세서", "컨트롤러", "제어 pc", "운영 pc", "미디어 서버", "서버"]):
            return LineItemCategory.PLAYER
        if any(keyword in normalized for keyword in ["전광판", "비디오월", "디스플레이", "모듈", "스크린"]):
            return LineItemCategory.DISPLAY
        if any(keyword in normalized for keyword in ["브라켓", "마운트", "거치", "구조물", "프레임", "앵커"]):
            return LineItemCategory.MOUNT
        if any(keyword in normalized for keyword in ["케이블", "전장", "배관", "배선", "광전송", "신호선"]):
            return LineItemCategory.CABLE
        if any(keyword in normalized for keyword in ["설치", "시공", "시운전", "교육", "인건비", "검수", "캘리브레이션"]):
            return LineItemCategory.INSTALL
        if any(keyword in normalized for keyword in ["소프트웨어", "라이선스", "콘텐츠", "cms"]):
            return LineItemCategory.SOFTWARE

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

    def _clean_company_suffix(self, value: Any) -> str:
        text = self._clean_text(value)
        text = re.sub(r"^\(?주\)?\s*", "", text)
        text = re.sub(r"\s*\(?주\)?$", "", text)
        text = text.replace("주식회사", "").strip()
        return text
