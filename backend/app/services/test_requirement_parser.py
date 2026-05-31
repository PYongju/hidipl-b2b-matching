from pathlib import Path
from pprint import pprint

from services.config import get_settings
from services.ocr.factory import create_ocr_provider
from services.requirement.factory import create_requirement_parser_provider
from services.requirement.input_processor import RequirementInputProcessor

SAMPLE_1 = """안녕하세요~ 신규 고객 건 연결드립니다.
확인 후 견적 검토 부탁드립니다. 참고로 요청 사항이 기존 캠트로닉스 건과 유사하니 빠르게 검토해주시면 좋을 것 같습니다~

1. 수수료모델 5%
2. 고객사 : 일강이앤아이
3. 견적 요청 내용 : 회의실 내 태양광 발전 현황 확인을 위한 비디오월 or LED 전광판 고려 중. 두 가지 모두 견적 요청
(1) 46" 비디오월 3x3
(2) LED P1.56 3,000 x 2,000mm
4. 일정 : 3개월 내외
5. 지역 : 충북 음성
6. 단계 : 견적 확인 후 내부 보고하여 의사 결정 예정"""


SAMPLE_2 = """신규 프로젝트 연결드립니다. 가능하시면 월요일 오전까지 검토해주시면 좋을 것 같습니다.

1. 수수료모델 A(5%)
2. 고객사: 스노우스페이스
3. 견적 요청 내용: 커브드 LED전광판 + 평면 LED전광판
(1) 커브드 LED 전광판
- 사이즈 : 12,000 × 3,000
- Pitch : 2.5 이하
(2) 플랫 LED전광판
- 사이즈 : 7,150 × 2,700
- Pitch : 2.5 이하
4. 설치 일정: 2월말~3월초
5. 지역: 서울 홍대(동교동)
6. 기타 사항
- 현재 설계 완료 후 건축 시공 진행 중"""


SAMPLE_3 = """고객정보 화면에서 확인된 기본 정보입니다.
기업명: 스노우스페이스
문의 내용: 디자인중인 공간 컨퍼런스 룸 설치건 문의드려요.
솔루션: LED스크린
단계: 구매 및 견적 비교
예산: 5천만원 이상~1억 미만
지역: 서울
일정: 1개월 이내"""


def test_text_samples() -> None:
    parser = create_requirement_parser_provider("rule")

    for index, sample in enumerate([SAMPLE_1, SAMPLE_2, SAMPLE_3], start=1):
        print(f"\n========== TEXT SAMPLE {index} ==========")
        result = parser.parse(sample)
        pprint(result.requirement)

        if result.warnings:
            print("\nWarnings:")
            pprint(result.warnings)

        print("\nRaw Matches:")
        pprint(result.raw_matches)


def test_file_samples() -> None:
    file_samples = [
        "data/스노우스페이스_홍대_파트너사요청내용.png",
        "data/일강인엘아이_홍대_파트너사요청내용.png",
    ]

    for index, file_sample in enumerate(file_samples, start=1):
        file_path = Path(file_sample)

        print(f"\n========== FILE SAMPLE {index} ==========")
        print(f"File: {file_path}")

        if not file_path.exists():
            print("파일이 없어 건너뜁니다.")
            continue

        settings = get_settings()
        ocr_provider = create_ocr_provider(settings)
        parser_provider = create_requirement_parser_provider("rule")
        processor = RequirementInputProcessor(
            parser_provider=parser_provider,
            ocr_provider=ocr_provider,
        )

        ocr_result = ocr_provider.extract(file_path)
        print("\nOCR Text Preview:")
        print(ocr_result.text[:1000])

        result = processor.process_file(file_path)
        pprint(result.requirement)

        if result.warnings:
            print("\nWarnings:")
            pprint(result.warnings)

        print("\nRaw Matches:")
        pprint(result.raw_matches)


def main() -> None:
    test_text_samples()
    test_file_samples()


if __name__ == "__main__":
    main()
