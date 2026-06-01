from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import ceil
from typing import Any


class LineItemCategory(str, Enum):
    DISPLAY = "DISPLAY"
    MOUNT = "MOUNT"
    PLAYER = "PLAYER"
    CABLE = "CABLE"
    INSTALL = "INSTALL"
    SOFTWARE = "SOFTWARE"
    ETC = "ETC"


# Deprecated compatibility schema.
# New code should use LineItem.
@dataclass
class QuoteItem:
    item_name: str | None = None
    spec: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: int | None = None
    supply_amount: int | None = None
    tax_amount: int | None = None
    amount: int | None = None
    note: str | None = None


@dataclass
class LineItem:
    name: str
    category: LineItemCategory
    quantity: float
    unit: str
    unit_price: int | None
    total_price: int | None
    is_optional: bool = False
    spec_raw: str = ""
    spec_parsed: dict = field(default_factory=dict)
    extraction_confidence: float = 0.0

    @property
    def item_name(self) -> str:
        return self.name

    @property
    def spec(self) -> str:
        return self.spec_raw

    @property
    def amount(self) -> int | None:
        return self.total_price

    @property
    def note(self) -> str:
        return self.spec_raw


@dataclass
class VendorSnapshot:
    vendor_id: str | None = None
    vendor_name: str | None = None
    is_premium_partner: bool = False
    past_success_rate: float | None = None
    response_speed_score: float | None = None
    response_speed: str | None = None
    financial_status: str | None = None
    is_excluded: bool = False
    specialty_tags: list[str] = field(default_factory=list)
    installation_count: int | None = None
    industry_breakdown: dict[str, int] = field(default_factory=dict)
    solution_breakdown: dict[str, int] = field(default_factory=dict)
    scale_breakdown: dict[str, int] = field(default_factory=dict)
    avg_projects_3yr: float | None = None
    avg_revenue_3yr: str | None = None
    avg_revenue_3yr_million: float | None = None
    years_in_business: int | None = None
    representative: str | None = None
    company_age_years: int | None = None
    avg_project_count_3y: float | None = None
    avg_revenue_3y_million: float | None = None
    company_location: str | None = None
    source: str = "data/partners.py"


@dataclass
class QuoteDocument:
    vendor_name: str
    quote_id: str
    received_at: datetime
    project_name: str
    total_supply_price: int
    total_with_vat: int | None
    currency: str = "KRW"
    delivery_weeks: int | None = None
    delivery_basis_raw: str = ""
    warranty_months: int | None = None
    notes_raw: str = ""
    source_file_path: str = ""
    source_file_hash: str = ""
    extraction_confidence: float = 0.0
    line_items: list[LineItem] = field(default_factory=list)
    vendor_snapshot: VendorSnapshot | None = None

    @property
    def total_amount(self) -> int | None:
        return self.total_with_vat if self.total_with_vat is not None else self.total_supply_price

    @property
    def supply_amount(self) -> int:
        return self.total_supply_price

    @property
    def tax_amount(self) -> int | None:
        if self.total_with_vat is None:
            return None
        return self.total_with_vat - self.total_supply_price

    @property
    def delivery_days(self) -> int | None:
        if self.delivery_weeks is None:
            return None
        return self.delivery_weeks * 7

    @property
    def quote_date(self) -> str | None:
        return self.received_at.date().isoformat()

    @property
    def quote_validity_days(self) -> int | None:
        return None

    @property
    def maintenance_included(self) -> bool | None:
        return None

    @property
    def installation_fee_included(self) -> bool | None:
        return None

    @property
    def delivery_fee_included(self) -> bool | None:
        return None

    @property
    def payment_terms(self) -> str | None:
        return None

    @property
    def items(self) -> list[LineItem]:
        return self.line_items

    @property
    def special_terms(self) -> list[str]:
        return [self.notes_raw] if self.notes_raw else []


# Deprecated compatibility schema.
# New code should use QuoteDocument.
@dataclass
class QuoteInfo:
    vendor_name: str | None = None
    quote_date: str | None = None

    total_amount: int | None = None
    supply_amount: int | None = None
    tax_amount: int | None = None
    currency: str = "KRW"

    delivery_days: int | None = None
    quote_validity_days: int | None = None
    warranty_months: int | None = None

    maintenance_included: bool | None = None
    installation_fee_included: bool | None = None
    delivery_fee_included: bool | None = None

    payment_terms: str | None = None
    special_terms: list[str] = field(default_factory=list)

    items: list[QuoteItem] = field(default_factory=list)


@dataclass(init=False)
class ParsedQuoteResult:
    quote_document: QuoteDocument
    source_text: str
    warnings: list[str] = field(default_factory=list)
    raw_matches: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        quote_document: QuoteDocument | None = None,
        source_text: str = "",
        warnings: list[str] | None = None,
        raw_matches: dict[str, Any] | None = None,
        quote: QuoteDocument | QuoteInfo | None = None,
    ) -> None:
        document = quote_document or quote

        if isinstance(document, QuoteInfo):
            document = quote_info_to_quote_document(document)

        if document is None:
            raise ValueError("quote_document is required.")

        self.quote_document = document
        self.source_text = source_text
        self.warnings = warnings or []
        self.raw_matches = raw_matches or {}

    @property
    def quote(self) -> QuoteDocument:
        return self.quote_document


def quote_info_to_quote_document(quote: QuoteInfo) -> QuoteDocument:
    delivery_weeks = None
    if quote.delivery_days is not None:
        delivery_weeks = ceil(quote.delivery_days / 7)

    return QuoteDocument(
        vendor_name=quote.vendor_name or "",
        quote_id="",
        received_at=datetime.now(),
        project_name="",
        total_supply_price=quote.supply_amount or quote.total_amount or 0,
        total_with_vat=quote.total_amount,
        currency=quote.currency,
        delivery_weeks=delivery_weeks,
        delivery_basis_raw=str(quote.delivery_days or ""),
        warranty_months=quote.warranty_months,
        notes_raw="\n".join(quote.special_terms),
        line_items=[quote_item_to_line_item(item) for item in quote.items],
    )


def quote_item_to_line_item(item: QuoteItem) -> LineItem:
    raw_text = " ".join(
        value
        for value in [item.item_name, item.spec, item.note]
        if value
    )

    return LineItem(
        name=item.item_name or "",
        category=infer_line_item_category(raw_text),
        quantity=item.quantity if item.quantity is not None else 0.0,
        unit=item.unit or "",
        unit_price=item.unit_price,
        total_price=item.amount or item.supply_amount,
        spec_raw=" ".join(value for value in [item.spec, item.note] if value),
        spec_parsed={},
        extraction_confidence=0.0,
    )


def infer_line_item_category(text: str) -> LineItemCategory:
    normalized = text.lower()

    if any(keyword in normalized for keyword in ["led", "전광판", "비디오월", "display"]):
        return LineItemCategory.DISPLAY
    if any(keyword in normalized for keyword in ["브라켓", "마운트", "mount", "거치"]):
        return LineItemCategory.MOUNT
    if any(keyword in normalized for keyword in ["player", "플레이어", "컨트롤러", "processor"]):
        return LineItemCategory.PLAYER
    if any(keyword in normalized for keyword in ["cable", "케이블", "hdmi", "전원선"]):
        return LineItemCategory.CABLE
    if any(keyword in normalized for keyword in ["설치", "시공", "install"]):
        return LineItemCategory.INSTALL
    if any(keyword in normalized for keyword in ["software", "소프트웨어", "라이선스"]):
        return LineItemCategory.SOFTWARE

    return LineItemCategory.ETC
