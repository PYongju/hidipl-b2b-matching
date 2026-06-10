import argparse
import json
import os
import re
from collections import Counter
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from config.paths import DATA_DIR, OUTPUT_DIR
from services.api_demo.response_builders import (
    _build_hardware_section,
    build_vendor_snapshot_summary,
)
from services.config import get_settings
from services.ocr.factory import create_ocr_provider
from services.parser.quote_parser_validator import (
    apply_delivery_normalization,
    build_amount_validation,
    build_delivery_validation,
    build_line_item_validation,
    build_quote_document_check_required,
    detect_multi_option,
    item_name_spec_split_needs_review,
    normalize_line_item_category,
)
from services.parser.rule_based_quote_parser import RuleBasedQuoteParser
from services.quote_ingestion.quote_ingestion_pipeline import QuoteIngestionPipeline


SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
EXCLUDED_DIR_NAMES = {"demo_outputs", "api_demo_uploads", "sample_files"}
REQUIRED_ENV_NAMES = [
    "DOCUMENTINTELLIGENCE_ENDPOINT",
    "DOCUMENTINTELLIGENCE_API_KEY",
]
BASELINE_DIR = OUTPUT_DIR / "rule_parser_baseline"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=[
            "before",
            "after",
            "after_v3",
            "after_v4",
            "after_v5_generalized",
            "after_v6_generalized",
            "after_v7_generalized",
            "after_v8_generalized",
            "after_v9_generalized",
            "after_v10_generalized",
            "after_v11_generalized",
            "after_v12_generalized",
        ],
        required=True,
    )
    args = parser.parse_args()

    load_dotenv()
    os.environ["QUOTE_PARSER_PROVIDER"] = "rule"

    missing = [name for name in REQUIRED_ENV_NAMES if not os.getenv(name)]
    if missing:
        print("Missing required environment variables for Rule Parser baseline:")
        for name in missing:
            print(f"- {name}")
        return

    quote_files = find_quote_files()
    if not quote_files:
        print(f"No Rule Parser baseline target files found in {relative_path(DATA_DIR)}")
        return

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    pipeline = create_rule_pipeline()

    results: list[dict[str, Any]] = []
    failed_files: list[dict[str, Any]] = []
    result_index = 1
    for file_path in quote_files:
        try:
            file_results = pipeline.process_file_to_results(
                file_path,
                request_id=f"rule_parser_baseline_{args.phase}",
            )
            for result in file_results:
                item = build_success_result(result_index, file_path, result)
                results.append(item)
                print_file_result(result_index, item)
                result_index += 1
        except Exception as e:
            failed = build_failed_result(result_index, file_path, e)
            failed_files.append(failed)
            print_failed_result(result_index, failed)
            result_index += 1

    summary_payload = build_summary(results, failed_files, len(quote_files))
    detail_payload = {
        "run_config": {
            "parser_provider": "rule",
            "pipeline": "OCR -> RuleBasedQuoteParserProvider -> QuoteParserValidator",
            "input_dir": "data",
            "input_file_count": len(quote_files),
            "quote_result_count": len(results),
            "executed_at": datetime.now().isoformat(timespec="seconds"),
            "note": "LLM Parser를 사용하지 않은 Rule Parser baseline 결과",
        },
        "results": results,
        "failed_files": failed_files,
    }
    if args.phase in {"after_v10_generalized", "after_v11_generalized", "after_v12_generalized"}:
        detail_payload["summary"] = summary_payload
    report_text = build_issue_report(args.phase, summary_payload, results, failed_files)

    detail_path = BASELINE_DIR / f"rule_parser_baseline_{args.phase}.json"
    summary_path = BASELINE_DIR / f"rule_parser_baseline_summary_{args.phase}.json"
    report_path = BASELINE_DIR / f"rule_parser_issue_report_{args.phase}.md"
    write_json(detail_path, detail_payload)
    if args.phase in {"after_v10_generalized", "after_v11_generalized", "after_v12_generalized"}:
        print_single_output_summary(summary_payload, detail_path)
        return
    write_json(summary_path, summary_payload)
    report_path.write_text(report_text, encoding="utf-8")

    if args.phase in {"after", "after_v3", "after_v4", "after_v5_generalized", "after_v6_generalized", "after_v7_generalized", "after_v8_generalized", "after_v9_generalized"}:
        diff_path = BASELINE_DIR / (
            f"rule_parser_before_after_diff_{args.phase.removeprefix('after_')}.json"
            if args.phase.startswith("after_")
            else "rule_parser_before_after_diff.json"
        )
        before_summary_path = BASELINE_DIR / "rule_parser_baseline_summary_before.json"
        if before_summary_path.exists():
            before_summary = json.loads(before_summary_path.read_text(encoding="utf-8"))
            write_json(diff_path, build_before_after_diff(before_summary, summary_payload))
    if args.phase == "after_v5_generalized":
        write_hardcoded_patch_audit()
    if args.phase == "after_v6_generalized":
        (BASELINE_DIR / "rule_parser_generalization_report_v6.md").write_text(
            build_generalization_v6_report(summary_payload),
            encoding="utf-8",
        )
    if args.phase == "after_v7_generalized":
        (BASELINE_DIR / "rule_parser_generalization_report_v7.md").write_text(
            build_generalization_v7_report(summary_payload),
            encoding="utf-8",
        )
    if args.phase == "after_v8_generalized":
        (BASELINE_DIR / "rule_parser_generalization_report_v8.md").write_text(
            build_generalization_v8_report(summary_payload),
            encoding="utf-8",
        )
    if args.phase == "after_v9_generalized":
        (BASELINE_DIR / "rule_parser_generalization_report_v9.md").write_text(
            build_generalization_v9_report(summary_payload),
            encoding="utf-8",
        )

    print_summary(summary_payload, detail_path, summary_path, report_path)


