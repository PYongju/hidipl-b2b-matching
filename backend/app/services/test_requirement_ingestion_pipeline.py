from pprint import pprint

from config.paths import DATA_DIR
from services.requirement_ingestion.factory import (
    create_requirement_ingestion_pipeline,
)


REQUIREMENT_TEXT = """신규 프로젝트 연결드립니다. 가능하시면 월요일 오전까지 검토해주시면 좋을 것 같습니다.

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


def main() -> None:
    run_text_ingestion_test()
    run_file_ingestion_test()
    run_storage_dict_test()


def run_text_ingestion_test():
    print("\n========== Requirement Text Ingestion Test ==========")
    pipeline = create_requirement_ingestion_pipeline()
    result = pipeline.process_text(
        REQUIREMENT_TEXT,
        request_id="text_test_request",
    )

    _print_text_result(result)
    return result, pipeline


def run_file_ingestion_test() -> None:
    print("\n========== Requirement File Ingestion Test ==========")
    pipeline = create_requirement_ingestion_pipeline()
    sample_dir = DATA_DIR / "sample_files" / "requirements"
    file_paths = []
    for pattern in ["*.png", "*.jpg", "*.jpeg", "*.pdf"]:
        file_paths.extend(sorted(sample_dir.glob(pattern)))

    if not file_paths:
        print("테스트할 고객 요청 파일이 없습니다.")
        return

    file_path = file_paths[0]
    try:
        result = pipeline.process_file(
            file_path,
            request_id="file_test_request",
        )
    except Exception as e:
        print(f"고객 요청 파일 ingestion 실패: {e}")
        return

    print(f"source_path: {result.source_path}")
    print(f"customer_name: {result.requirement.customer_name}")
    print(f"product_count: {len(result.requirement.products)}")
    print(f"region: {result.requirement.region}")
    print(f"embedding_dim: {result.embedding_dim}")
    print("parser_warnings:")
    pprint(result.parser_warnings)
    print("ingestion_warnings:")
    pprint(result.ingestion_warnings)


def run_storage_dict_test() -> None:
    print("\n========== Requirement Storage Dict Test ==========")
    result, pipeline = run_text_ingestion_test()
    storage_dict = pipeline.to_storage_dict(result)
    keys = list(storage_dict.keys())
    expected_keys = [
        "request_id",
        "source_type",
        "source_path",
        "requirement",
        "embedding_text",
        "embedding_vector",
        "embedding_dim",
        "raw_text_preview",
        "parser_warnings",
        "parser_raw_matches",
        "ingestion_warnings",
        "metadata",
    ]

    print("storage_dict keys:")
    pprint(keys)
    print("contains expected keys:")
    pprint({key: key in storage_dict for key in expected_keys})


def _print_text_result(result) -> None:
    print(f"request_id: {result.request_id}")
    print(f"source_type: {result.source_type}")
    print(f"customer_name: {result.requirement.customer_name}")
    print(f"request_summary: {result.requirement.request_summary}")
    print(f"product_count: {len(result.requirement.products)}")
    print(f"region: {result.requirement.region}")
    print(f"install_schedule_text: {result.requirement.install_schedule_text}")
    print(f"embedding_dim: {result.embedding_dim}")
    print("parser_warnings:")
    pprint(result.parser_warnings)
    print("ingestion_warnings:")
    pprint(result.ingestion_warnings)
    print("\nEmbedding text preview:")
    print(result.embedding_text[:1000])


if __name__ == "__main__":
    main()
