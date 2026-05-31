import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from pprint import pprint
from typing import Any

from dotenv import load_dotenv

from services.explanation.factory import create_explanation_provider
from services.explanation.schemas import RecommendationExplanationResult
from services.partner_matching.factory import create_partner_matching_pipeline
from services.partner_matching.schemas import PartnerMatchingResult
from services.quote_ingestion.schemas import QuoteIngestionBatchResult
from services.recommendation.schemas import RecommendationPipelineResult
from services.recommendation.factory import create_recommendation_pipeline
from services.requirement_ingestion.factory import create_requirement_ingestion_pipeline
from services.requirement_ingestion.schemas import RequirementIngestionResult
from services.quote_ingestion.factory import create_quote_ingestion_pipeline

REQUEST_ID = "demo_request_001"
SUPPORTED_QUOTE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".xls"}
OUTPUT_PATH = Path("data/demo_outputs/full_pipeline_demo_result_ilgang.json")


# def get_demo_requirement_text() -> str:
#     return """신규 프로젝트 연결드립니다. 가능하시면 월요일 오전까지 검토해주시면 좋을 것 같습니다.

# 1. 수수료모델 A(5%)
# 2. 고객사: 스노우스페이스
# 3. 견적 요청 내용: 커브드 LED전광판 + 평면 LED전광판
#    (1) 커브드 LED 전광판
# * 사이즈 : 12,000 × 3,000
# * Pitch : 2.5 이하
#   (2) 플랫 LED전광판
# * 사이즈 : 7,150 × 2,700
# * Pitch : 2.5 이하


# 4. 설치 일정: 2월말~3월초
# 5. 지역: 서울 홍대(동교동)
# 6. 기타 사항
# * 현재 설계 완료 후 건축 시공 진행 중
# """
def get_demo_requirement_text() -> str:
    return """안녕하세요~ 신규 고객 건 연결드립니다.
확인 후 견적 검토 부탁드립니다. 참고로 요청 사항이 기존 캠트로닉스 건과 유사하니 빠르게 검토해주시면 좋을 것 같습니다~

1. 수수료모델 5%
2. 고객사: 일강이엔아이
3. 견적 요청 내용: 회의실 내 태양광 발전 현황 확인을 위한 비디오월 or LED 전광판 고려 중. 두 가지 모두 견적 요청
   (1) 46" 비디오월 3x3
   (2) LED P1.56 3,000 x 2,000mm

4. 일정: 3개월 내외
5. 지역: 충북 음성
6. 단계: 견적 확인 후 내부 보고하여 의사결정 예정
"""


def find_quote_files() -> list[Path]:
    for directory in [Path("data"), Path("samples/quotes")]:
        if not directory.exists():
            continue

        file_paths = sorted(
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_QUOTE_EXTENSIONS
        )
        if file_paths:
            return file_paths

    return []


def run_requirement_ingestion(
    requirement_text: str,
    request_id: str,
) -> RequirementIngestionResult:
    pipeline = create_requirement_ingestion_pipeline()
    return pipeline.process_text(requirement_text, request_id=request_id)


def run_quote_ingestion(
    file_paths: list[Path],
    request_id: str,
) -> QuoteIngestionBatchResult:
    pipeline = create_quote_ingestion_pipeline()
    return pipeline.process_files(file_paths, request_id=request_id)


def run_partner_matching(
    requirement_result: RequirementIngestionResult,
) -> PartnerMatchingResult | None:
    try:
        pipeline = create_partner_matching_pipeline()
        return pipeline.run(requirement_result, top_n=10, similarity_threshold=60.0)
    except Exception as e:
        print(f"PartnerMatching 실행 실패, 데모에서는 계속 진행합니다: {e}")
        return None


def run_recommendation(
    requirement_result: RequirementIngestionResult,
    quote_results,
) -> RecommendationPipelineResult:
    pipeline = create_recommendation_pipeline("rule")
    return pipeline.recommend(requirement_result, quote_results, top_n=3)


def run_explanation(
    recommendation_result: RecommendationPipelineResult,
) -> RecommendationExplanationResult:
    requested_provider = os.getenv("EXPLANATION_PROVIDER")
    provider_type = requested_provider or (
        "azure_openai" if os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT") else "template"
    )

    try:
        provider = create_explanation_provider(provider_type)
        return provider.generate(recommendation_result)
    except Exception as e:
        if provider_type == "template":
            raise

        print(f"Azure Explanation 실패, template provider로 fallback합니다: {e}")
        provider = create_explanation_provider("template")
        result = provider.generate(recommendation_result)
        result.provider = "template_fallback"
        result.warnings.append(
            f"{provider_type} provider 실패로 template fallback 사용: {e}"
        )
        result.metadata["requested_provider"] = provider_type
        return result


