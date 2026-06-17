from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config.paths import DATA_DIR, OUTPUT_DIR
from services.quote_ingestion.factory import create_quote_ingestion_pipeline
from services.recommendation.factory import create_recommendation_pipeline
from services.requirement.schemas import RequirementInfo, RequirementProduct
from services.requirement_ingestion.factory import create_requirement_ingestion_pipeline


OUTPUT_DIR_PATH = OUTPUT_DIR / "explanation_baseline"
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".xls"}
UNCATEGORIZED_PRODUCT_GROUP = "미분류"

FILE_NAME_BY_SCENARIO_AND_GROUP = {
    ("ILGANG-BASELINE-001", "비디오월"): (
        "ilgangeeni_videowall_explanation_baseline_recommendation.json"
    ),
    ("ILGANG-BASELINE-001", "LED전광판"): (
        "ilgangeeni_led_explanation_baseline_recommendation.json"
    ),
    ("SNOWSPACE-BASELINE-001", "LED전광판"): (
        "snowspace_led_explanation_baseline_recommendation.json"
    ),
}

REQUIRED_OUTPUT_FILES = {
    "ilgangeeni_videowall_explanation_baseline_recommendation.json",
    "ilgangeeni_led_explanation_baseline_recommendation.json",
    "snowspace_led_explanation_baseline_recommendation.json",
    "baseline_index.json",
}

STALE_COMBINED_FILES = {
    "ilgangeeni_explanation_baseline_recommendation.json",
    "snowspace_explanation_baseline_recommendation.json",
}

FORBIDDEN_KEYS = {
    "embedding_vector",
    "requirement_embedding",
    "quote_embedding",
    "partner_embedding",
    "api_key",
    "endpoint",
    "ocr_text",
    "ocr_full_text",
    "raw_ocr_text",
    "full_text",
    "document_text",
    "source_file_abs_path",
    "raw_llm_output",
}


def main() -> None:
    os.environ.setdefault("QUOTE_PARSER_PROVIDER", "rule")
    os.environ.setdefault("ENABLE_LEGACY_SAMPLE_PATCHES", "false")
    build_explanation_baseline_snapshots()
    print("explanation baseline product-group snapshots generated")


def build_explanation_baseline_snapshots() -> None:
    OUTPUT_DIR_PATH.mkdir(parents=True, exist_ok=True)
    for file_name in STALE_COMBINED_FILES:
        stale_path = OUTPUT_DIR_PATH / file_name
        if stale_path.exists():
            stale_path.unlink()

    scenarios = [
        {
            "scenario_id": "ILGANG-BASELINE-001",
            "customer_name": "일강이엔아이",
            "data_dir": DATA_DIR / "일강이엔아이",
            "requirement": build_ilgangeeni_requirement(),
            "expected_groups": {"비디오월": 7, "LED전광판": 5},
        },
        {
            "scenario_id": "SNOWSPACE-BASELINE-001",
            "customer_name": "스노우스페이스",
            "data_dir": DATA_DIR / "스노우스페이스",
            "requirement": build_snowspace_requirement(),
            "expected_groups": {"LED전광판": 4},
        },
    ]

    index = {
        "generated_at": datetime.now().isoformat(),
        "baseline_type": "normal_recommendation_pipeline_result_before_explanation",
        "explanation_provider_called": False,
        "llm_trap_applied": False,
        "scenarios": [],
    }

    generated_files: set[str] = set()
    for scenario in scenarios:
        group_snapshots = build_scenario_group_snapshots(scenario)
        assert set(group_snapshots) == set(scenario["expected_groups"])

        for product_group, snapshot in group_snapshots.items():
            output_file = FILE_NAME_BY_SCENARIO_AND_GROUP[
                (scenario["scenario_id"], product_group)
            ]
            output_path = OUTPUT_DIR_PATH / output_file
            write_json(output_path, snapshot)
            assert_baseline_safe(output_path)
            generated_files.add(output_file)

            index["scenarios"].append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "customer_name": scenario["customer_name"],
                    "product_group": product_group,
                    "quote_result_count": len(snapshot["all_items"]),
                    "top_n": 3,
                    "output_file": output_file,
                }
            )

    index_path = OUTPUT_DIR_PATH / "baseline_index.json"
    write_json(index_path, index)
    assert_baseline_safe(index_path)
    generated_files.add("baseline_index.json")

    assert REQUIRED_OUTPUT_FILES <= generated_files
    assert_required_product_group_snapshots()


