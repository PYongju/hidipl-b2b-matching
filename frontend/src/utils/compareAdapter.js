import { getStatusUi, normalizeApiStatus } from "./statusMap";

const moneyFormatter = new Intl.NumberFormat("ko-KR");

const sectionDefs = [
  {
    id: "requiredInfo",
    title: "섹션 0 — 회사 정보",
    defaultOpen: true,
    rows: [
      { label: "업력", path: ["company_info", "company_age_years"], format: (value) => withUnit(value, "년") },
      { label: "매출액 (3년 평균)", path: ["vendor_snapshot", "avg_revenue_3yr"] },
      { label: "프로젝트 수 (3년 평균)", path: ["company_info", "avg_project_count_3y"], format: (value) => withUnit(value, "건") },
      { label: "회사 위치", path: ["company_info", "company_location"] },
    ],
  },
  {
    id: "hardware",
    title: "섹션 1 — 하드웨어 품목",
    defaultOpen: true,
    rows: [
      { label: "스크린 크기 (mm)", path: ["hardware", "screen_size_mm"] },
      { label: "해상도", path: ["hardware", "resolution"] },
      { label: "Type", path: ["hardware", "type"] },
      { label: "Pixel Pitch", path: ["hardware", "pixel_pitch"] },
      { label: "소비전력 (kW)", path: ["hardware", "power_consumption_kw"] },
      { label: "밝기 (cd/m2)", path: ["hardware", "brightness_cd_m2"] },
      { label: "Refresh Rate", path: ["hardware", "refresh_rate"] },
      { label: "무상유지보수 기간", path: ["hardware", "free_maintenance_period"] },
    ],
  },
  {
    id: "quoteItems",
    title: "섹션 2 — 견적 항목별 금액",
    defaultOpen: false,
    rows: [
      { label: "디스플레이 H/W", costKey: "display_hw" },
      { label: "시스템 장비", costKey: "system_equipment" },
      { label: "설치 공사비", costKey: "installation" },
      { label: "자재비 (케이블·브라켓 등)", costKey: "materials" },
      { label: "출장비", costKey: "travel_expense" },
      { label: "기타", costKey: "etc" },
      { label: "소프트웨어", costKey: "software" },
      { label: "콘텐츠", costKey: "content" },
    ],
  },
  {
    id: "conditions",
    title: "섹션 3 — 기타 조건",
    defaultOpen: false,
    rows: [
      { label: "납기", path: ["conditions", "delivery"], highlight: "is_fastest_delivery" },
      { label: "제품 보증 기간", path: ["conditions", "warranty_display"], highlight: "is_longest_warranty" },
      { label: "A/S 방식", path: ["conditions", "as_method"] },
      { label: "설치 위치", path: ["conditions", "install_location"] },
      { label: "특이사항", path: ["conditions", "special_notes"], format: formatNotes },
    ],
  },
];

function getFinalScore(row) {
  const score = row.scores?.final_score ?? row.final_score;
  return typeof score === "number" ? score : Number.NEGATIVE_INFINITY;
}

function sortRowsByRanking(rows) {
  return [...rows]
    .map((row, index) => ({ row, index }))
    .sort((left, right) => {
      const scoreDiff = getFinalScore(right.row) - getFinalScore(left.row);
      if (scoreDiff !== 0) return scoreDiff;
      return left.index - right.index;
    })
    .map(({ row }) => row);
}

function createCompareViewModel(response) {
  const rows = sortRowsByRanking(response?.rows ?? []);
  const suppliers = rows.map((row, index) => toSupplier(row, index));
  const sections = sectionDefs.map((section) => ({
    ...section,
    rows: section.rows.map((rowDef) => toComparisonRow(rowDef, rows)),
  }));
  const totalRows = [
    {
      label: "견적 총액",
      cells: rows.reduce((cells, row) => {
        const isUnconfirmed = row.total?.is_confirmed === false;
        cells[getSupplierId(row)] = {
          value: row.total?.display_text ?? formatWon(row.total_with_vat),
          status: isUnconfirmed ? "needsReview" : undefined,
          highlight: !isUnconfirmed && row.highlights?.is_lowest_total_price ? "bestPrice" : undefined,
        };
        return cells;
      }, {}),
    },
  ];

  return { suppliers, comparisonSections: sections, totalRows };
}