def build_generalization_v6_report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Rule Parser Generalization Report v6",
            "",
            "- `QUOTE_PARSER_PROVIDER=rule`",
            "- `ENABLE_LEGACY_SAMPLE_PATCHES=false`",
            "- LLM Parser / Azure OpenAI Chat: not used",
            "",
            f"- input_file_count: {summary.get('input_file_count')}",
            f"- quote_result_count: {summary.get('quote_result_count')}",
            f"- line_items_sum_normal_count: {summary.get('line_items_sum_normal_count')}",
            f"- amount_validation_normal_count: {summary.get('amount_validation_normal_count')}",
            f"- multi_option_split_count: {summary.get('multi_option_split_count')}",
            "",
        ]
    )


def build_generalization_v7_report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Rule Parser Generalization Report v7",
            "",
            "- `QUOTE_PARSER_PROVIDER=rule`",
            "- `ENABLE_LEGACY_SAMPLE_PATCHES=false`",
            "- LLM Parser / Azure OpenAI Chat: not used",
            "",
            f"- quote_result_count: {summary.get('quote_result_count')}",
            f"- line_items_sum_normal_count: {summary.get('line_items_sum_normal_count')}",
            f"- residual_item_count: {summary.get('residual_item_count')}",
            f"- installation_included_count: {summary.get('installation_included_count')}",
            f"- spec_sanitized_count: {summary.get('spec_sanitized_count')}",
            "",
        ]
    )


def build_generalization_v8_report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Rule Parser Generalization Report v8",
            "",
            "- `QUOTE_PARSER_PROVIDER=rule`",
            "- `ENABLE_LEGACY_SAMPLE_PATCHES=false`",
            "- LLM Parser / Azure OpenAI Chat: not used",
            "",
            f"- quote_result_count: {summary.get('quote_result_count')}",
            f"- line_items_sum_normal_count: {summary.get('line_items_sum_normal_count')}",
            f"- amount_validation_normal_count: {summary.get('amount_validation_normal_count')}",
            f"- residual_item_count: {summary.get('residual_item_count')}",
            f"- residual_check_required_count: {summary.get('residual_check_required_count')}",
            f"- installation_included_count: {summary.get('installation_included_count')}",
            f"- category_reclassified_count: {summary.get('category_reclassified_count')}",
            f"- delivery_raw_clean_count: {summary.get('delivery_raw_clean_count')}",
            f"- source_spec_raw_preview_present_count: {summary.get('source_spec_raw_preview_present_count')}",
            f"- azure_ocr_test_status: {summary.get('azure_ocr_test_status')}",
            f"- api_demo_env_test_status: {summary.get('api_demo_env_test_status')}",
            "",
        ]
    )


def build_generalization_v9_report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Rule Parser Generalization Report v9",
            "",
            "- `QUOTE_PARSER_PROVIDER=rule`",
            "- `ENABLE_LEGACY_SAMPLE_PATCHES=false`",
            "- LLM Parser / Azure OpenAI Chat: not used",
            "",
            f"- quote_result_count: {summary.get('quote_result_count')}",
            f"- line_items_sum_normal_count: {summary.get('line_items_sum_normal_count')}",
            f"- amount_validation_normal_count: {summary.get('amount_validation_normal_count')}",
            f"- residual_item_count: {summary.get('residual_item_count')}",
            f"- residual_check_required_count: {summary.get('residual_check_required_count')}",
            f"- hyosung_led_residual_count: {summary.get('hyosung_led_residual_count')}",
            f"- hyosung_videowall_residual_count: {summary.get('hyosung_videowall_residual_count')}",
            f"- hyosung_led_line_item_count: {summary.get('hyosung_led_line_item_count')}",
            f"- hyosung_videowall_line_item_count: {summary.get('hyosung_videowall_line_item_count')}",
            f"- category_reclassified_count: {summary.get('category_reclassified_count')}",
            f"- source_spec_raw_preview_present_count: {summary.get('source_spec_raw_preview_present_count')}",
            "",
            "## Remaining Issues Top 10",
            "",
            *[
                f"- {item.get('issue')}: {item.get('count')}"
                for item in summary.get("remaining_detected_issues_top10", [])
            ],
            "",
        ]
    )


