from pathlib import Path
from pprint import pprint

from services.config import get_settings
from services.ocr.factory import create_ocr_provider
from services.parser.factory import create_parser_provider


def main() -> None:
    settings = get_settings()

    ocr_provider = create_ocr_provider(settings)
    parser_provider = create_parser_provider("rule")

    file_path = Path("data/일강_LED전광판(p1_5)_다올씨앤씨.pdf")

    ocr_result = ocr_provider.extract(file_path)
    parsed_result = parser_provider.parse(ocr_result)

    print("\n========== 추출된 견적 정보 ==========")
    pprint(parsed_result.quote)

    print("\n========== 경고 ==========")
    pprint(parsed_result.warnings)

    print("\n========== Raw Matches ==========")
    pprint(parsed_result.raw_matches)


if __name__ == "__main__":
    main()
