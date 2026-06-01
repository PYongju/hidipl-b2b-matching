from datetime import datetime

from services.parser.schemas import QuoteDocument
from services.quote_ingestion.vendor_snapshot_enricher import VendorSnapshotEnricher


def main() -> None:
    quote = QuoteDocument(
        vendor_name="㈜가이드삼정",
        quote_id="test_quote",
        received_at=datetime.now(),
        project_name="",
        total_supply_price=0,
        total_with_vat=None,
    )
    enricher = VendorSnapshotEnricher()
    enriched, debug = enricher.enrich(quote)

    print("debug:", debug)
    assert enriched.vendor_snapshot is not None
    assert enriched.vendor_snapshot.vendor_name == "가이드삼정"
    assert enriched.vendor_snapshot.is_premium_partner is True
    assert enriched.vendor_snapshot.past_success_rate == 0.10
    assert enriched.vendor_snapshot.response_speed_score in {100.0, 70.0, 40.0, None}
    print("vendor_snapshot:", enriched.vendor_snapshot)


if __name__ == "__main__":
    main()