def write_hardcoded_patch_audit() -> None:
    path = BASELINE_DIR / "rule_parser_hardcoded_patch_audit.md"
    path.write_text(
        """# Rule Parser Hardcoded Patch Audit

## Existing Legacy Patch Functions

- `_apply_known_hyosung_multi_option_items`
- `_apply_known_orion_items`
- `_known_display_spec`
- `_apply_known_spec_overrides`
- `_extract_known_summary_amounts`
- `_extract_known_delivery`
- `_apply_sysmate_55_amounts`

## Production Default

- `ENABLE_LEGACY_SAMPLE_PATCHES=false`
- 위 legacy 함수는 기본 production parser 경로에서 실행되지 않습니다.
- production 기본 경로는 `rule_amount_extractor`, `rule_display_spec_extractor`,
  `rule_line_item_parser`, `rule_profiles`를 사용합니다.

## Removed From Main Execution Path

- 업체/특정 금액 문자열 기반 QuoteItem 직접 생성
- 모델명별 고정 display spec 반환
- 특정 문서별 고정 summary amount/delivery 반환

## Still Present

- 기존 baseline 비교와 단계적 제거를 위해 legacy 함수 정의는 파일에 남아 있습니다.
- 환경변수를 명시적으로 `true`로 설정한 경우에만 실행됩니다.

## Removal Plan

1. Generic table parser의 multi-line block/option-section 처리를 강화합니다.
2. Legacy-off golden baseline이 목표 수준에 도달하면 legacy 함수 정의를 삭제합니다.
3. 업체명이 아닌 OCR table fingerprint 기반 profile만 유지합니다.
""",
        encoding="utf-8",
    )


def create_rule_pipeline() -> QuoteIngestionPipeline:
    settings = get_settings()
    ocr_provider = create_ocr_provider(settings)
    return QuoteIngestionPipeline(
        ocr_provider=ocr_provider,
        parser_provider=RuleBasedQuoteParser(),
        embedding_provider=None,
    )


