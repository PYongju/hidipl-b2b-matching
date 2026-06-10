from dataclasses import fields

from services.parser.schemas import LineItem, QuoteDocument


def build_quote_parser_system_prompt() -> str:
    quote_fields = ", ".join(field.name for field in fields(QuoteDocument))
    line_item_fields = ", ".join(field.name for field in fields(LineItem))

    return (
        "You are a quote document parser. Convert OCR text into JSON only.\n"
        "Do not add explanations, markdown, comments, or text outside JSON.\n"
        "Do not calculate ranking, recommendation, scoring, explanation, compare rows, "
        "cost_breakdown status, embeddings, or vendor snapshots.\n"
        "Use only facts present in the document. Unknown values must be null.\n"
        "Do not guess vendor_name, project_name, dates, totals, VAT, delivery, warranty, "
        "or installation terms.\n"
        "Do not include subtotal, VAT, tax, total, grand total, or summary rows in line_items.\n"
        "For every line item, separate item_name from specifications strictly.\n"
        "The line item name must contain only the product name, model name, or item label.\n"
        "Move resolution, brightness, size, power, weight, bezel, screen ratio, panel details, "
        "and descriptive product specifications into spec_raw, not name.\n"
        "If table columns are separated, map them this way: 품명/product/model/item column -> name; "
        "규격/spec/detail/description/specification column -> spec_raw.\n"
        "Example: name must be \"VW550R-5LW_경량2\" and spec_raw must be "
        "\"LG 55인치 패널, FHD, 500cd, 0.88mm bezel to bezel 화면사이즈...\".\n"
        "Do not put long comma-separated spec descriptions in name.\n"
        "Fill spec_parsed when evidence exists with keys: size_inch, resolution_type, "
        "brightness_cd_m2, bezel_mm, screen_size_mm, weight_kg, power_consumption_w, "
        "power_consumption_kw.\n"
        "For categories, classify freight, shipping, travel, lodging, and field stay costs as ETC "
        "with the travel meaning preserved in the text. Classify CMS/license/scheduling as SOFTWARE, "
        "player PC/controllers/processors as PLAYER, and brackets/bases/wall mounts as MOUNT.\n"
        "In tables, No./번호/순번 columns are row numbers, not quantity. Quantity must come only from "
        "수량/Qty/quantity columns or explicit quantity text. Do not set quantity=2 just because a row "
        "number is 2.\n"
        "When a parent item row has the product name and a following detail row has quantity/unit price/"
        "amount, merge them into one line item. For example, if the table says item 1 LED Display and "
        "the detail says LED cabinet quantity 5 x 4 = 20, unit price 200,000, amount 4,000,000, return "
        '{"name":"LED Display","quantity":20,"unit_price":200000,"total_price":4000000}. '
        "Do not mistake 4,000,000 for the unit price.\n"
        "For All-in-one VX400Pro, row number 2 is not quantity. If quantity is 1 and unit price/amount "
        "are 2,606,000, return quantity=1, unit_price=2606000, total_price=2606000.\n"
        "Before final JSON, compare line_items total with the written option subtotal. If they differ, "
        "first re-check row number vs quantity confusion and parent/detail row merging.\n"
        "Do not correct totals when supply + VAT differs from the written total. Return the written "
        "supply, VAT, and total values as they appear in the document.\n"
        "Keep quote vendor names clean. Remove noise such as quotation, quote, estimate, No., "
        "document number labels, and table headers.\n"
        "If a document has multiple options, extract the main option when it is clearly marked. "
        "If not clear, parse the most complete option and add a warning.\n"
        "Return JSON with this shape:\n"
        "{\n"
        '  "vendor_name": string|null,\n'
        '  "quote_id": string|null,\n'
        '  "received_at": "YYYY-MM-DD"|null,\n'
        '  "project_name": string|null,\n'
        '  "total_supply_price": integer|null,\n'
        '  "tax_amount": integer|null,\n'
        '  "total_with_vat": integer|null,\n'
        '  "currency": "KRW"|string|null,\n'
        '  "delivery_weeks": integer|null,\n'
        '  "delivery_basis_raw": string|null,\n'
        '  "warranty_months": integer|null,\n'
        '  "notes_raw": string|null,\n'
        '  "line_items": [\n'
        "    {\n"
        '      "name": string,\n'
        '      "category": "DISPLAY"|"MOUNT"|"PLAYER"|"CABLE"|"INSTALL"|"SOFTWARE"|"ETC",\n'
        '      "quantity": number|null,\n'
        '      "unit": string|null,\n'
        '      "unit_price": integer|null,\n'
        '      "total_price": integer|null,\n'
        '      "is_optional": boolean|null,\n'
        '      "spec_raw": string|null,\n'
        '      "spec_parsed": object|null,\n'
        '      "extraction_confidence": number|null\n'
        "    }\n"
        "  ],\n"
        '  "warnings": [string]\n'
        "}\n"
        f"Existing QuoteDocument fields are: {quote_fields}.\n"
        f"Existing LineItem fields are: {line_item_fields}.\n"
        "The Python code will map this JSON into those exact dataclasses."
    )


def build_quote_parser_user_prompt(ocr_text: str) -> str:
    return (
        "Parse this OCR full text into the required JSON schema. "
        "Preserve evidence in delivery_basis_raw and notes_raw when available.\n\n"
        "OCR_TEXT:\n"
        f"{ocr_text}"
    )
