const REQUEST_TEXT_FIELD_MAP = {
  "프로젝트명": "projectName",
  "사용 용도": "usage",
  "디스플레이 크기": "displaySize",
  "수량": "quantity",
  "운영 시간": "operationTime",
  "카테고리": "solutions",
  "솔루션": "solutions",
  "예산 상한": "budgetAmount",
  "우선 검토 기준": "reviewPreset",
  "추가 요청사항": "otherConditions",
  "첨부 메모": "attachmentMemo",
};

const EMPTY_REQUEST_VALUES = new Set(["미입력", "없음"]);

export const DISPLAY_SIZE_UNITS = ["mm", "cm", "m", "inch"];

export const SOLUTION_OPTIONS = [
  "LED전광판",
  "비디오월",
  "사이니지",
  "투명디스플레이",
  "빔프로젝터",
  "키오스크",
  "콘텐츠",
];

function parseSolutionsValue(value) {
  const text = normalizeRequestValue(value);
  if (!text) return [];
  return text
    .split(/[,/]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function normalizeProjectSolutions(data) {
  if (Array.isArray(data?.solutions)) {
    return data.solutions.map((item) => String(item).trim()).filter(Boolean);
  }

  const legacyCategory = String(data?.category ?? "").trim();
  if (!legacyCategory) return [];

  return parseSolutionsValue(legacyCategory);
}

export function formatProjectSolutions(data, fallback = "미입력") {
  const solutions = normalizeProjectSolutions(data);
  return solutions.length > 0 ? solutions.join(", ") : fallback;
}

function normalizeRequestValue(value) {
  const trimmed = String(value ?? "").trim();
  if (!trimmed || EMPTY_REQUEST_VALUES.has(trimmed)) {
    return null;
  }
  return trimmed;
}

function inferDisplayUnit(displaySize = "") {
  if (/인치|inch/i.test(displaySize)) return "inch";
  const unitMatch = displaySize.match(/\b(mm|cm|m)\b/i);
  return unitMatch?.[1]?.toLowerCase() || "mm";
}

function parseDisplayInch(displaySize = "") {
  const match = displaySize.match(/([\d,.]+)\s*(?:인치|inch)/i);
  return match?.[1] || "";
}

function parseDisplayDimension(displaySize = "", axis) {
  const axisPattern = axis === "width" ? /W\s*([\d,.]+)/i : /H\s*([\d,.]+)/i;
  const axisMatch = displaySize.match(axisPattern);
  if (axisMatch?.[1]) return axisMatch[1];

  const pairMatch = displaySize.match(/([\d,.]+)\s*(?:x|×)\s*([\d,.]+)/i);
  if (!pairMatch) return "";
  return axis === "width" ? pairMatch[1] : pairMatch[2];
}

function formatInchSize(value = "") {
  const normalized = value.replace(/인치/g, "").trim();
  return normalized ? `${normalized}인치` : "";
}

function formatDimensionSize(width = "", height = "", unit = "mm") {
  const normalizedWidth = width.trim();
  const normalizedHeight = height.trim();
  if (!normalizedWidth && !normalizedHeight) return "";
  if (!normalizedHeight) return `W ${normalizedWidth} ${unit}`;
  if (!normalizedWidth) return `H ${normalizedHeight} ${unit}`;
  return `W ${normalizedWidth} x H ${normalizedHeight} ${unit}`;
}

export function mapDisplaySizeFields(displaySizeText) {
  const displaySize = normalizeRequestValue(displaySizeText);
  if (!displaySize) {
    return {
      displaySize: null,
      displayUnit: null,
      displayWidth: null,
      displayHeight: null,
      displayInch: null,
    };
  }

  const displayUnit = inferDisplayUnit(displaySize);
  if (displayUnit === "inch") {
    const displayInch = parseDisplayInch(displaySize);
    return {
      displaySize: formatInchSize(displayInch) || displaySize,
      displayUnit: "inch",
      displayWidth: "",
      displayHeight: "",
      displayInch,
    };
  }

  const displayWidth = parseDisplayDimension(displaySize, "width");
  const displayHeight = parseDisplayDimension(displaySize, "height");
  return {
    displaySize: formatDimensionSize(displayWidth, displayHeight, displayUnit) || displaySize,
    displayUnit,
    displayWidth,
    displayHeight,
    displayInch: "",
  };
}

export function parseProjectFieldsFromRequestText(requestText) {
  const fields = Object.fromEntries(
    Object.values(REQUEST_TEXT_FIELD_MAP).map((key) => [
      key,
      key === "solutions" ? [] : null,
    ]),
  );

  for (const rawLine of String(requestText ?? "").split(/\r?\n/)) {
    const line = rawLine.trim();
    const colonIndex = line.indexOf(":");
    if (colonIndex < 0) continue;

    const label = line.slice(0, colonIndex).trim();
    const value = line.slice(colonIndex + 1).trim();
    const key = REQUEST_TEXT_FIELD_MAP[label];
    if (!key) continue;

    fields[key] =
      key === "solutions" ? parseSolutionsValue(value) : normalizeRequestValue(value);
  }

  return fields;
}

export function applyParsedRequestTextToProjectData(localData, requestText) {
  const parsed = parseProjectFieldsFromRequestText(requestText);
  const displayFields = mapDisplaySizeFields(parsed.displaySize);

  const merge = (key) => parsed[key] ?? localData?.[key] ?? null;
  const mergeDisplay = (key) => displayFields[key] ?? localData?.[key] ?? null;
  const solutions =
    parsed.solutions?.length > 0
      ? parsed.solutions
      : normalizeProjectSolutions(localData);

  return {
    projectName: merge("projectName"),
    usage: merge("usage"),
    quantity: merge("quantity"),
    operationTime: merge("operationTime"),
    solutions,
    budgetAmount: merge("budgetAmount"),
    reviewPreset: merge("reviewPreset"),
    otherConditions: merge("otherConditions"),
    attachmentMemo: merge("attachmentMemo"),
    displaySize: mergeDisplay("displaySize"),
    displayUnit: mergeDisplay("displayUnit"),
    displayWidth: mergeDisplay("displayWidth"),
    displayHeight: mergeDisplay("displayHeight"),
    displayInch: mergeDisplay("displayInch"),
  };
}

export function buildProjectRequestText(data) {
  const displaySizeText = data.displaySize || "";

  return [
    `프로젝트명: ${data.projectName || "미입력"}`,
    `사용 용도: ${data.usage || "미입력"}`,
    `디스플레이 크기: ${displaySizeText || "미입력"}`,
    `수량: ${data.quantity || "미입력"}`,
    `운영 시간: ${data.operationTime || "미입력"}`,
    `카테고리: ${formatProjectSolutions(data)}`,
    `예산 상한: ${data.budgetAmount || "미입력"}`,
    `현재 단계: ${data.currentStage || "미입력"}`,
    `우선 검토 기준: ${data.reviewPreset || "미입력"}`,
    `추가 요청사항: ${data.otherConditions || "없음"}`,
    `첨부 메모: ${data.attachmentMemo || "없음"}`,
  ].join("\n");
}

function formatBudgetForMessage(value) {
  const normalized = normalizeRequestValue(value);
  return normalized ? `${normalized}원` : null;
}

function buildQuoteReplyChecklist() {
  return [
    "▪ 모델명 / 주요 사양",
    "▪ 수량 기준 단가 및 총액",
    "▪ 설치 / 배송 포함 여부",
    "▪ 예상 납기",
    "▪ A/S 및 보증 조건",
  ];
}

export function buildQuoteRequestMessage(data, options = {}) {
  const vendorName = normalizeRequestValue(options.vendorName) || "[업체명]";
  const solutions = formatProjectSolutions(data, "");
  const lines = [
    ["프로젝트명", normalizeRequestValue(data.projectName)],
    ["고객사", normalizeRequestValue(data.companyName)],
    ["설치 위치", normalizeRequestValue(data.location)],
    ["희망 일정", normalizeRequestValue(data.projectDate)],
    ["사용 용도", normalizeRequestValue(data.usage)],
    ["희망 제품군", solutions || null],
    ["디스플레이 크기", normalizeRequestValue(data.displaySize)],
    ["수량", normalizeRequestValue(data.quantity)],
    ["운영 시간", normalizeRequestValue(data.operationTime)],
    ["예산 범위", formatBudgetForMessage(data.budgetAmount)],
    ["추가 요청사항", normalizeRequestValue(data.otherConditions)],
    ["첨부 / 참고자료", normalizeRequestValue(data.attachmentMemo)],
  ]
    .filter(([, value]) => Boolean(value))
    .map(([label, value]) => `▪ ${label}: ${value}`);

  return [
    `안녕하세요 ${vendorName} 님`,
    "하이디플레이를 통해 견적 요청드립니다.",
    "",
    ...lines,
    "",
    "가능하시다면 아래 항목을 포함해 회신 부탁드립니다.",
    ...buildQuoteReplyChecklist(),
    "",
    "내용 확인 후 견적 회신 부탁드립니다.",
    "감사합니다.",
  ].join("\n");
}

export function buildProjectRequestPayload(data) {
  return {
    company_name: data.companyName || "미입력",
    location: data.location || null,
    deadline: data.projectDate || null,
    request_text: buildProjectRequestText(data),
  };
}

/** @deprecated use normalizeProjectSolutions() */
export function parseCategoryFromRequestText(requestText) {
  return formatProjectSolutions({
    solutions: parseProjectFieldsFromRequestText(requestText).solutions,
  });
}