def find_quote_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(DATA_DIR.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        if path.parent.name in EXCLUDED_DIR_NAMES:
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        files.append(path)
    return files


def build_success_result(index: int, file_path: Path, result) -> dict[str, Any]:
    quote = result.quote
    raw_matches = result.parser_raw_matches or {}
    category_normalization = []
    for item in quote.line_items:
        change = normalize_line_item_category(item)
        if change:
            category_normalization.append(change)

    delivery_validation = apply_delivery_normalization(quote)
    amount_validation = build_amount_validation(
        quote,
        quoted_tax_amount=raw_matches.get("quoted_tax_amount"),
    )
    line_item_validation = build_line_item_validation(quote)
    if (result.metadata or {}).get("split_from_multi_option"):
        multi_option_detection = {
            **((raw_matches.get("multi_option_detection") or {})),
            "is_multi_option_possible": False,
            "auto_split": True,
        }
    else:
        multi_option_detection = detect_multi_option(
            quote,
            source_text=result.ocr_text_preview or "",
        )
    check_required = build_quote_document_check_required(
        quote,
        source_text=result.ocr_text_preview or "",
        amount_validation=amount_validation,
        delivery_validation=delivery_validation,
        multi_option_detection=multi_option_detection,
    )
    existing_checks = result.metadata.get("parser_check_required") or []
    check_required = dedupe([*existing_checks, *check_required])
    if (result.parser_raw_matches or {}).get("quote_date_missing"):
        check_required = dedupe([*check_required, "견적일자 확인 필요"])

    metadata = sanitize_metadata(result.metadata)
    metadata.update(
        {
            "file_name": file_path.name,
            "source_file_hash_short": metadata.get("source_file_hash_short"),
            "ocr_provider": metadata.get("ocr_provider"),
            "parser_provider": "RuleBasedQuoteParserProvider",
        }
    )

    detected_issues = detect_issues(
        file_path=file_path,
        result=result,
        amount_validation=amount_validation,
        delivery_validation=delivery_validation,
        multi_option_detection=multi_option_detection,
        check_required=check_required,
    )

    quoted_tax_amount = raw_matches.get("quoted_tax_amount")
    quote_date = None if raw_matches.get("quote_date_missing") else quote.quote_date
    hardware = _build_hardware_section(quote)

    return {
        "index": index,
        "source_file_name": file_path.name,
        "source_file_ext": file_path.suffix.lower(),
        "source_file_path": relative_path(file_path),
        "status": "success",
        "ocr_status": "success",
        "parser_provider": "RuleBasedQuoteParserProvider",
        "quote_id": quote.quote_id,
        "vendor_name": quote.vendor_name or None,
        "company_location": getattr(quote.vendor_snapshot, "company_location", None),
        "install_location": raw_matches.get("install_location"),
        "vendor_snapshot": build_vendor_snapshot_summary(quote.vendor_snapshot),
        "project_name": quote.project_name or None,
        "quote_date": quote_date,
        "total_supply_price": quote.total_supply_price,
        "tax_amount": quoted_tax_amount if quoted_tax_amount is not None else quote.tax_amount,
        "total_with_vat": quote.total_with_vat,
        "currency": quote.currency,
        "delivery_weeks": quote.delivery_weeks,
        "delivery_basis_raw": quote.delivery_basis_raw or None,
        "warranty_months": quote.warranty_months,
        "payment_terms": raw_matches.get("payment_terms"),
        "special_notes": raw_matches.get("special_notes") or [],
        "quote_validity_terms": raw_matches.get("quote_validity_terms"),
        "installation_included": infer_installation_included(quote),
        "line_item_count": len(quote.line_items),
        "line_items": [line_item_to_dict(item) for item in quote.line_items],
        "hardware": hardware,
        "parser_warnings": list(result.parser_warnings),
        "parser_check_required": check_required,
        "amount_validation": amount_validation,
        "line_item_validation": line_item_validation,
        "delivery_validation": delivery_validation,
        "multi_option_detection": multi_option_detection,
        "category_normalization": category_normalization,
        "project_name_resolution": raw_matches.get("project_name_resolution") or {},
        "parser_quality_notes": dedupe(
            [
                *((result.metadata or {}).get("parser_quality_notes") or []),
                *(raw_matches.get("parser_quality_notes") or []),
            ]
        ),
        "detected_issues": detected_issues,
        "metadata": metadata,
    }


def detect_issues(
    *,
    file_path: Path,
    result,
    amount_validation: dict[str, Any],
    delivery_validation: dict[str, Any],
    multi_option_detection: dict[str, Any],
    check_required: list[str],
) -> list[str]:
    quote = result.quote
    issues: list[str] = []

    if not (quote.vendor_name or "").strip():
        issues.append("vendor_name_missing")
    if _looks_noisy(quote.vendor_name):
        issues.append("vendor_name_noise_included")
    if quote.vendor_snapshot is None:
        issues.append("vendor_name_partner_not_matched")

    if not (quote.project_name or "").strip():
        issues.append("project_name_missing")
    resolution = (result.parser_raw_matches or {}).get("project_name_resolution") or {}
    if resolution.get("source") == "file_name_fallback":
        issues.append("project_name_fallback_used")
    if _looks_noisy(quote.project_name):
        issues.append("project_name_noise_included")
    if not (quote.project_name or "").strip() and not check_required:
        issues.append("project_name_missing_without_check_required")

    if not quote.total_supply_price:
        issues.append("total_supply_price_missing")
    if amount_validation.get("quoted_tax_amount") is None:
        issues.append("tax_amount_missing")
    if quote.total_with_vat is None:
        issues.append("total_with_vat_missing")
    amount_status = amount_validation.get("validation_status")
    if amount_status == "amount_mismatch":
        issues.append("amount_mismatch")
    elif amount_status == "rounding_or_adjustment_possible":
        issues.append("amount_rounding_or_adjustment")
    if amount_validation.get("line_items_difference") not in (None, 0):
        issues.append("line_items_sum_mismatch")
    if amount_validation.get("tax_difference") not in (None, 0):
        issues.append("tax_total_mismatch")

    if not quote.line_items:
        issues.append("line_items_empty")
    for item in quote.line_items:
        if item_name_spec_split_needs_review(item.name):
            issues.append("line_item_name_spec_not_separated")
        if not item.spec_raw and item.name and len(item.name) > 30:
            issues.append("line_item_name_spec_not_separated")
        if _looks_row_number_quantity(item):
            issues.append("row_number_used_as_quantity")
        if amount_status not in {"normal", "rounding_or_adjustment_possible"} and _looks_quantity_unit_price_swapped(item):
            issues.append("quantity_unit_price_swapped")
        if item.total_price is None:
            issues.append("line_item_amount_missing")
        if amount_status != "normal" and _line_item_total_mismatch(item):
            issues.append("line_item_total_mismatch")
        if enum_value(item.category) == "DISPLAY":
            spec = item.spec_parsed or {}
            raw = (item.spec_raw or "").lower()
            searchable = raw
            if not item.spec_raw and any(token in searchable for token in ["해상도", "pitch", "밝기", "nit", "bezel", "크기"]):
                issues.append("display_spec_raw_missing")
            if not (spec.get("screen_size_mm") or spec.get("full_screen_size_mm")) and any(token in searchable for token in ["화면", "screen", "display size", "전체 크기"]):
                issues.append("display_screen_size_missing")
            if not (spec.get("resolution") or spec.get("resolution_type")) and "해상도" in searchable:
                issues.append("display_resolution_missing")
            if not (spec.get("brightness_cd_m2") or spec.get("brightness_nit")) and any(token in searchable for token in ["밝기", "nit", "cd"]):
                issues.append("display_brightness_missing")
            if not (spec.get("pixel_pitch_mm") or spec.get("pitch_mm")) and "pitch" in searchable:
                issues.append("display_pixel_pitch_missing")
            if not (spec.get("power_consumption_kw") or spec.get("power_consumption_w")) and any(token in searchable for token in ["최대전력", "최대소비전력", "전기용량"]):
                issues.append("display_power_consumption_missing")
            if not (spec.get("refresh_rate") or spec.get("refresh_rate_hz")) and "refresh rate" in searchable:
                issues.append("display_refresh_rate_missing")
    if build_line_item_validation(quote):
        issues.append("line_item_arithmetic_mismatch")

    if delivery_validation.get("validation_status") == "missing":
        issues.append("delivery_missing")
    if delivery_validation.get("validation_status") == "discussion_required":
        issues.append("delivery_to_be_discussed")
    if delivery_validation.get("validation_status") == "normalized":
        issues.append("delivery_weeks_not_normalized")

    if quote.warranty_months is None:
        issues.append("warranty_missing")
    if quote.warranty_months is None and _has_warranty_raw(result.ocr_text_preview or ""):
        issues.append("warranty_raw_exists_but_not_parsed")

    for item in quote.line_items:
        if (item.spec_parsed or {}).get("normalized_cost_type") is None:
            issues.append("normalized_cost_type_missing")
            break

    if _is_hyosung_multi_option_file(file_path) and not (result.metadata or {}).get("split_from_multi_option"):
        if not multi_option_detection.get("is_multi_option_possible"):
            issues.append("multi_option_not_detected")
        elif not (result.metadata or {}).get("split_from_multi_option"):
            issues.append("multi_option_detected_but_not_split")
    if (result.metadata or {}).get("split_from_multi_option") and amount_validation.get("line_items_difference") not in (None, 0):
        issues.append("multi_option_split_amount_mismatch")
    if any((item.spec_parsed or {}).get("reconciliation_residual") for item in quote.line_items):
        issues.append("unparsed_residual_present")
    if any((item.spec_parsed or {}).get("spec_sanitization") for item in quote.line_items):
        issues.append("spec_sanitized")
    if not quote_date_available(result):
        issues.append("quote_date_missing")

    return dedupe(issues)


def build_failed_result(index: int, file_path: Path, error: Exception) -> dict[str, Any]:
    return {
        "index": index,
        "source_file_name": file_path.name,
        "source_file_ext": file_path.suffix.lower(),
        "source_file_path": relative_path(file_path),
        "status": "failed",
        "ocr_status": "failed" if "ocr" in str(error).lower() else "unknown",
        "stage": infer_failure_stage(error),
        "error_type": error.__class__.__name__,
        "error_message": str(error),
    }


def build_summary(
    results: list[dict[str, Any]],
    failed_files: list[dict[str, Any]],
    input_file_count: int,
) -> dict[str, Any]:
    issue_counter = Counter()
    for item in results:
        issue_counter.update(item["detected_issues"])
    display_items = [
        line_item
        for result in results
        for line_item in result.get("line_items", [])
        if line_item.get("category") == "DISPLAY"
    ]
    hardware_sections = [result.get("hardware") or {} for result in results]
    hyosung_led = _find_hyosung_split_result(results, 1)
    hyosung_videowall = _find_hyosung_split_result(results, 2)

    files = [
        {
            "source_file_name": item["source_file_name"],
            "status": item["status"],
            "vendor_name": item["vendor_name"],
            "project_name": item["project_name"],
            "total_with_vat": item["total_with_vat"],
            "line_item_count": item["line_item_count"],
            "warranty_months": item["warranty_months"],
            "delivery_weeks": item["delivery_weeks"],
            "detected_issues": item["detected_issues"],
        }
        for item in results
    ]
    files.extend(
        {
            "source_file_name": item["source_file_name"],
            "status": "failed",
            "error_type": item["error_type"],
            "error_message": item["error_message"],
        }
        for item in failed_files
    )

    return {
        "parser_provider": "rule",
        "input_file_count": input_file_count,
        "quote_result_count": len(results),
        "multi_option_split_count": sum(
            1 for item in results if (item.get("metadata") or {}).get("split_from_multi_option")
        ),
        "total_files": input_file_count,
        "success_count": len(results),
        "failed_count": len(failed_files),
        "vendor_name_extracted_count": count_present(results, "vendor_name"),
        "project_name_extracted_count": count_present(results, "project_name"),
        "total_amount_extracted_count": sum(
            1 for item in results if item.get("total_with_vat") or item.get("total_supply_price")
        ),
        "tax_amount_extracted_count": count_present(results, "tax_amount"),
        "quote_date_valid_count": sum(1 for item in results if is_valid_quote_date(item.get("quote_date"))),
        "line_items_extracted_count": sum(1 for item in results if item.get("line_item_count", 0) > 0),
        "warranty_extracted_count": count_present(results, "warranty_months"),
        "delivery_extracted_count": sum(
            1 for item in results if item.get("delivery_weeks") or item.get("delivery_basis_raw")
        ),
        "multi_option_detected_count": sum(
            1 for item in results if (item.get("multi_option_detection") or {}).get("is_multi_option_possible")
        ),
        "amount_validation_normal_count": sum(
            1 for item in results if (item.get("amount_validation") or {}).get("validation_status") == "normal"
        ),
        "amount_rounding_or_adjustment_count": sum(
            1
            for item in results
            if (item.get("amount_validation") or {}).get("validation_status")
            == "rounding_or_adjustment_possible"
        ),
        "amount_mismatch_count": sum(
            1
            for item in results
            if (item.get("amount_validation") or {}).get("validation_status") == "amount_mismatch"
        ),
        "line_item_amount_missing_count": sum(
            1
            for item in results
            for line_item in item.get("line_items", [])
            if line_item.get("supply_amount") is None and line_item.get("total_price") is None
        ),
        "installation_included_count": sum(
            1 for item in results if item.get("installation_included") is True
        ),
        "product_group_detected_count": sum(
            1
            for item in results
            if (item.get("multi_option_detection") or {}).get("product_groups")
        ),
        "display_item_count": len(display_items),
        "display_spec_raw_present_count": sum(1 for item in display_items if item.get("spec_raw")),
        "display_screen_size_extracted_count": sum(
            1
            for item in display_items
            if (item.get("spec_parsed") or {}).get("screen_size_mm")
            or (item.get("spec_parsed") or {}).get("full_screen_size_mm")
        ),
        "display_resolution_extracted_count": sum(
            1
            for item in display_items
            if (item.get("spec_parsed") or {}).get("resolution")
            or (item.get("spec_parsed") or {}).get("resolution_type")
        ),
        "display_brightness_extracted_count": sum(
            1
            for item in display_items
            if (item.get("spec_parsed") or {}).get("brightness_cd_m2")
            or (item.get("spec_parsed") or {}).get("brightness_nit")
        ),
        "display_pixel_pitch_extracted_count": sum(
            1
            for item in display_items
            if (item.get("spec_parsed") or {}).get("pixel_pitch_mm")
            or (item.get("spec_parsed") or {}).get("pitch_mm")
        ),
        "display_power_consumption_extracted_count": sum(
            1
            for item in display_items
            if (item.get("spec_parsed") or {}).get("power_consumption_kw")
            or (item.get("spec_parsed") or {}).get("power_consumption_w")
        ),
        "display_refresh_rate_extracted_count": sum(
            1
            for item in display_items
            if (item.get("spec_parsed") or {}).get("refresh_rate")
            or (item.get("spec_parsed") or {}).get("refresh_rate_hz")
        ),
        "hardware_response_complete_count": sum(
            1
            for hardware in hardware_sections
            if all(hardware.get(key) is not None for key in ["type", "screen_size_mm", "resolution", "brightness_cd_m2"])
        ),
        "hardware_response_partial_count": sum(
            1
            for hardware in hardware_sections
            if hardware.get("type") is not None
            and not all(hardware.get(key) is not None for key in ["screen_size_mm", "resolution", "brightness_cd_m2"])
        ),
        "display_hardware_sanitized_count": sum(
            1
            for item in results
            if "hardware_value_sanitized" in (item.get("detected_issues") or [])
        ),
        "residual_item_count": sum(
            1
            for item in results
            for line_item in item.get("line_items", [])
            if (line_item.get("spec_parsed") or {}).get("reconciliation_residual")
        ),
        "residual_check_required_count": sum(
            1
            for item in results
            if any("개별 품목으로 복원되지" in check for check in item.get("parser_check_required", []))
        ),
        "hyosung_led_residual_count": _count_residual_items(hyosung_led),
        "hyosung_videowall_residual_count": _count_residual_items(hyosung_videowall),
        "hyosung_led_line_item_count": (hyosung_led or {}).get("line_item_count", 0),
        "hyosung_videowall_line_item_count": (hyosung_videowall or {}).get("line_item_count", 0),
        "spec_sanitized_count": sum(
            1
            for item in results
            for line_item in item.get("line_items", [])
            if (line_item.get("spec_parsed") or {}).get("spec_sanitization")
        ),
        "line_item_arithmetic_mismatch_count": sum(
            len(item.get("line_item_validation") or []) for item in results
        ),
        "parser_quality_notes_count": sum(
            len(item.get("parser_quality_notes") or []) for item in results
        ),
        "source_spec_raw_preview_clean_count": sum(
            1
            for item in results
            if (item.get("hardware") or {}).get("source_spec_raw_preview")
            and ":unselected:" not in str(
                (item.get("hardware") or {}).get("source_spec_raw_preview")
            ).lower()
            and "| |" not in str(
                (item.get("hardware") or {}).get("source_spec_raw_preview")
            )
        ),
        "category_reclassified_count": sum(len(item.get("category_normalization") or []) for item in results),
        "quote_date_missing_count": sum(1 for item in results if not item.get("quote_date")),
        "delivery_raw_clean_count": sum(
            1
            for item in results
            if item.get("delivery_basis_raw") and not str(item.get("delivery_basis_raw")).isdigit()
        ),
        "preview_cleaned_count": sum(
            1
            for item in results
            if (item.get("hardware") or {}).get("source_spec_raw_preview")
            and ":unselected:" not in str((item.get("hardware") or {}).get("source_spec_raw_preview")).lower()
        ),
        "source_spec_raw_preview_present_count": sum(
            1 for item in results if (item.get("hardware") or {}).get("source_spec_raw_preview")
        ),
        "azure_ocr_test_status": "success" if results and not failed_files else ("partial" if results else "failed"),
        "api_demo_env_test_status": "run_separately",
        "line_items_sum_normal_count": sum(
            1
            for item in results
            if (item.get("amount_validation") or {}).get("line_items_difference") in (None, 0)
        ),
        "amount_validation_warning_count": sum(
            1
            for item in results
            if (item.get("amount_validation") or {}).get("validation_status")
            not in {"normal", "not_enough_data"}
        ),
        "issue_counts": [
            {"issue": issue, "count": count}
            for issue, count in issue_counter.most_common()
        ],
        "remaining_amount_mismatch_count": sum(
            1
            for item in results
            if (item.get("amount_validation") or {}).get("validation_status")
            not in {"normal", "not_enough_data"}
        ),
        "remaining_detected_issues": [
            {"issue": issue, "count": count}
            for issue, count in issue_counter.most_common()
        ],
        "remaining_detected_issues_top10": [
            {"issue": issue, "count": count}
            for issue, count in issue_counter.most_common(10)
        ],
        "files": files,
        "notes": [
            "QUOTE_PARSER_PROVIDER=rule 기준입니다.",
            "LLM Parser 및 Azure OpenAI Chat 호출은 사용하지 않았습니다.",
            "embedding_vector와 OCR full text는 저장하지 않았습니다.",
        ],
    }


def _find_hyosung_split_result(results: list[dict[str, Any]], option_index: int) -> dict[str, Any] | None:
    for item in results:
        metadata = item.get("metadata") or {}
        if metadata.get("option_index") != option_index:
            continue
        if not metadata.get("split_from_multi_option"):
            continue
        source_name = str(item.get("source_file_name") or "").lower()
        quote_id = str(item.get("quote_id") or "").lower()
        if "itx" in source_name or "itx" in quote_id:
            return item
    return None


def _count_residual_items(result: dict[str, Any] | None) -> int:
    if not result:
        return 0
    return sum(
        1
        for line_item in result.get("line_items", [])
        if (line_item.get("spec_parsed") or {}).get("reconciliation_residual")
    )


def build_issue_report(
    phase: str,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
    failed_files: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Rule Parser Baseline {phase}",
        "",
        f"- parser_provider: {summary['parser_provider']}",
        f"- input_file_count: {summary['input_file_count']}",
        f"- quote_result_count: {summary['quote_result_count']}",
        f"- success_count: {summary['success_count']}",
        f"- failed_count: {summary['failed_count']}",
        "",
        "## Issue Counts",
        "",
    ]
    for item in summary["issue_counts"]:
        lines.append(f"- {item['issue']}: {item['count']}")
    lines.extend(["", "## Files", ""])
    for item in results:
        issues = ", ".join(item["detected_issues"]) or "none"
        lines.append(
            f"- {item['source_file_name']}: vendor={item['vendor_name']}, "
            f"project={item['project_name']}, total={item['total_with_vat']}, "
            f"items={item['line_item_count']}, issues={issues}"
        )
    if failed_files:
        lines.extend(["", "## Failed Files", ""])
        for item in failed_files:
            lines.append(f"- {item['source_file_name']}: {item['error_type']} - {item['error_message']}")
    return "\n".join(lines) + "\n"


def build_before_after_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    metric_keys = [
        "vendor_name_extracted_count",
        "project_name_extracted_count",
        "total_amount_extracted_count",
        "tax_amount_extracted_count",
        "line_items_extracted_count",
        "warranty_extracted_count",
        "delivery_extracted_count",
        "multi_option_detected_count",
        "multi_option_split_count",
        "quote_date_valid_count",
        "line_items_sum_normal_count",
        "amount_validation_normal_count",
        "amount_validation_warning_count",
    ]
    before_files = {item["source_file_name"]: item for item in before.get("files", [])}
    improved_files = []
    remaining_issues = []
    for item in after.get("files", []):
        name = item.get("source_file_name")
        before_issue_count = len((before_files.get(name) or {}).get("detected_issues") or [])
        after_issue_count = len(item.get("detected_issues") or [])
        if after_issue_count < before_issue_count:
            improved_files.append(
                {
                    "source_file_name": name,
                    "before_issue_count": before_issue_count,
                    "after_issue_count": after_issue_count,
                }
            )
        if item.get("detected_issues"):
            remaining_issues.append(
                {
                    "source_file_name": name,
                    "detected_issues": item.get("detected_issues"),
                }
            )
    return {
        "before": {key: before.get(key) for key in metric_keys},
        "after": {key: after.get(key) for key in metric_keys},
        "delta": {key: (after.get(key) or 0) - (before.get(key) or 0) for key in metric_keys},
        "improved_files": improved_files,
        "remaining_issues": remaining_issues,
    }


def line_item_to_dict(item) -> dict[str, Any]:
    return {
        "item_name": item.name,
        "category": enum_value(item.category),
        "quantity": item.quantity,
        "unit": item.unit,
        "unit_price": item.unit_price,
        "supply_amount": item.total_price,
        "total_price": item.total_price,
        "spec_raw": item.spec_raw,
        "spec_parsed": to_jsonable(item.spec_parsed),
    }


def infer_installation_included(quote) -> bool | None:
    install_keywords = [
        "설치",
        "시공",
        "System 설치",
        "시운전",
        "장비 설치",
        "제품 설치비",
        "비디오월 설치",
        "전광판 장비 설치",
        "인수인계",
    ]
    for item in quote.line_items:
        spec = item.spec_parsed or {}
        text = f"{item.name} {item.spec_raw}".lower()
        if enum_value(item.category) == "INSTALL" and item.total_price:
            return True
        if str(spec.get("normalized_cost_type") or "").upper() == "INSTALL" and item.total_price:
            return True
        if item.total_price and any(keyword.lower() in text for keyword in install_keywords):
            return True
    notes = (quote.notes_raw or "").lower()
    if "installation included" in notes:
        return True
    if "installation separate" in notes:
        return False
    return None


def quote_date_available(result) -> bool:
    raw_matches = result.parser_raw_matches or {}
    if raw_matches.get("quote_date_missing"):
        return False
    quote_date = getattr(result.quote, "quote_date", None)
    if not quote_date:
        return False
    return str(quote_date) not in {"1970-01-01"}


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    blocked_keys = {"source_file_path", "embedding_vector", "ocr_text", "ocr_full_text"}
    sanitized = {}
    for key, value in (metadata or {}).items():
        if key in blocked_keys:
            continue
        sanitized[key] = to_jsonable(value)
    if sanitized.get("source_file_hash"):
        sanitized.pop("source_file_hash")
    return sanitized


def _looks_noisy(value: str | None) -> bool:
    text = (value or "").lower()
    return any(token in text for token in ["quotation", "quote", "estimate", "no."])


def _looks_row_number_quantity(item) -> bool:
    text = f"{item.name} {item.spec_raw}".lower()
    if item.quantity not in {2, 2.0, 3, 3.0, 4, 4.0}:
        return False
    if any(token in text for token in ["vx400pro", "controller", "player", "processor", "all-in-one"]):
        return True
    return False


def _looks_quantity_unit_price_swapped(item) -> bool:
    if item.quantity in (None, 0):
        return False
    if item.unit_price is None or item.total_price is None:
        return False
    return item.quantity == 1 and item.unit_price == item.total_price and item.total_price >= 1_000_000


def _line_item_total_mismatch(item) -> bool:
    if item.quantity in (None, 0) or item.unit_price is None or item.total_price is None:
        return False
    return abs(int(item.quantity * item.unit_price) - item.total_price) > 10_000


def _has_warranty_raw(text: str) -> bool:
    lower = (text or "").lower()
    return any(token in lower for token in ["warranty", "a/s", "as"]) or any(
        token in text for token in ["무상", "보증", "유지보수"]
    )


def _is_hyosung_multi_option_file(path: Path) -> bool:
    lower = path.name.lower()
    return "효성" in path.name or "hyosung" in lower or "itx" in lower


def count_present(results: list[dict[str, Any]], key: str) -> int:
    return sum(1 for item in results if item.get(key) not in [None, "", []])


def is_valid_quote_date(value: Any) -> bool:
    if not value:
        return False
    match = re.match(r"(?P<year>\d{4})-\d{2}-\d{2}$", str(value))
    if not match:
        return False
    return 2000 <= int(match.group("year")) <= 2100


def print_file_result(index: int, item: dict[str, Any]) -> None:
    print(f"\n========== Rule Parser Baseline Result {index} ==========")
    for key in [
        "source_file_name",
        "status",
        "vendor_name",
        "project_name",
        "total_supply_price",
        "total_with_vat",
        "line_item_count",
        "delivery_weeks",
        "warranty_months",
    ]:
        print(f"{key}: {item.get(key)}")
    print(f"detected_issues: {item.get('detected_issues')}")


def print_failed_result(index: int, item: dict[str, Any]) -> None:
    print(f"\n========== Rule Parser Baseline Result {index} ==========")
    print(f"source_file_name: {item['source_file_name']}")
    print("status: failed")
    print(f"stage: {item['stage']}")
    print(f"error_type: {item['error_type']}")
    print(f"error_message: {item['error_message']}")


def print_summary(summary: dict[str, Any], detail_path: Path, summary_path: Path, report_path: Path) -> None:
    print("\n========== Rule Parser Baseline Summary ==========")
    for key in [
        "input_file_count",
        "quote_result_count",
        "success_count",
        "failed_count",
        "vendor_name_extracted_count",
        "project_name_extracted_count",
        "total_amount_extracted_count",
        "tax_amount_extracted_count",
        "line_items_extracted_count",
        "warranty_extracted_count",
        "delivery_extracted_count",
        "multi_option_detected_count",
        "multi_option_split_count",
        "quote_date_valid_count",
        "line_items_sum_normal_count",
        "amount_validation_normal_count",
        "amount_validation_warning_count",
    ]:
        print(f"{key}: {summary[key]}")
    print(f"saved_result_path: {relative_path(detail_path)}")
    print(f"saved_summary_path: {relative_path(summary_path)}")
    print(f"saved_report_path: {relative_path(report_path)}")


def print_single_output_summary(summary: dict[str, Any], detail_path: Path) -> None:
    print("\n========== Rule Parser Baseline Single JSON Summary ==========")
    for key in [
        "input_file_count",
        "quote_result_count",
        "success_count",
        "failed_count",
        "vendor_name_extracted_count",
        "line_items_sum_normal_count",
        "amount_validation_normal_count",
    ]:
        print(f"{key}: {summary[key]}")
    print(f"saved_result_path: {relative_path(detail_path)}")


def infer_failure_stage(error: Exception) -> str:
    message = str(error).lower()
    if "ocr" in message:
        return "ocr"
    if "parser" in message:
        return "rule_parser"
    return "unknown"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return relative_path(value)
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


def enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(DATA_DIR.parent.resolve()).as_posix()
    except ValueError:
        return path.name


def dedupe(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if not value:
            continue
        text = str(value)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


if __name__ == "__main__":
    main()
