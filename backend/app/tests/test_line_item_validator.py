from datetime import datetime

from services.parser.quote_parser_validator import build_line_item_validation
from services.parser.schemas import LineItem, LineItemCategory, QuoteDocument


def main() -> None:
    quote = QuoteDocument(
        vendor_name="TEST",
        quote_id="test",
        received_at=datetime(2025, 1, 1),
        project_name="test",
        total_supply_price=9_900_000,
        total_with_vat=10_890_000,
        line_items=[
            LineItem(
                name="DISPLAY-X",
                category=LineItemCategory.DISPLAY,
                quantity=9,
                unit="EA",
                unit_price=1_000_000,
                total_price=9_900_000,
            )
        ],
    )
    validation = build_line_item_validation(quote)
    assert len(validation) == 1
    assert validation[0]["validation_status"] == "line_item_arithmetic_mismatch"
    assert validation[0]["difference"] == 900_000
    assert validation[0]["auto_corrected"] is False
    assert quote.line_items[0].total_price == 9_900_000
    print("line item validator tests: ok")


if __name__ == "__main__":
    main()
