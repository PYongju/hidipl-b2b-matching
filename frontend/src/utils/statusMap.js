// spec D1~D5 기준: ok / to_be_discussed / parse_fail / separate / included
const API_CELL_STATUSES = [
  "ok",
  "normal",
  "included",
  "separate",
  "missing",
  "to_be_discussed",
  "parse_fail",
  "parse_failed",
];

// 가이드 §4 상태 단어 정리: 범례(색=의미 1:1)에 셀 배지를 맞춤
// orange=확인 필요, red=수정 필요, gray=검토 필요. 원인(추출 실패)은 note로 분리.
const CELL_STATUS_UI = {
  included: { badge: "포함", tone: "green", cellClass: "included" },
  separate: { badge: "별도 청구", tone: "gray", cellClass: "separate" },
  missing: { badge: "미기재", tone: "gray", cellClass: "missing" },
  editable: { badge: "수정 가능", tone: "gray", cellClass: "editable" },
  toBeDiscussed: { badge: "확인 필요", tone: "orange", cellClass: "toBeDiscussed" },
  parseFail: {
    badge: "수정 필요",
    tone: "red",
    cellClass: "parseFail",
    note: "견적서에서 값을 읽지 못했어요. 원본을 확인한 뒤 입력해 주세요.",
  },
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
  // spec D1~D5
  ok: undefined,
  to_be_discussed: "toBeDiscussed",
  parse_fail: "parseFail",
  separate: "separate",
  included: "included",
  // 이전 호환
  normal: undefined,
  missing: "missing",
  parse_failed: "parseFail",
  포함: "included",
  "별도 청구": "separate",
  별도: "separate",
  "확인 필요": "toBeDiscussed",
  "검토 필요": "needsReview",
  "파싱 실패": "parseFail",
  "OCR 분석 실패": "parseFail",
  "수정 필요": "parseFail",
  미기재: "missing",
  미확인: "needsReview",
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