function toSupplier(row, index) {
  const id = getSupplierId(row);
  const score = getFinalScore(row);
  const hasScore = score !== Number.NEGATIVE_INFINITY;
  const hasParseIssue = row.rule_warnings?.some((warning) => warning.includes("OCR") || warning.includes("Parser"));
  const isRecommended = Boolean(row.highlights?.is_highest_score);

  return {
    id,
    rank: index + 1,
    name: row.vendor_name || "업체명 확인 필요",
    logo: getLogo(row.vendor_name, index),
    logoClass: ["logo-blue", "logo-purple", "logo-teal", "logo-orange", "logo-gray"][index] ?? "logo-gray",
    fit: hasScore ? Math.round(score) : "-",
    fitClass: hasScore && score >= 80 ? "fit-good" : "fit-warn",
    recommended: isRecommended,
    submitted: hasParseIssue ? "OCR 일부 실패 · 수정 필요" : "제출 완료",
    badges: getSupplierBadges(row),
    strengths: getStrengths(row),
    weakness: getWeakness(row),
    comparison: {},
  };
}

function toComparisonRow(rowDef, rows) {
  return {
    label: rowDef.label,
    cells: rows.reduce((cells, quoteRow) => {
      const cell = rowDef.costKey
        ? getCostCell(quoteRow, rowDef.costKey)
        : getValueCell(quoteRow, rowDef);
      cells[getSupplierId(quoteRow)] = cell;
      return cells;
    }, {}),
  };
}

function getCostCell(row, costKey) {
  const item = row.cost_breakdown?.[costKey];
  const status = normalizeApiStatus(item?.status);
  return {
    value: status === "parseFail" ? "OCR 분석 실패" : formatCostValue(item),
    status,
  };
}

function getValueCell(row, rowDef) {
  const rawValue = getByPath(row, rowDef.path);
  const value = rowDef.format ? rowDef.format(rawValue) : formatEmpty(rawValue);
  const status = getDerivedStatus(value);
  const highlight = rowDef.highlight && row.highlights?.[rowDef.highlight] ? "bestValue" : undefined;
  return { value, status, highlight };
}

function getDerivedStatus(value) {
  if (value === "—" || value === "미기재") return "missing";
  return undefined;
}

function formatCostValue(item) {
  if (!item) return "—";
  if (typeof item.amount === "number") {
    return formatWon(item.amount);
  }
  return getStatusUi(item.status)?.badge ?? item.status ?? "—";
}

function formatWon(value) {
  if (typeof value !== "number") return "—";
  return `₩ ${moneyFormatter.format(value)}`;
}

function formatNotes(value) {
  if (Array.isArray(value)) return value.length > 0 ? value.join(", ") : "—";
  return formatEmpty(value);
}

function formatEmpty(value) {
  if (value === null || value === undefined || value === "") return "—";
  return value;
}

function withUnit(value, unit) {
  if (value === null || value === undefined || value === "") return "—";
  return `${value}${unit}`;
}

function getByPath(source, path) {
  return path.reduce((value, key) => value?.[key], source);
}

function getSupplierId(row) {
  return row.vendor_snapshot?.vendor_id ?? row.quote_id ?? row.vendor_name;
}

function getLogo(name, index) {
  if (!name || name.includes("확인 필요")) return "?";
  return name.slice(0, 1).toUpperCase() || String(index + 1);
}

function getSupplierBadges(row) {
  const badges = [];
  if (row.highlights?.is_lowest_total_price) badges.push("최저가");
  if (row.highlights?.is_fastest_delivery) badges.push("납기 우위");
  if (row.vendor_snapshot?.is_premium_partner) badges.push("프리미엄 파트너");
  if (row.total?.is_confirmed === false) badges.push("총액 미확정");
  return badges.length > 0 ? badges : ["검토 대상"];
}

function getStrengths(row) {
  const strengths = [];
  if (row.highlights?.is_lowest_total_price) strengths.push("가격 경쟁력");
  if (row.highlights?.is_fastest_delivery) strengths.push("납기 우위");
  if (row.highlights?.is_longest_warranty) strengths.push("보증 조건 우수");
  if (row.vendor_snapshot?.is_premium_partner) strengths.push("프리미엄 파트너");
  return strengths.length > 0 ? strengths.join(", ") : "조건 확인 후 판단 가능";
}

function getWeakness(row) {
  const issues = [...(row.check_required ?? []), ...(row.rule_warnings ?? [])];
  return issues.length > 0 ? issues.join(", ") : "-";
}

export { createCompareViewModel };
