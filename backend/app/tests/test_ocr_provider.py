from config.paths import DATA_DIR
from services.config import get_settings
from services.ocr.factory import create_ocr_provider


def main() -> None:
    settings = get_settings()
    ocr_provider = create_ocr_provider(settings)

    file_paths = sorted(DATA_DIR.glob("*.pdf"))
    if not file_paths:
        print("테스트할 PDF 파일이 없습니다.")
        return

    result = ocr_provider.extract(file_paths[0])

    print("\n========= 전체 텍스트 ============")
    print(result.text[:2000])

    print("\n========= 페이지 정보 ============")
    for page in result.pages:
        print(f"Page {page.page_number}: {len(page.lines)} lines")

    print("\n========= 표 정보 ============")
    for idx, table in enumerate(result.tables):
        print(f"\nTable {idx + 1}")
        print(f"Rows : {table.row_count}, Columns : {table.column_count}")

        for row in table.cells:
            print(row)

    print("\n========= Key-Value ============")
    for key, value in result.key_values.items():
        print(f"{key} : {value}")


if __name__ == "__main__":
    main()
