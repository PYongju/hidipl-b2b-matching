import re
from typing import Any

from services.requirement.base import RequirementParserProvider
from services.requirement.schemas import (
    ParsedRequirementResult,
    RequirementInfo,
    RequirementProduct,
)


DEFAULT_PRIORITY = {
    "price": 0.25,
    "spec_match": 0.30,
    "schedule": 0.15,
    "region": 0.10,
    "condition": 0.10,
    "semantic": 0.10,
}


class RuleBasedRequirementParser(RequirementParserProvider):
    def parse(self, text: str) -> ParsedRequirementResult:
        normalized_text = self._normalize_text(text)
        raw_matches: dict[str, Any] = {}
        warnings: list[str] = []

        commission_model, commission_rate = self._extract_commission(
            normalized_text, raw_matches
        )
        customer_name = self._extract_customer_name(normalized_text, raw_matches)
        request_summary = self._extract_request_summary(normalized_text, raw_matches)
        products = self._extract_products(normalized_text, raw_matches)
        region = self._extract_labeled_value(
            normalized_text,
            ["지역"],
            raw_matches,
            "region",
        )
        install_schedule_text = self._extract_labeled_value(
            normalized_text,
            ["설치 일정", "설치일정", "일정"],
            raw_matches,
            "install_schedule_text",
        )
        review_deadline_text = self._extract_review_deadline(normalized_text)
        project_stage = self._extract_labeled_value(
            normalized_text,
            ["단계"],
            raw_matches,
            "project_stage",
        )
        budget_min, budget_max = self._extract_budget(normalized_text, raw_matches)
        notes = self._extract_notes(normalized_text)

        if project_stage is None:
            project_stage = self._extract_project_stage_from_text(normalized_text)

        required_keywords = self._extract_required_keywords(
            normalized_text,
            products,
        )
        excluded_keywords = self._extract_excluded_keywords(normalized_text)

        if customer_name is None:
            warnings.append("고객사를 추출하지 못했습니다.")

        if not products:
            warnings.append("견적 요청 제품을 추출하지 못했습니다.")

        if region is None:
            warnings.append("지역 정보를 추출하지 못했습니다.")

        requirement = RequirementInfo(
            raw_text=text,
            customer_name=customer_name,
            commission_model=commission_model,
            commission_rate_percent=commission_rate,
            request_summary=request_summary,
            products=products,
            region=region,
            install_schedule_text=install_schedule_text,
            review_deadline_text=review_deadline_text,
            project_stage=project_stage,
            budget_min=budget_min,
            budget_max=budget_max,
            notes=notes,
            required_keywords=required_keywords,
            preferred_keywords=[],
            excluded_keywords=excluded_keywords,
            priority=DEFAULT_PRIORITY.copy(),
        )

        return ParsedRequirementResult(
            requirement=requirement,
            warnings=warnings,
            raw_matches=raw_matches,
        )

    def _normalize_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _extract_commission(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> tuple[str | None, float | None]:
        pattern = re.compile(
            r"수수료[ \t]*모델[ \t]*[:：]?[ \t]*(?P<model>[A-Za-z가-힣]?[ \t]*\(?[ \t]*\d+(?:\.\d+)?[ \t]*%[ \t]*\)?|\d+(?:\.\d+)?[ \t]*%)",
            re.IGNORECASE,
        )
        match = pattern.search(text)

        if not match:
            return None, None

        model = re.sub(r"\s+", "", match.group("model"))
        rate_match = re.search(r"\d+(?:\.\d+)?", model)
        rate = float(rate_match.group()) if rate_match else None
        raw_matches["commission"] = match.group(0)
        return model, rate

    def _extract_customer_name(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> str | None:
        value = self._extract_labeled_value(
            text,
            ["고객사", "기업명"],
            raw_matches,
            "customer_name",
        )
        return value

    def _extract_request_summary(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> str | None:
        summary = self._extract_labeled_block(
            text,
            ["견적 요청 내용", "문의 내용"],
            raw_matches,
            "request_summary",
        )

        if summary is None:
            return None

        lines = []
        for line in summary.splitlines():
            stripped = line.strip()
            if re.match(r"^\(\d+\)", stripped):
                break
            if self._is_labeled_section_line(stripped):
                break
            if stripped:
                lines.append(stripped)

        return " ".join(lines).strip() or None

    def _extract_labeled_value(
        self,
        text: str,
        labels: list[str],
        raw_matches: dict[str, Any],
        raw_key: str,
    ) -> str | None:
        label_pattern = "|".join(re.escape(label) for label in labels)
        pattern = re.compile(
            rf"(?:^\s*(?:\d+\.\s*)?)({label_pattern})\s*[:：]\s*(?P<value>.+)$",
            re.MULTILINE,
        )
        match = pattern.search(text)

        if not match:
            return None

        value = self._clean_value(match.group("value"))
        raw_matches[raw_key] = match.group(0).strip()
        return value

    def _extract_labeled_block(
        self,
        text: str,
        labels: list[str],
        raw_matches: dict[str, Any],
        raw_key: str,
    ) -> str | None:
        label_pattern = "|".join(re.escape(label) for label in labels)
        pattern = re.compile(
            rf"^\s*(?:\d+\.\s*)?(?:{label_pattern})\s*[:：]\s*(?P<value>.*)$",
            re.MULTILINE,
        )
        match = pattern.search(text)

        if not match:
            return None

        lines = [match.group("value").strip()]
        start = match.end()
        for line in text[start:].splitlines():
            stripped = line.strip()
            if re.match(r"^\d+\.\s+", stripped):
                break
            lines.append(stripped)

        block = "\n".join(line for line in lines if line).strip()
        raw_matches[raw_key] = block
        return block or None

    def _extract_budget(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> tuple[int | None, int | None]:
        budget_min = None
        budget_max = None

        range_pattern = re.compile(
            r"(?P<min>\d[\d,]*(?:\.\d+)?\s*(?:천\s*만\s*원|천만원|만\s*원|만원|억\s*원|억원|억|원)?)\s*이상\s*(?:~|-|부터)?\s*(?P<max>\d[\d,]*(?:\.\d+)?\s*(?:천\s*만\s*원|천만원|만\s*원|만원|억\s*원|억원|억|원)?)\s*(?:미만|이하|까지)?"
        )
        match = range_pattern.search(text)
        if match:
            budget_min = self._parse_korean_money(match.group("min"))
            budget_max = self._parse_korean_money(match.group("max"))
            raw_matches["budget"] = match.group(0)
            return budget_min, budget_max

        max_pattern = re.compile(
            r"(?:예산\s*)?(?:최대\s*)?(?P<amount>\d[\d,]*(?:\.\d+)?\s*(?:천\s*만\s*원|천만원|만\s*원|만원|억\s*원|억원|억|원))\s*(?:이하|미만|까지)"
        )
        match = max_pattern.search(text)
        if match:
            budget_max = self._parse_korean_money(match.group("amount"))
            raw_matches["budget"] = match.group(0)
            return None, budget_max

        max_prefix_pattern = re.compile(
            r"최대\s*(?P<amount>\d[\d,]*(?:\.\d+)?\s*(?:천\s*만\s*원|천만원|만\s*원|만원|억\s*원|억원|억|원))"
        )
        match = max_prefix_pattern.search(text)
        if match:
            budget_max = self._parse_korean_money(match.group("amount"))
            raw_matches["budget"] = match.group(0)
            return None, budget_max

        min_pattern = re.compile(
            r"(?P<amount>\d[\d,]*(?:\.\d+)?\s*(?:천\s*만\s*원|천만원|만\s*원|만원|억\s*원|억원|억|원))\s*이상"
        )
        match = min_pattern.search(text)
        if match:
            budget_min = self._parse_korean_money(match.group("amount"))
            raw_matches["budget"] = match.group(0)

        return budget_min, budget_max

    def _parse_korean_money(self, value: str | None) -> int | None:
        if value is None:
            return None

        compact = re.sub(r"\s+", "", value).replace(",", "")
        number_match = re.search(r"\d+(?:\.\d+)?", compact)
        if not number_match:
            return None

        number = float(number_match.group())

        if "천만원" in compact:
            return int(number * 10_000_000)
        if "만원" in compact:
            return int(number * 10_000)
        if "억" in compact:
            return int(number * 100_000_000)
        if "원" in compact:
            return int(number)

        return int(number)

    def _extract_products(
        self,
        text: str,
        raw_matches: dict[str, Any],
    ) -> list[RequirementProduct]:
        product_blocks = self._extract_numbered_product_blocks(text)
        products = [self._parse_product_block(block) for block in product_blocks]
        products = [product for product in products if product is not None]

        if not products:
            fallback = self._parse_solution_product(text)
            if fallback:
                products.append(fallback)

        raw_matches["products"] = [product.raw_text for product in products]
        return products

    def _extract_numbered_product_blocks(self, text: str) -> list[str]:
        lines = text.splitlines()
        blocks: list[list[str]] = []
        current: list[str] | None = None

        for line in lines:
            stripped = line.strip()

            if re.match(r"^\(\d+\)", stripped):
                if current:
                    blocks.append(current)
                current = [stripped]
                continue

            if current is not None:
                if re.match(r"^\d+\.\s+", stripped):
                    blocks.append(current)
                    current = None
                    continue
                if stripped:
                    current.append(stripped)

        if current:
            blocks.append(current)

        return ["\n".join(block) for block in blocks]

    def _parse_product_block(self, block: str) -> RequirementProduct | None:
        first_line = block.splitlines()[0].strip()
        name = re.sub(r"^\(\d+\)\s*", "", first_line).strip()

        if not self._looks_like_product(block):
            return None

        product = RequirementProduct(raw_text=block, name=name)
        self._apply_product_type(product, block)
        self._apply_display_type(product, block)
        self._apply_diagonal(product, block)
        self._apply_layout(product, block)
        self._apply_size(product, block)
        self._apply_pitch(product, block)

        if product.pitch_mm is not None:
            product.name = self._trim_name_after_pitch_size(product.name)
        product.name = self._trim_name_after_layout(product.name)

        return product

    def _parse_solution_product(self, text: str) -> RequirementProduct | None:
        solution = self._extract_labeled_value(text, ["솔루션"], {}, "solution")
        if not solution:
            return None

        product = RequirementProduct(raw_text=solution, name=solution)
        self._apply_product_type(product, solution)
        self._apply_display_type(product, solution)
        return product

    def _looks_like_product(self, text: str) -> bool:
        return bool(
            re.search(
                r"LED|전광판|비디오월|스크린|디스플레이|Pitch|피치|P\d",
                text,
                re.IGNORECASE,
            )
        )

    def _apply_product_type(self, product: RequirementProduct, text: str) -> None:
        if re.search(r"비디오\s*월|비디오월", text, re.IGNORECASE):
            product.product_type = "비디오월"
        elif re.search(r"LED|전광판|스크린", text, re.IGNORECASE):
            product.product_type = "LED 전광판"

    def _apply_display_type(self, product: RequirementProduct, text: str) -> None:
        for display_type in ["커브드", "평면", "플랫", "실내용"]:
            if display_type in text:
                product.display_type = display_type
                return

    def _apply_diagonal(self, product: RequirementProduct, text: str) -> None:
        match = re.search(r"(?P<inch>\d+(?:\.\d+)?)\s*(?:\"|인치)", text)
        if match:
            product.diagonal_inch = float(match.group("inch"))

    def _apply_layout(self, product: RequirementProduct, text: str) -> None:
        match = re.search(
            r"(?<![\d,])(?P<rows>\d{1,2})\s*[xX×]\s*(?P<cols>\d{1,2})(?![\d,])",
            text,
        )
        if match:
            product.layout_rows = int(match.group("rows"))
            product.layout_cols = int(match.group("cols"))

    def _apply_size(self, product: RequirementProduct, text: str) -> None:
        match = re.search(
            r"(?P<width>\d{1,3}(?:,\d{3})+|\d{4,5})\s*[xX×]\s*(?P<height>\d{1,3}(?:,\d{3})+|\d{4,5})(?:\s*mm)?",
            text,
            re.IGNORECASE,
        )
        if match:
            product.width_mm = int(match.group("width").replace(",", ""))
            product.height_mm = int(match.group("height").replace(",", ""))

    def _apply_pitch(self, product: RequirementProduct, text: str) -> None:
        pitch_max_match = re.search(
            r"(?:Pitch|피치)\s*[:：]?\s*(?P<pitch>\d+(?:\.\d+)?)\s*이하",
            text,
            re.IGNORECASE,
        )
        if pitch_max_match:
            product.pitch_max_mm = float(pitch_max_match.group("pitch"))

        pitch_match = re.search(r"\bP\s*(?P<pitch>\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if pitch_match:
            product.pitch_mm = float(pitch_match.group("pitch"))

    def _trim_name_after_pitch_size(self, name: str | None) -> str | None:
        if name is None:
            return None

        size_match = re.search(
            r"\s+\d{1,3}(?:,\d{3})+\s*[xX×]\s*\d{1,3}(?:,\d{3})+",
            name,
            re.IGNORECASE,
        )
        if size_match:
            return name[: size_match.start()].strip()

        return name

    def _trim_name_after_layout(self, name: str | None) -> str | None:
        if name is None:
            return None

        return re.sub(
            r"\s+\d{1,2}\s*[xX×]\s*\d{1,2}\s*$",
            "",
            name,
            flags=re.IGNORECASE,
        ).strip()

    def _extract_review_deadline(self, text: str) -> str | None:
        patterns = [
            r"월요일\s*오전까지",
            r"내일까지",
            r"금요일까지",
            r"이번\s*주까지",
            r"빠르게\s*검토",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None

    def _extract_notes(self, text: str) -> list[str]:
        notes: list[str] = []
        in_notes_section = False

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if re.match(r"^\d+\.\s*기타\s*사항", stripped):
                in_notes_section = True
                continue

            if in_notes_section and re.match(r"^\d+\.\s+", stripped):
                in_notes_section = False

            if in_notes_section and stripped.startswith("-"):
                notes.append(self._clean_value(stripped.lstrip("-")))
                continue

            if stripped.startswith("현재 "):
                notes.append(self._clean_value(stripped.lstrip("-")))

        return self._deduplicate(notes)

    def _extract_project_stage_from_text(self, text: str) -> str | None:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("현재 "):
                return self._clean_value(stripped)
        return None

    def _extract_required_keywords(
        self,
        text: str,
        products: list[RequirementProduct],
    ) -> list[str]:
        keyword_candidates = [
            "LED 전광판",
            "비디오월",
            "회의실",
            "컨퍼런스 룸",
            "디스플레이",
            "커브드",
            "평면",
            "플랫",
            "설치",
            "태양광 발전 현황",
            "프로세서",
            "잡자재",
        ]
        keywords: list[str] = []

        for product in products:
            if product.product_type:
                keywords.append(product.product_type)
            if product.display_type:
                keywords.append(product.display_type)

        for keyword in keyword_candidates:
            if keyword in text:
                keywords.append(keyword)

        return self._deduplicate(keywords)

    def _extract_excluded_keywords(self, text: str) -> list[str]:
        return [
            keyword
            for keyword in ["별도 제외", "불가", "제외"]
            if keyword in text
        ]

    def _is_labeled_section_line(self, line: str) -> bool:
        return bool(
            re.match(
                r"^(?:\d+\.\s*)?(수수료\s*모델|고객사|기업명|견적 요청 내용|문의 내용|일정|설치 일정|설치일정|지역|단계|기타 사항|예산|솔루션)\s*[:：]?",
                line,
            )
        )

    def _clean_value(self, value: str | None) -> str | None:
        if value is None:
            return None

        value = re.sub(r"\s+", " ", value).strip()
        return value or None

    def _deduplicate(self, values: list[str]) -> list[str]:
        seen = set()
        deduplicated = []

        for value in values:
            cleaned = self._clean_value(value)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduplicated.append(cleaned)

        return deduplicated
