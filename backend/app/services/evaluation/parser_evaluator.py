import json
from pathlib import Path
from typing import Any

from services.config import get_settings
from services.ocr.factory import create_ocr_provider
from services.parser.factory import create_parser_provider
from services.parser.schemas import QuoteDocument


CASE_FILE_PATH = Path(__file__).with_name("parser_evaluation_cases.json")

COMPARE_FIELDS = [
    "vendor_name",
    "project_name",
    "total_supply_price",
    "total_with_vat",
    "delivery_weeks",
    "warranty_months",
    "line_item_count",
    "categories",
    "spec_parsed_contains",
]


def main() -> None:
    cases = load_cases(CASE_FILE_PATH)

    if not cases:
        print(f"No parser evaluation cases found: {CASE_FILE_PATH}")
        print("Add cases to parser_evaluation_cases.json and run again.")
        return

    settings = get_settings()
    ocr_provider = create_ocr_provider(settings)
    parser_provider = create_parser_provider("rule")

    total_checks = 0
    passed_checks = 0

    for index, case in enumerate(cases, start=1):
        case_name = str(case.get("case_id") or case.get("name") or f"case_{index}")
        raw_file_path = str(case.get("file_path") or "").strip()
        expected = case.get("expected") or {}

        print(f"\n[{index}] {case_name}")

        if not raw_file_path:
            print("  ERROR: file_path is empty.")
            continue

        file_path = Path(raw_file_path)

        if not file_path.exists():
            print(f"  ERROR: file does not exist: {file_path}")
            print(
                "  Check parser_evaluation_cases.json and use a path relative to the project root or an absolute path."
            )
            continue

        ocr_result = ocr_provider.extract(file_path)
        parsed_result = parser_provider.parse(ocr_result)
        quote_document = get_quote_document(parsed_result)

        case_total, case_passed = print_field_results(expected, quote_document)
        total_checks += case_total
        passed_checks += case_passed

    print_summary(passed_checks, total_checks)


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Parser evaluation case file does not exist: {path}")

    with open(path, encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        return data["cases"]

    raise ValueError(
        "parser_evaluation_cases.json must contain a list or an object with a 'cases' list."
    )


def get_quote_document(parsed_result) -> QuoteDocument:
    return getattr(parsed_result, "quote_document", parsed_result.quote)


def print_field_results(
    expected: dict[str, Any],
    quote_document: QuoteDocument,
) -> tuple[int, int]:
    total = 0
    passed = 0

    for field in COMPARE_FIELDS:
        if field not in expected:
            print(f"  SKIP {field}: expected value is not defined.")
            continue

        total += 1
        expected_value = expected[field]

        if field == "categories":
            ok, actual_value = compare_categories(quote_document, expected_value)
        elif field == "spec_parsed_contains":
            ok, actual_value = compare_spec_parsed_contains(
                quote_document,
                expected_value,
            )
        else:
            actual_value = get_comparable_value(quote_document, field)
            ok = actual_value == expected_value

        if ok:
            passed += 1
            print(f"  PASS {field}: {actual_value!r}")
        else:
            print(
                f"  FAIL {field}: expected={expected_value!r}, actual={actual_value!r}"
            )

    return total, passed


def get_comparable_value(quote_document: QuoteDocument, field: str) -> Any:
    if field == "line_item_count":
        return len(quote_document.line_items)

    return getattr(quote_document, field)


def compare_categories(
    quote_document: QuoteDocument,
    expected_categories: list[str],
) -> tuple[bool, list[str]]:
    actual_categories = [item.category.value for item in quote_document.line_items]
    return actual_categories == expected_categories, actual_categories


def compare_spec_parsed_contains(
    quote_document: QuoteDocument,
    expected: dict[str, list[str]],
) -> tuple[bool, dict[str, list[str]]]:
    actual: dict[str, list[str]] = {}

    for category, expected_keys in expected.items():
        category_items = [
            item
            for item in quote_document.line_items
            if item.category.value == category
        ]
        found_keys = sorted(
            {
                key
                for item in category_items
                for key in item.spec_parsed.keys()
            }
        )
        actual[category] = found_keys

        for key in expected_keys:
            if not any(key in item.spec_parsed for item in category_items):
                return False, actual

    return True, actual


def print_summary(passed: int, total: int) -> None:
    if total == 0:
        print("\nSummary: no comparable expected fields were defined.")
        return

    pass_rate = passed / total * 100
    print(f"\nSummary: {passed}/{total} checks passed ({pass_rate:.1f}%).")


if __name__ == "__main__":
    main()