def build_demo_output(
    *,
    request_id: str,
    ran_at: str,
    quote_file_count: int,
    requirement_result: RequirementIngestionResult,
    partner_matching_result: PartnerMatchingResult | None,
    quote_batch_result: QuoteIngestionBatchResult,
    recommendation_result: RecommendationPipelineResult,
    explanation_result: RecommendationExplanationResult,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "requirement": _compact_requirement_result(requirement_result),
        "partner_matching": (
            _compact_partner_matching_result(partner_matching_result)
            if partner_matching_result is not None
            else None
        ),
        "quote_ingestion": {
            "processed_count": len(quote_batch_result.results),
            "results": [
                _compact_quote_result(result) for result in quote_batch_result.results
            ],
            "failed_files": quote_batch_result.failed_files,
        },
        "recommendation": _strip_large_fields(asdict(recommendation_result)),
        "explanation": _strip_large_fields(asdict(explanation_result)),
        "metadata": {
            "ran_at": ran_at,
            "explanation_provider": explanation_result.provider,
            "quote_file_count": quote_file_count,
        },
    }


def save_demo_output(output: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_to_jsonable(output), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def print_requirement_result(result: RequirementIngestionResult) -> None:
    requirement = result.requirement
    print("\n========== Requirement Ingestion 결과 ==========")
    print("customer_name:", requirement.customer_name)
    print("request_summary:", requirement.request_summary)
    print("products 개수:", len(requirement.products))
    print("region:", requirement.region)
    print("install_schedule_text:", requirement.install_schedule_text)
    print("requirement embedding_dim:", result.embedding_dim)
    print("parser_warnings:")
    pprint(result.parser_warnings)
    print("ingestion_warnings:")
    pprint(result.ingestion_warnings)


def print_quote_ingestion_result(batch_result: QuoteIngestionBatchResult) -> None:
    print("\n========== Quote Ingestion 결과 ==========")
    for result in batch_result.results:
        quote = result.quote
        print()
        print("quote_id:", result.quote_id)
        print("source_file_path:", result.source_file_path)
        print("vendor_name:", quote.vendor_name)
        print("project_name:", quote.project_name)
        print("total_supply_price:", quote.total_supply_price)
        print("total_with_vat:", quote.total_with_vat)
        print("line_items 개수:", len(quote.line_items))
        print("embedding_dim:", result.embedding_dim)
        print("parser_warnings:")
        pprint(result.parser_warnings)
        print("ingestion_warnings:")
        pprint(result.ingestion_warnings)

    if batch_result.failed_files:
        print("\nfailed_files:")
        pprint(batch_result.failed_files)


def print_partner_matching_result(result: PartnerMatchingResult | None) -> None:
    print("\n========== Partner Matching 결과 ==========")
    if result is None:
        print("PartnerMatching 결과가 없습니다.")
        return

    print("top_n:", result.top_n)
    print("filtered partner count:", len(result.filtered_candidates))
    for index, candidate in enumerate(result.candidates, start=1):
        print()
        print("rank:", index)
        print("partner_name:", candidate.partner_name)
        print("semantic_similarity_score:", candidate.semantic_similarity_score)
        print("specialty_tags:")
        pprint(candidate.specialty_tags)
        print("is_premium:", candidate.is_premium)
        print("success_rate:", candidate.success_rate)
        print("response_speed:", candidate.response_speed)
        print("financial_status:", candidate.financial_status)
        print("filter_reasons:")
        pprint(candidate.filter_reasons)


def print_recommendation_result(result: RecommendationPipelineResult) -> None:
    print("\n========== Recommendation 결과 ==========")
    for item in result.items:
        print()
        print("rank:", item.rank)
        print("quote_id:", item.quote_id)
        print("vendor_name:", item.vendor_name)
        print("partner_name:", item.partner_name)
        print("final_score:", item.final_score)
        print("spec_score:", item.spec_score)
        print("price_score:", item.price_score)
        print("delivery_score:", item.delivery_score)
        print("warranty_score:", item.warranty_score)
        print("installation_score:", item.installation_score)
        print("cosine_similarity:", item.cosine_similarity)
        print("is_premium:", item.is_premium)
        print("success_rate:", item.success_rate)
        print("business_rule_passed:", item.business_rule_passed)
        print("filter_reasons:")
        pprint(item.filter_reasons)
        print("check_required:")
        pprint(item.check_required)

    if not result.items:
        print("추천 가능한 Top-N 후보가 없습니다.")
        print("filtered_candidates:")
        pprint(result.filtered_candidates)


def print_explanation_result(result: RecommendationExplanationResult) -> None:
    print("\n========== Explanation 결과 ==========")
    print("provider:", result.provider)
    print("overall_summary:")
    print(result.overall_summary)
    print("\nsupplier_explanations:")
    for item in result.supplier_explanations:
        print()
        print("rank:", item.rank)
        print("vendor_name:", item.vendor_name)
        print("card_summary:", item.card_summary)
        print("strengths:")
        pprint(item.strengths)
        print("weaknesses:")
        pprint(item.weaknesses)
        print("check_required:")
        pprint(item.check_required)

    if result.warnings:
        print("\nexplanation warnings:")
        pprint(result.warnings)


def main() -> None:
    load_dotenv()

    ran_at = datetime.now().isoformat(timespec="seconds")
    requirement_text = get_demo_requirement_text()
    quote_files = find_quote_files()
    requested_provider = os.getenv("EXPLANATION_PROVIDER") or (
        "azure_openai" if os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT") else "template"
    )

    print("========== Full Pipeline Demo 시작 ==========")
    print("실행 시간:", ran_at)
    print("request_id:", REQUEST_ID)
    print("사용 explanation provider:", requested_provider)
    print("견적서 파일 개수:", len(quote_files))

    if not quote_files:
        print("처리할 견적서 파일이 없습니다.")
        return

    try:
        requirement_result = run_requirement_ingestion(requirement_text, REQUEST_ID)
    except Exception as e:
        print(f"Requirement ingestion 실패: {e}")
        return
    print_requirement_result(requirement_result)

    partner_matching_result = run_partner_matching(requirement_result)
    print_partner_matching_result(partner_matching_result)

    try:
        quote_batch_result = run_quote_ingestion(quote_files, REQUEST_ID)
    except Exception as e:
        print(f"Quote ingestion 실행 실패: {e}")
        return
    print_quote_ingestion_result(quote_batch_result)

    if not quote_batch_result.results:
        print(
            "Quote ingestion 성공 결과가 0개입니다. Recommendation을 실행하지 않습니다."
        )
        return

    try:
        recommendation_result = run_recommendation(
            requirement_result,
            quote_batch_result.results,
        )
    except Exception as e:
        print(f"Recommendation 실패: {e}")
        return
    print_recommendation_result(recommendation_result)

    try:
        explanation_result = run_explanation(recommendation_result)
    except Exception as e:
        print(f"Explanation 실패: {e}")
        return
    print_explanation_result(explanation_result)

    output = build_demo_output(
        request_id=REQUEST_ID,
        ran_at=ran_at,
        quote_file_count=len(quote_files),
        requirement_result=requirement_result,
        partner_matching_result=partner_matching_result,
        quote_batch_result=quote_batch_result,
        recommendation_result=recommendation_result,
        explanation_result=explanation_result,
    )
    save_demo_output(output, OUTPUT_PATH)
    print("\n최종 JSON 저장:", OUTPUT_PATH)


def _compact_requirement_result(result: RequirementIngestionResult) -> dict[str, Any]:
    return {
        "request_id": result.request_id,
        "source_type": result.source_type,
        "source_path": result.source_path,
        "requirement": asdict(result.requirement),
        "embedding_dim": result.embedding_dim,
        "raw_text_preview": result.raw_text_preview[:1000],
        "parser_warnings": result.parser_warnings,
        "parser_raw_matches": result.parser_raw_matches,
        "ingestion_warnings": result.ingestion_warnings,
        "metadata": result.metadata,
    }


def _compact_quote_result(result) -> dict[str, Any]:
    return {
        "quote_id": result.quote_id,
        "request_id": result.request_id,
        "source_file_path": result.source_file_path,
        "quote": asdict(result.quote),
        "embedding_dim": result.embedding_dim,
        "ocr_text_preview": result.ocr_text_preview[:1000],
        "parser_warnings": result.parser_warnings,
        "parser_raw_matches": result.parser_raw_matches,
        "ingestion_warnings": result.ingestion_warnings,
        "metadata": result.metadata,
    }


def _compact_partner_matching_result(
    result: PartnerMatchingResult,
) -> dict[str, Any]:
    return {
        "top_n": result.top_n,
        "candidates": [
            {
                "partner_name": candidate.partner_name,
                "semantic_similarity_score": candidate.semantic_similarity_score,
                "cosine_similarity": candidate.cosine_similarity,
                "specialty_tags": candidate.specialty_tags,
                "is_premium": candidate.is_premium,
                "success_rate": candidate.success_rate,
                "response_speed": candidate.response_speed,
                "financial_status": candidate.financial_status,
                "business_rule_passed": candidate.business_rule_passed,
                "filter_reasons": candidate.filter_reasons,
            }
            for candidate in result.candidates
        ],
        "filtered_count": len(result.filtered_candidates),
        "metadata": result.metadata,
    }


def _strip_large_fields(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == "embedding_vector":
                continue
            if key in {"embedding_text"}:
                result[key] = str(item)[:1000]
                continue
            if key in {"ocr_text_preview", "raw_text_preview"}:
                result[key] = str(item)[:1000]
                continue
            result[key] = _strip_large_fields(item)
        return result

    if isinstance(value, list):
        return [_strip_large_fields(item) for item in value]

    return value


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]

    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]

    return value


if __name__ == "__main__":
    main()
