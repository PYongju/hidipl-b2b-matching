from enum import StrEnum


class CellStatus(StrEnum):
    NORMAL = "normal"
    INCLUDED = "included"
    SEPARATE = "separate"
    MISSING = "missing"
    TO_BE_DISCUSSED = "to_be_discussed"
    PARSE_FAILED = "parse_failed"
