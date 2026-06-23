from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from services.ocr.schemas import OCRResult
from services.parser.base import ParserProvider
from services.parser.llm_prompt_builder import (
    build_quote_parser_system_prompt,
    build_quote_parser_user_prompt,
)
from services.parser.quote_parser_validator import (
    SUMMARY_ROW_KEYWORDS,
    apply_delivery_normalization,
    build_amount_validation,
    build_quote_document_check_required,
    detect_multi_option,
    normalize_line_item_category,
    validate_quote_document,
)
from services.parser.schemas import (
    LineItem,
    LineItemCategory,
    ParsedQuoteResult,
    QuoteDocument,
    infer_line_item_category,
)
from services.parser.vendor_name_resolver import VendorNameResolver


class LLMQuoteParserProvider(ParserProvider):
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
        *,
        settings=None,
        client=None,
        fallback_provider: ParserProvider | None = None,
        max_tokens: int = 4000,
    ) -> None:
        load_dotenv()

        self.endpoint = endpoint or getattr(settings, "azure_openai_endpoint", None) or os.getenv(
            "AZURE_OPENAI_ENDPOINT"
        )
        self.api_key = api_key or getattr(settings, "azure_openai_api_key", None) or os.getenv(
            "AZURE_OPENAI_API_KEY"
        )
        self.deployment = (
            deployment
            or getattr(settings, "azure_openai_chat_deployment", None)
            or os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
        )
        self.api_version = (
            api_version
            or getattr(settings, "azure_openai_chat_api_version", None)
            or os.getenv("AZURE_OPENAI_CHAT_API_VERSION")
            or os.getenv("AZURE_OPENAI_API_VERSION")
            or "2025-01-01-preview"
        )
        self.fallback_provider = fallback_provider
        self.max_tokens = max_tokens

        if client is not None:
            self.client = client
            return

        missing = [
            name
            for name, value in [
                ("AZURE_OPENAI_ENDPOINT", self.endpoint),
                ("AZURE_OPENAI_API_KEY", self.api_key),
                ("AZURE_OPENAI_CHAT_DEPLOYMENT", self.deployment),
            ]
            if not value
        ]
        if missing:
            raise ValueError("Azure OpenAI Chat settings are missing: " + ", ".join(missing))

        try:
            from openai import AzureOpenAI
        except ImportError as e:
            raise RuntimeError("openai package is required for LLMQuoteParserProvider.") from e

        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
        )

    def parse(self, ocr_result: OCRResult | str) -> ParsedQuoteResult:
        source_text = self._source_text(ocr_result)
        raw_matches: dict[str, Any] = {
            "parser_provider": self.__class__.__name__,
            "deployment": self.deployment,
            "api_version": self.api_version,
        }

        try:
            parsed = self._parse_with_retry(source_text, raw_matches)
            quote_document = self._dict_to_quote_document(parsed)
            self._resolve_vendor_name(quote_document, source_text, raw_matches)
            quoted_tax_amount = self._to_int(parsed.get("tax_amount"))
            if quoted_tax_amount is not None:
                raw_matches["quoted_tax_amount"] = quoted_tax_amount

            category_normalization = []
            for item in quote_document.line_items:
                change = normalize_line_item_category(item)
                if change:
                    category_normalization.append(change)
            if category_normalization:
                raw_matches["category_normalization"] = category_normalization

            delivery_validation = apply_delivery_normalization(quote_document)
            amount_validation = build_amount_validation(
                quote_document,
                quoted_tax_amount=quoted_tax_amount,
            )
            multi_option_detection = detect_multi_option(
                quote_document,
                source_text=source_text,
            )
            raw_matches["amount_validation"] = amount_validation
            raw_matches["delivery_validation"] = delivery_validation
            raw_matches["multi_option_detection"] = multi_option_detection

            check_required = build_quote_document_check_required(
                quote_document,
                source_text=source_text,
                amount_validation=amount_validation,
                delivery_validation=delivery_validation,
                multi_option_detection=multi_option_detection,
            )
            raw_matches["parser_check_required"] = check_required
            warnings = self._collect_warnings(parsed, quote_document)
            return ParsedQuoteResult(
                quote_document=quote_document,
                source_text=source_text,
                warnings=warnings,
                raw_matches=raw_matches,
            )
        except Exception as e:
            if self.fallback_provider is None:
                raise RuntimeError(f"LLM quote parser failed: {e}") from e

            fallback_result = self.fallback_provider.parse(
                ocr_result if isinstance(ocr_result, OCRResult) else OCRResult(text=source_text)
            )
            fallback_result.warnings.append(
                f"LLM parser failed; rule parser fallback used: {e}"
            )
            fallback_result.raw_matches["llm_parser_error"] = str(e)
            fallback_result.raw_matches["llm_parser_fallback"] = (
                self.fallback_provider.__class__.__name__
            )
            return fallback_result

    def _parse_with_retry(self, source_text: str, raw_matches: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        for attempt in range(1, 3):
            content = self._request_llm_json(source_text, errors)
            raw_matches[f"llm_raw_response_attempt_{attempt}"] = content[:1000]
            try:
                return self._load_json(content)
            except Exception as e:
                errors.append(str(e))
                raw_matches[f"llm_json_error_attempt_{attempt}"] = str(e)

        raise ValueError("LLM response was not valid JSON after retry.")

    def _request_llm_json(self, source_text: str, previous_errors: list[str]) -> str:
        user_prompt = build_quote_parser_user_prompt(source_text)
        if previous_errors:
            user_prompt += (
                "\n\nPrevious response was invalid JSON. Return corrected JSON only. "
                f"Parser errors: {'; '.join(previous_errors)}"
            )

        response = self.client.chat.completions.create(
            model=self.deployment,
            temperature=0.0,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": build_quote_parser_system_prompt()},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""

    def _load_json(self, content: str) -> dict[str, Any]:
        text = content.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise
            parsed = json.loads(match.group(0))

        if not isinstance(parsed, dict):
            raise ValueError("LLM JSON root must be an object.")

        return parsed

    def _dict_to_quote_document(self, data: dict[str, Any]) -> QuoteDocument:
        line_items = [
            self._dict_to_line_item(item)
            for item in self._as_list(data.get("line_items"))
        ]
        line_items = [
            item
            for item in line_items
            if not self._is_summary_line_item(item)
        ]

        total_with_vat = self._to_int(data.get("total_with_vat"))
        total_supply_price = self._to_int(data.get("total_supply_price"))
        tax_amount = self._to_int(data.get("tax_amount"))

        if total_supply_price is None and total_with_vat is not None and tax_amount is not None:
            total_supply_price = total_with_vat - tax_amount
        if total_supply_price is None:
            total_supply_price = sum(
                item.total_price or 0
                for item in line_items
                if item.total_price is not None
            )

        received_at = self._parse_datetime(data.get("received_at") or data.get("quote_date"))
        quote_id = self._clean_text(data.get("quote_id")) or ""
        vendor_name = self._clean_vendor_name(data.get("vendor_name"))
        project_name = self._clean_project_name(data.get("project_name"))

        return QuoteDocument(
            vendor_name=vendor_name,
            quote_id=quote_id,
            received_at=received_at,
            project_name=project_name,
            total_supply_price=total_supply_price or 0,
            total_with_vat=total_with_vat,
            currency=self._clean_text(data.get("currency")) or "KRW",
            delivery_weeks=self._to_int(data.get("delivery_weeks")),
            delivery_basis_raw=self._clean_text(data.get("delivery_basis_raw")) or "",
            warranty_months=self._to_int(data.get("warranty_months")),
            notes_raw=self._clean_text(data.get("notes_raw")) or "",
            source_file_path="",
            source_file_hash="",
            extraction_confidence=self._to_float(data.get("extraction_confidence"), 0.75),
            line_items=line_items,
            vendor_snapshot=None,
        )

    def _dict_to_line_item(self, data: Any) -> LineItem:
        if not isinstance(data, dict):
            data = {"name": str(data)}

        name = self._clean_text(data.get("name") or data.get("item_name")) or ""
        spec_raw = self._clean_text(data.get("spec_raw") or data.get("spec")) or ""
        category = self._to_category(data.get("category"), " ".join([name, spec_raw]))
        quantity = self._to_float(data.get("quantity"), 0.0)
        unit_price = self._to_int(data.get("unit_price"))
        total_price = self._to_int(
            data.get("total_price")
            if data.get("total_price") is not None
            else data.get("amount")
        )

        spec_parsed = data.get("spec_parsed") if isinstance(data.get("spec_parsed"), dict) else {}
        spec_parsed = {
            **self._extract_spec_parsed(" ".join([name, spec_raw])),
            **spec_parsed,
        }

        return LineItem(
            name=name,
            category=category,
            quantity=quantity,
            unit=self._clean_text(data.get("unit")) or "",
            unit_price=unit_price,
            total_price=total_price,
            is_optional=bool(data.get("is_optional") or False),
            spec_raw=spec_raw,
            spec_parsed=spec_parsed,
            extraction_confidence=self._to_float(data.get("extraction_confidence"), 0.75),
        )

    def _collect_warnings(
        self,
        parsed: dict[str, Any],
        quote_document: QuoteDocument,
    ) -> list[str]:
        warnings = [
            str(item)
            for item in self._as_list(parsed.get("warnings"))
            if str(item).strip()
        ]
        warnings.extend(validate_quote_document(quote_document))
        return self._deduplicate(warnings)

    def _source_text(self, ocr_result: OCRResult | str) -> str:
        if isinstance(ocr_result, str):
            return ocr_result
        return ocr_result.text or ""

    def _resolve_vendor_name(
        self,
        quote_document: QuoteDocument,
        source_text: str,
        raw_matches: dict[str, Any],
    ) -> None:
        resolved_vendor_name, vendor_debug = VendorNameResolver().resolve(
            current_vendor_name=quote_document.vendor_name,
            source_text=source_text,
        )
        if resolved_vendor_name:
            quote_document.vendor_name = resolved_vendor_name
        raw_matches["vendor_name_debug"] = vendor_debug

    def _to_category(self, value: Any, fallback_text: str) -> LineItemCategory:
        if value is not None:
            try:
                return LineItemCategory(str(value).strip().upper())
            except ValueError:
                pass
        return infer_line_item_category(fallback_text)

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if value:
            text = str(value).strip()
            for fmt in ["%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    return datetime.strptime(text[: len(fmt)], fmt)
                except ValueError:
                    continue
        return datetime.now()

    def _extract_spec_parsed(self, text: str) -> dict[str, Any]:
        spec: dict[str, Any] = {}
        normalized = text.strip()
        lower = normalized.lower()

        size_match = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*(?:inch|인치|형)", lower)
        if size_match:
            spec["size_inch"] = float(size_match.group("value"))

        resolution_type_match = re.search(r"\b(?P<value>fhd|uhd|4k|8k|hd)\b", lower)
        if resolution_type_match:
            spec["resolution_type"] = resolution_type_match.group("value").upper()

        brightness_match = re.search(
            r"(?P<value>\d+(?:\.\d+)?)\s*(?:cd(?:/m2|/㎡|/m²)?|nit|nits)",
            lower,
        )
        if brightness_match:
            spec["brightness_cd_m2"] = int(float(brightness_match.group("value")))

        bezel_match = re.search(
            r"(?P<value>\d+(?:\.\d+)?)\s*mm\s*(?:bezel|베젤)",
            lower,
        ) or re.search(
            r"(?:bezel|베젤)[^\d]*(?P<value>\d+(?:\.\d+)?)\s*mm",
            lower,
        )
        if bezel_match:
            spec["bezel_mm"] = float(bezel_match.group("value"))

        screen_size_match = re.search(
            r"(?P<width>\d{2,5}(?:\.\d+)?)\s*(?:x|×|횞)\s*(?P<height>\d{2,5}(?:\.\d+)?)\s*mm",
            lower,
        )
        if screen_size_match:
            spec["screen_size_mm"] = (
                f"{screen_size_match.group('width')}x{screen_size_match.group('height')}"
            )

        weight_match = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*kg", lower)
        if weight_match:
            spec["weight_kg"] = float(weight_match.group("value"))

        power_kw_match = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*kw", lower)
        if power_kw_match:
            spec["power_consumption_kw"] = float(power_kw_match.group("value"))

        power_w_match = re.search(r"(?P<value>\d+(?:\.\d+)?)\s*w\b", lower)
        if power_w_match and "power_consumption_kw" not in spec:
            spec["power_consumption_w"] = int(float(power_w_match.group("value")))

        return spec

    def _to_int(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value).strip()
        if not text:
            return None
        number = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text)
        if not number:
            return None
        return int(float(number.group(0).replace(",", "")))

    def _to_float(self, value: Any, default: float) -> float:
        if value is None or value == "":
            return default
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            return default

    def _clean_vendor_name(self, value: Any) -> str:
        text = self._clean_text(value) or ""
        text = re.sub(r"\b(quotation|quote|estimate|no\.?)\b", "", text, flags=re.IGNORECASE)
        text = text.replace("견적서", "").replace("견적", "")
        return re.sub(r"\s+", " ", text).strip(" :-_|")

    def _clean_project_name(self, value: Any) -> str:
        text = self._clean_text(value) or ""
        text = re.sub(r"\b(quotation|quote|estimate|no\.?)\b", "", text, flags=re.IGNORECASE)
        return text.strip(" :-_|")

    def _clean_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).replace("\x00", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    def _as_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def _is_summary_line_item(self, item: LineItem) -> bool:
        text = " ".join([item.name, item.spec_raw]).lower()
        return any(keyword in text for keyword in SUMMARY_ROW_KEYWORDS)

    def _deduplicate(self, values: list[str]) -> list[str]:
        result = []
        seen = set()
        for value in values:
            cleaned = value.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
        return result
