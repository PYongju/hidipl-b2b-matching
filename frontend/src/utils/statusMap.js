const API_CELL_STATUSES = [
  "normal",
  "included",
  "separate",
  "missing",
  "to_be_discussed",
  "parse_failed",
];

const CELL_STATUS_UI = {
  included: { badge: "포함", tone: "green", cellClass: "included" },
  separate: { badge: "별도 청구", tone: "gray", cellClass: "separate" },
  missing: { badge: "미기재", tone: "gray", cellClass: "missing" },
  toBeDiscussed: { badge: "검토 필요", tone: "orange", cellClass: "toBeDiscussed" },
  parseFail: { badge: "OCR 분석 실패", tone: "red", cellClass: "parseFail" },
};

const HIGHLIGHT_UI = {
  bestPrice: { badge: "최저가", tone: "green", cellClass: "bestPrice" },
  bestValue: { badge: "우위", tone: "green", cellClass: "bestValue" },
};

const REVIEW_STATUS_UI = {
  needsReview: { badge: "검토 필요", tone: "gray", cellClass: "needsReview" },
};

const STATUS_UI = {
  ...CELL_STATUS_UI,
  ...HIGHLIGHT_UI,
  ...REVIEW_STATUS_UI,
};

const API_STATUS_TO_UI_STATUS = {
  normal: undefined,
  included: "included",
  separate: "separate",
  missing: "missing",
  to_be_discussed: "toBeDiscussed",
  parse_failed: "parseFail",
  포함: "included",
  "별도 청구": "separate",
  별도: "separate",
  "확인 필요": "toBeDiscussed",
  "검토 필요": "toBeDiscussed",
  "파싱 실패": "parseFail",
  "OCR 분석 실패": "parseFail",
  "수정 필요": "parseFail",
  미기재: "missing",
  미확정: "needsReview",
};

function normalizeApiStatus(status) {
  return API_STATUS_TO_UI_STATUS[status] ?? status;
}

function getStatusUi(status) {
  return STATUS_UI[normalizeApiStatus(status)] ?? null;
}

export {
  API_CELL_STATUSES,
  CELL_STATUS_UI,
  HIGHLIGHT_UI,
  REVIEW_STATUS_UI,
  STATUS_UI,
  normalizeApiStatus,
  getStatusUi,
};
