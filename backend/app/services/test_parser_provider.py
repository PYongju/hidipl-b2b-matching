from pprint import pprint

from config.paths import DATA_DIR
from services.config import get_settings
from services.ocr.factory import create_ocr_provider
from services.parser.factory import create_parser_provider


def main() -> None:
    settings = get_settings()

    ocr_provider = create_ocr_provider(settings)
    parser_provider = create_parser_provider("rule")

    file_paths = sorted(DATA_DIR.glob("*.pdf"))
    if not file_paths:
        print("테스트할 PDF 파일이 없습니다.")
        return

    ocr_result = ocr_provider.extract(file_paths[0])
    parsed_result = parser_provider.parse(ocr_result)

    print("\n========== 추출된 견적 정보 ==========")
    pprint(parsed_result.quote)

    print("\n========== 경고 ==========")
    pprint(parsed_result.warnings)

    print("\n========== Raw Matches ==========")
    pprint(parsed_result.raw_matches)


if __name__ == "__main__":
    main()
