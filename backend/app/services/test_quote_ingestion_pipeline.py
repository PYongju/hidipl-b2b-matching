from pprint import pprint

from config.paths import DATA_DIR
from services.quote_ingestion.factory import create_quote_ingestion_pipeline


def main() -> None:
    run_pdf_quote_ingestion_test()
    run_excel_quote_ingestion_test()


def run_pdf_quote_ingestion_test() -> None:
    file_paths = sorted(DATA_DIR.glob("*.pdf"))

    if not file_paths:
        print("테스트할 견적서 PDF가 없습니다.")
        return

    pipeline = create_quote_ingestion_pipeline()

    batch_result = pipeline.process_files(
        file_paths,
        request_id="test_request_001",
    )

    for index, result in enumerate(batch_result.results, start=1):
        print(f"\n========== Quote Ingestion Result {index} ==========")
        print(f"quote_id: {result.quote_id}")
        print(f"vendor_name: {result.quote.vendor_name}")
        print(f"total_supply_price: {result.quote.total_supply_price}")
        print(f"total_with_vat: {result.quote.total_with_vat}")
        print(f"line_item_count: {len(result.quote.line_items)}")
        print(f"embedding_dim: {result.embedding_dim}")
        print(f"source_file_hash: {result.quote.source_file_hash}")
        print("parser_warnings:")
        pprint(result.parser_warnings)
        print("ingestion_warnings:")
        pprint(result.ingestion_warnings)

    if batch_result.failed_files:
        print("\n========== Failed Files ==========")
        pprint(batch_result.failed_files)

    if batch_result.results:
        storage_dict = pipeline.to_storage_dict(batch_result.results[0])
        print("\n========== Storage Dict Keys ==========")
        pprint(list(storage_dict.keys()))


def run_excel_quote_ingestion_test() -> None:
    print("\n========== Excel Quote Ingestion Test ==========")
    excel_files = sorted(DATA_DIR.glob("*.xlsx"))

    if not excel_files:
        print("테스트할 Excel 견적서가 없습니다.")
        return

    pipeline = create_quote_ingestion_pipeline()
    result = pipeline.process_file(
        excel_files[0],
        request_id="excel_test_request_001",
    )

    print(f"quote_id: {result.quote_id}")
    print(f"source_file_path: {result.source_file_path}")
    print(f"vendor_name: {result.quote.vendor_name}")
    print(f"project_name: {result.quote.project_name}")
    print(f"received_at: {result.quote.received_at}")
    print(f"total_supply_price: {result.quote.total_supply_price}")
    print(f"total_with_vat: {result.quote.total_with_vat}")
    print(f"delivery_weeks: {result.quote.delivery_weeks}")
    print(f"warranty_months: {result.quote.warranty_months}")
    print(f"line_item_count: {len(result.quote.line_items)}")
    print(f"embedding_dim: {result.embedding_dim}")
    print(f"source_file_hash: {result.quote.source_file_hash}")
    print("first_line_items:")
    pprint(
        [
            {
                "name": item.name,
                "category": item.category.value,
                "total_price": item.total_price,
                "spec_parsed": item.spec_parsed,
            }
            for item in result.quote.line_items[:5]
        ]
    )
    print("parser_raw_matches:")
    pprint(result.parser_raw_matches)
    print("ingestion_warnings:")
    pprint(result.ingestion_warnings)


if __name__ == "__main__":
    main()