def build_scenario_group_snapshots(
    scenario: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    file_paths = find_quote_files(scenario["data_dir"])
    if not file_paths:
        raise FileNotFoundError(f"baseline quote files not found: {scenario['data_dir'].name}")

    request_id = scenario["scenario_id"].lower().replace("-", "_")
    requirement_pipeline = create_requirement_ingestion_pipeline()
    requirement_result = requirement_pipeline.process_requirement_info(
        scenario["requirement"],
        request_id=request_id,
    )

    quote_pipeline = create_quote_ingestion_pipeline()
    quote_batch = quote_pipeline.process_files(
        file_paths,
        request_id=request_id,
    )
    if not quote_batch.results:
        raise AssertionError(f"no quote ingestion results: {scenario['scenario_id']}")

    recommendation_pipeline = create_recommendation_pipeline("rule")
    grouped_results = recommendation_pipeline.recommend_grouped_by_product_group(
        requirement_result=requirement_result,
        quote_results=quote_batch.results,
        top_n=3,
    )

    product_group_counts = {
        product_group: len(result.all_items)
        for product_group, result in grouped_results.items()
    }
    expected_groups = scenario["expected_groups"]
    for product_group, expected_count in expected_groups.items():
        actual_count = product_group_counts.get(product_group)
        assert actual_count == expected_count, (
            f"{scenario['scenario_id']} {product_group} count mismatch: "
            f"expected {expected_count}, got {actual_count}"
        )

    snapshots: dict[str, dict[str, Any]] = {}
    for product_group, group_result in grouped_results.items():
        if product_group == UNCATEGORIZED_PRODUCT_GROUP:
            continue
        if product_group not in expected_groups:
            continue

        snapshot = recommendation_pipeline.to_storage_dict(group_result)
        tag_items_with_product_group(snapshot, product_group)
        metadata = dict(snapshot.get("metadata") or {})
        metadata.update(
            {
                "baseline_type": (
                    "normal_recommendation_pipeline_result_before_explanation"
                ),
                "baseline_scope": "product_group",
                "product_group": product_group,
                "explanation_provider_called": False,
                "llm_trap_applied": False,
                "scenario_id": scenario["scenario_id"],
                "customer_request_summary": scenario["requirement"].request_summary,
                "source_data_dir": f"data/{scenario['data_dir'].name}",
                "quote_file_count": len(file_paths),
                "quote_result_count": len(quote_batch.results),
                "group_quote_result_count": len(group_result.all_items),
                "product_group_counts": product_group_counts,
                "failed_quote_files": [
                    sanitize_value(item) for item in (quote_batch.failed_files or [])
                ],
                "top_n": 3,
                "generated_at": datetime.now().isoformat(),
                "pipeline": {
                    "quote_parser_provider": os.getenv("QUOTE_PARSER_PROVIDER", "rule"),
                    "legacy_sample_patches": os.getenv(
                        "ENABLE_LEGACY_SAMPLE_PATCHES",
                        "false",
                    ).lower()
                    == "true",
                    "recommendation_pipeline": recommendation_pipeline.__class__.__name__,
                },
                "requirement_products": [
                    sanitize_value(product) for product in scenario["requirement"].products
                ],
            }
        )
        snapshot["metadata"] = metadata
        snapshots[product_group] = sanitize_value(snapshot)

    return snapshots


def tag_items_with_product_group(snapshot: dict[str, Any], product_group: str) -> None:
    for item in [*snapshot.get("items", []), *snapshot.get("all_items", [])]:
        item["product_group"] = product_group
        metadata = item.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["product_group"] = product_group


def build_ilgangeeni_requirement() -> RequirementInfo:
    raw_text = (
        "고객사: 일강이엔아이\n"
        "견적 요청 내용: 회의실 내 태양광 발전 현황 확인을 위한 비디오월 or LED 전광판 고려 중\n"
        "두 가지 모두 견적 요청\n"
        "1) 46\" 비디오월 3x3\n"
        "2) LED P1.56, 3,000 x 2,000mm\n"
        "일정: 3개월 내외\n"
        "지역: 충북 음성\n"
        "단계: 견적 확인 후 내부 보고하여 의사결정 예정\n"
        "수수료모델: 5%"
    )
    return RequirementInfo(
        raw_text=raw_text,
        customer_name="일강이엔아이",
        project_name="충북 음성 회의실 디스플레이",
        request_summary=(
            "회의실 내 태양광 발전 현황 확인을 위한 비디오월 및 LED전광판 견적 비교"
        ),
        commission_model="5%",
        commission_rate_percent=5.0,
        products=[
            RequirementProduct(
                product_type="비디오월",
                name='46" 비디오월 3x3',
                diagonal_inch=46,
                layout_rows=3,
                layout_cols=3,
                raw_text='46" 비디오월 3x3',
            ),
            RequirementProduct(
                product_type="LED전광판",
                name="LED P1.56",
                width_mm=3000,
                height_mm=2000,
                pitch_mm=1.56,
                raw_text="LED P1.56, 3,000 x 2,000mm",
            ),
        ],
        region="충북 음성",
        install_schedule_text="3개월 내외",
        project_stage="견적 확인 후 내부 보고하여 의사결정 예정",
        category="디스플레이",
        required_keywords=["비디오월", "LED전광판", "회의실", "태양광 발전 현황"],
        metadata={
            "source": "normal_explanation_baseline",
            "requested_product_groups": ["비디오월", "LED전광판"],
        },
    )


def build_snowspace_requirement() -> RequirementInfo:
    raw_text = (
        "고객사: 스노우스페이스\n"
        "견적 요청 내용: 커브드 LED전광판 + 평면 LED전광판\n"
        "1) 커브드 LED 전광판 - 사이즈: 12,000 x 3,000 - Pitch: 2.5 이하\n"
        "2) 플랫 LED전광판 - 사이즈: 7,150 x 2,700 - Pitch: 2.5 이하\n"
        "설치 일정: 2월말~3월초\n"
        "지역: 서울 홍대(동교동)\n"
        "기타 사항: 현재 설계 완료 후 건축 시공 진행 중\n"
        "수수료모델 A: 5%"
    )
    return RequirementInfo(
        raw_text=raw_text,
        customer_name="스노우스페이스",
        project_name="스노우스페이스 LED전광판",
        request_summary="커브드 LED전광판 및 평면 LED전광판 견적 비교",
        commission_model="A",
        commission_rate_percent=5.0,
        products=[
            RequirementProduct(
                product_type="LED전광판",
                display_type="curved",
                name="커브드 LED 전광판",
                width_mm=12000,
                height_mm=3000,
                pitch_max_mm=2.5,
                raw_text="커브드 LED 전광판, 12,000 x 3,000, Pitch 2.5 이하",
            ),
            RequirementProduct(
                product_type="LED전광판",
                display_type="flat",
                name="플랫 LED전광판",
                width_mm=7150,
                height_mm=2700,
                pitch_max_mm=2.5,
                raw_text="플랫 LED전광판, 7,150 x 2,700, Pitch 2.5 이하",
            ),
        ],
        region="서울 홍대(동교동)",
        install_schedule_text="2월말~3월초",
        project_stage="설계 완료 후 건축 시공 진행 중",
        category="LED전광판",
        required_keywords=["LED전광판", "커브드 LED", "평면 LED", "Pitch 2.5 이하"],
        metadata={
            "source": "normal_explanation_baseline",
            "requested_product_groups": ["LED전광판"],
            "requested_display_types": ["curved", "flat"],
        },
    )


def find_quote_files(data_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(data_dir.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def sanitize_value(value: Any) -> Any:
    if is_dataclass(value):
        return sanitize_value(asdict(value))
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in FORBIDDEN_KEYS:
                continue
            if key == "source_file_path":
                cleaned[key] = safe_path_leaf(item)
                continue
            cleaned[key] = sanitize_value(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_value(item) for item in value]
    if isinstance(value, str):
        return sanitize_string(value)
    return value


def sanitize_string(value: str) -> str:
    text = value.replace("\\", "/")
    if "C:/Users/" in text:
        return text.rsplit("/", 1)[-1]
    return text


def safe_path_leaf(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    return str(value).replace("\\", "/").rsplit("/", 1)[-1]


def assert_required_product_group_snapshots() -> None:
    video = load_json(
        OUTPUT_DIR_PATH / "ilgangeeni_videowall_explanation_baseline_recommendation.json"
    )
    led = load_json(
        OUTPUT_DIR_PATH / "ilgangeeni_led_explanation_baseline_recommendation.json"
    )
    snow = load_json(
        OUTPUT_DIR_PATH / "snowspace_led_explanation_baseline_recommendation.json"
    )
    index = load_json(OUTPUT_DIR_PATH / "baseline_index.json")

    assert video["metadata"]["product_group"] == "비디오월"
    assert led["metadata"]["product_group"] == "LED전광판"
    assert snow["metadata"]["product_group"] == "LED전광판"

    assert len(video["all_items"]) == 7
    assert len(led["all_items"]) == 5
    assert len(snow["all_items"]) == 4

    for snapshot in [video, led, snow]:
        assert len(snapshot["items"]) <= 3
        assert snapshot["metadata"]["baseline_scope"] == "product_group"
        assert snapshot["metadata"]["explanation_provider_called"] is False
        assert snapshot["metadata"]["llm_trap_applied"] is False
        assert "items" in snapshot
        assert "all_items" in snapshot
        assert "failed_candidates" in snapshot
        assert "filtered_candidates" in snapshot
        assert [item["rank"] for item in snapshot["items"]] == list(
            range(1, len(snapshot["items"]) + 1)
        )

    assert all("비디오월" in item_product_group_hint(item) for item in video["all_items"])
    assert all(
        "LED" in item_product_group_hint(item)
        or "전광판" in item_product_group_hint(item)
        for item in led["all_items"]
    )
    assert all(
        "LED" in item_product_group_hint(item)
        or "전광판" in item_product_group_hint(item)
        for item in snow["all_items"]
    )

    assert len(index["scenarios"]) == 3
    assert {
        (item["scenario_id"], item["product_group"], item["output_file"])
        for item in index["scenarios"]
    } == {
        (
            "ILGANG-BASELINE-001",
            "비디오월",
            "ilgangeeni_videowall_explanation_baseline_recommendation.json",
        ),
        (
            "ILGANG-BASELINE-001",
            "LED전광판",
            "ilgangeeni_led_explanation_baseline_recommendation.json",
        ),
        (
            "SNOWSPACE-BASELINE-001",
            "LED전광판",
            "snowspace_led_explanation_baseline_recommendation.json",
        ),
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def item_product_group_hint(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    values = [
        item.get("product_group"),
        metadata.get("product_group"),
        item.get("quote_id"),
        item.get("project_name"),
        item.get("vendor_name"),
    ]
    return " ".join(str(value) for value in values if value)


def assert_baseline_safe(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    forbidden_tokens = [
        "embedding_vector",
        "requirement_embedding",
        "quote_embedding",
        "partner_embedding",
        "api_key",
        "endpoint",
        "ocr_text",
        "ocr_full_text",
        "raw_ocr_text",
        "full_text",
        "document_text",
        "source_file_abs_path",
        "C:\\Users\\",
        "C:/Users/",
    ]
    for token in forbidden_tokens:
        assert token not in text

    data = json.loads(text)
    if path.name != "baseline_index.json":
        assert data["top_n"] == 3
        assert data["items"]
        assert data["all_items"]
        assert data["metadata"]["explanation_provider_called"] is False
        assert data["metadata"]["llm_trap_applied"] is False


if __name__ == "__main__":
    main()
