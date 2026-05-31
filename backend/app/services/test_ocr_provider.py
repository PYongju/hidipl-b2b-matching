from pathlib import Path

from services.config import get_settings
from services.ocr.factory import create_ocr_provider


def main() -> None:
    settings = get_settings()
    ocr_provider = create_ocr_provider(settings)

    file_path = Path("data/일강_LED전광판(p1_5)_다올씨앤씨.pdf")

    result = ocr_provider.extract(file_path)

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
