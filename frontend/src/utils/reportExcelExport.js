import * as XLSX from "xlsx-js-style";
import { applyCompareCellOverride } from "./compareCellOverrides";
import { getStatusUi } from "./statusMap";

const EXCEL_ROW_KIND = {
  TITLE: "title",
  META: "meta",
  SECTION: "section",
  HEADER: "header",
  DATA: "data",
  SUMMARY: "summary",
  SPACER: "spacer",
  EXPLANATION_FIELD: "explanationField",
};

const EXCEL_BORDER = {
  top: { style: "thin", color: { rgb: "E2E8F0" } },
  bottom: { style: "thin", color: { rgb: "E2E8F0" } },
  left: { style: "thin", color: { rgb: "E2E8F0" } },
  right: { style: "thin", color: { rgb: "E2E8F0" } },
};

const EXCEL_STYLES = {
  title: {
    font: { bold: true, sz: 16, color: { rgb: "0F172A" } },
    fill: { fgColor: { rgb: "F1F5F9" } },
    alignment: { vertical: "center", wrapText: true },
  },
  metaLabel: {
    font: { bold: true, sz: 11, color: { rgb: "64748B" } },
    fill: { fgColor: { rgb: "F8FAFC" } },
    alignment: { vertical: "center" },
    border: EXCEL_BORDER,
  },
  metaValue: {
    font: { sz: 11, color: { rgb: "0F172A" } },
    alignment: { vertical: "center", wrapText: true },
    border: EXCEL_BORDER,
  },
  section: {
    font: { bold: true, sz: 13, color: { rgb: "1E3A8A" } },
    fill: { fgColor: { rgb: "E2E8F0" } },
    alignment: { vertical: "center" },
  },
  header: {
    font: { bold: true, sz: 12, color: { rgb: "475569" } },
    fill: { fgColor: { rgb: "F8FAFC" } },
    alignment: { horizontal: "center", vertical: "center", wrapText: true },
    border: EXCEL_BORDER,
  },
  headerRecommended: {
    font: { bold: true, sz: 12, color: { rgb: "1D4ED8" } },
    fill: { fgColor: { rgb: "EFF6FF" } },
    alignment: { horizontal: "center", vertical: "center", wrapText: true },
    border: EXCEL_BORDER,
  },
  dataLabel: {
    font: { bold: true, sz: 12, color: { rgb: "64748B" } },
    fill: { fgColor: { rgb: "F8FAFC" } },
    alignment: { vertical: "top", wrapText: true },
    border: EXCEL_BORDER,
  },
  dataValue: {
    font: { sz: 12, color: { rgb: "0F172A" } },
    alignment: { horizontal: "left", vertical: "top", wrapText: true },
    border: EXCEL_BORDER,
  },
  summary: {
    font: { sz: 12, color: { rgb: "0F172A" } },
    fill: { fgColor: { rgb: "F8FAFC" } },
    alignment: { vertical: "top", wrapText: true },
    border: EXCEL_BORDER,
  },
};

function getQuoteIdFromSupplierId(supplierId) {
  const text = String(supplierId ?? "");
  const match = text.match(/^quote-(.+)-(\d+)$/);
  return match?.[1] ?? text;
}

function splitListText(value) {
  const text = String(value ?? "").trim();
  if (!text || text === "-") return [];

  return text
    .split(/,\s*/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildExportSupplierExplanations(suppliers, supplierExplanations) {
  const byQuoteId = new Map();
  const byVendorName = new Map();

  supplierExplanations.forEach((item) => {
    if (item.quoteId) {
      byQuoteId.set(String(item.quoteId), item);
    }
    if (item.vendorName) {
      byVendorName.set(item.vendorName, item);
    }
  });

  return suppliers.map((supplier, index) => {
    const quoteId = getQuoteIdFromSupplierId(supplier.id);
    const matched =
      byQuoteId.get(quoteId) ??
      byQuoteId.get(String(supplier.id)) ??
      byVendorName.get(supplier.vendorName) ??
      byVendorName.get(supplier.name);

    if (matched) {
      return {
        ...matched,
        displayName: supplier.name,
        recommended: Boolean(supplier.recommended),
        rank: supplier.rank ?? matched.rank ?? index + 1,
        strengthItems:
          matched.strengthItems ??
          splitListText(matched.strengths ?? supplier.strengths),
        weaknessItems:
          matched.weaknessItems ??
          splitListText(matched.weaknesses ?? supplier.weakness),
      };
    }

    return {
      quoteId: supplier.id,
      vendorName: supplier.vendorName ?? supplier.name,
      displayName: supplier.name,
      rank: supplier.rank ?? index + 1,
      recommended: Boolean(supplier.recommended),
      cardSummary: supplier.strengths || "비교 데이터 기준으로 검토가 필요합니다.",
      strengths: supplier.strengths || "-",
      weaknesses: supplier.weakness || "-",
      checkRequired: [],
      strengthItems: splitListText(supplier.strengths),
      weaknessItems: splitListText(supplier.weakness),
    };
  });
}

function getSupplierColumnLabel(supplier) {
  return supplier.recommended ? `${supplier.name} (AI 추천)` : supplier.name;
}

function getColumnLayout(supplierCount) {
  const safeCount = Math.max(supplierCount, 1);
  return {
    labelColumnMax: safeCount > 6 ? 16 : 20,
    valueColumnMax: Math.max(14, Math.min(40, Math.floor(220 / safeCount))),
    wrapWidth: Math.max(18, Math.min(52, Math.floor(240 / safeCount))),
  };
}

function getCellDisplayWidth(value) {
  const text = String(value ?? "");
  const lines = text.split("\n");
  return Math.max(
    ...lines.map((line) => {
      let width = 0;
      for (const char of line) {
        width += char.charCodeAt(0) > 255 ? 2 : 1;
      }
      return width;
    }),
    0,
  );
}

function wrapSingleLine(text, maxWidth) {
  const normalized = String(text ?? "")
    .replace(/\s+/g, " ")
    .trim();
  if (getCellDisplayWidth(normalized) <= maxWidth) return [normalized];

  const lines = [];
  let current = "";

  for (const char of normalized) {
    const next = current + char;
    if (current && getCellDisplayWidth(next) > maxWidth) {
      lines.push(current);
      current = char;
    } else {
      current = next;
    }
  }

  if (current) lines.push(current);
  return lines.length > 0 ? lines : [normalized];
}

function formatWrappedTextForExcel(value, maxWidth = 52) {
  const text = String(value ?? "-")
    .trim()
    .replace(/\s+/g, " ");
  if (!text || text === "-") return text;

  return text
    .split(/(?<=[.!?])\s+/)
    .flatMap((sentence) => wrapSingleLine(sentence.trim(), maxWidth))
    .filter(Boolean)
    .join("\n");
}

function formatExplanationListForExcel(value, maxWidth = 36) {
  const text = String(value ?? "-")
    .trim()
    .replace(/\s+/g, " ");
  if (!text || text === "-") return text;

  const parts = text.includes(", ")
    ? text
        .split(/,\s+/)
        .map((part) => part.trim())
        .filter(Boolean)
    : [text];

  return parts.flatMap((part) => wrapSingleLine(part, maxWidth)).join("\n");
}

function formatExplanationItemsForExcel(items, fallback, maxWidth) {
  if (Array.isArray(items) && items.length > 0) {
    return items
      .flatMap((item) => wrapSingleLine(`• ${item}`, maxWidth))
      .join("\n");
  }

  return formatExplanationListForExcel(fallback, maxWidth);
}

function formatSpecialNotesForExcel(value, maxWidth = 44) {
  const text = String(value ?? "—").trim();
  if (!text || text === "—" || text === "-") return text;

  const parts = text.includes(", ")
    ? text
        .split(/,\s+/)
        .map((part) => part.trim())
        .filter(Boolean)
    : [text];

  return parts.flatMap((part) => wrapSingleLine(part, maxWidth)).join("\n");
}

function formatReadableCompareValue(value, rowLabel, maxWidth = 28) {
  if (rowLabel === "특이사항") {
    return formatSpecialNotesForExcel(value, Math.max(maxWidth, 36));
  }

  const text = String(value ?? "—");
  if (text === "—" || getCellDisplayWidth(text) <= maxWidth) return text;
  return wrapSingleLine(text, maxWidth).join("\n");
}

function formatCompareCellValue(cell, rowLabel, wrapWidth) {
  const rawValue = cell?.value || "—";
  const value = formatReadableCompareValue(rawValue, rowLabel, wrapWidth);
  const badges = [];
  const statusUi = cell?.status ? getStatusUi(cell.status) : null;
  const highlightUi = cell?.highlight ? getStatusUi(cell.highlight) : null;

  if (statusUi?.badge) badges.push(statusUi.badge);
  if (highlightUi?.badge) badges.push(highlightUi.badge);

  if (badges.length === 0) return value;
  if (rowLabel === "특이사항" && value.includes("\n")) {
    return `${value}\n(${badges.join(", ")})`;
  }
  return `${value} (${badges.join(", ")})`;
}

function buildMetaSheetRows({
  projectName,
  projectInfoSummary,
  supplierCount,
  columnCount,
}) {
  const exportedAt = new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "long",
    timeStyle: "short",
  }).format(new Date());

  const rows = [
    ["고객 보고서", ...Array(Math.max(columnCount - 1, 0)).fill("")],
    ["프로젝트", projectName, ...Array(Math.max(columnCount - 2, 0)).fill("")],
    [
      "프로젝트 정보",
      projectInfoSummary || "-",
      ...Array(Math.max(columnCount - 2, 0)).fill(""),
    ],
    [
      "견적서 수",
      `${supplierCount}건`,
      ...Array(Math.max(columnCount - 2, 0)).fill(""),
    ],
    [
      "생성 일시",
      exportedAt,
      ...Array(Math.max(columnCount - 2, 0)).fill(""),
    ],
    [],
  ];
  const rowKinds = [
    EXCEL_ROW_KIND.TITLE,
    EXCEL_ROW_KIND.META,
    EXCEL_ROW_KIND.META,
    EXCEL_ROW_KIND.META,
    EXCEL_ROW_KIND.META,
    EXCEL_ROW_KIND.SPACER,
  ];

  return { rows, rowKinds };
}

function buildExplanationSheetRows(
  overallSummary,
  exportExplanations,
  suppliers,
  wrapWidth,
) {
  const header = [
    "항목",
    ...suppliers.map((supplier) => getSupplierColumnLabel(supplier)),
  ];
  const rows = [
    ["AI 근거 요약", ...Array(Math.max(header.length - 1, 0)).fill("")],
    [
      formatWrappedTextForExcel(overallSummary, wrapWidth + 8),
      ...Array(Math.max(header.length - 1, 0)).fill(""),
    ],
    [],
    ["공급사별 상세", ...Array(Math.max(header.length - 1, 0)).fill("")],
    [...header],
  ];
  const rowKinds = [
    EXCEL_ROW_KIND.SECTION,
    EXCEL_ROW_KIND.SUMMARY,
    EXCEL_ROW_KIND.SPACER,
    EXCEL_ROW_KIND.SECTION,
    EXCEL_ROW_KIND.HEADER,
  ];

  const fieldDefs = [
    {
      label: "요약",
      getValue: (item) =>
        formatWrappedTextForExcel(item.cardSummary, wrapWidth),
    },
    {
      label: "장점",
      getValue: (item) =>
        formatExplanationItemsForExcel(
          item.strengthItems,
          item.strengths,
          wrapWidth,
        ),
    },
    {
      label: "단점",
      getValue: (item) =>
        formatExplanationItemsForExcel(
          item.weaknessItems,
          item.weaknesses,
          wrapWidth,
        ),
    },
    {
      label: "확인 필요",
      getValue: (item) =>
        formatExplanationItemsForExcel(
          Array.isArray(item.checkRequired) ? item.checkRequired : [],
          Array.isArray(item.checkRequired) && item.checkRequired.length > 0
            ? item.checkRequired.join(", ")
            : "-",
          wrapWidth,
        ),
    },
  ];

  fieldDefs.forEach(({ label, getValue }) => {
    rows.push([
      label,
      ...exportExplanations.map((item) => getValue(item)),
    ]);
    rowKinds.push(EXCEL_ROW_KIND.EXPLANATION_FIELD);
  });

  return { rows, rowKinds };
}

function buildCompareSheetRows(
  suppliers,
  comparisonSections,
  totalRows,
  compareCellOverrides,
  wrapWidth,
) {
  const header = ["항목(요구사항)", ...suppliers.map(getSupplierColumnLabel)];
  const rows = [
    ["견적 비교표", ...Array(Math.max(header.length - 1, 0)).fill("")],
  ];
  const rowKinds = [EXCEL_ROW_KIND.SECTION];

  const appendSpacer = () => {
    rows.push([]);
    rowKinds.push(EXCEL_ROW_KIND.SPACER);
  };

  appendSpacer();

  comparisonSections.forEach((section) => {
    rows.push([
      section.title,
      ...Array(Math.max(header.length - 1, 0)).fill(""),
    ]);
    rowKinds.push(EXCEL_ROW_KIND.SECTION);
    rows.push([...header]);
    rowKinds.push(EXCEL_ROW_KIND.HEADER);

    section.rows.forEach((row) => {
      rows.push([
        row.label,
        ...suppliers.map((supplier) =>
          formatCompareCellValue(
            applyCompareCellOverride(
              row.cells?.[supplier.id],
              supplier.id,
              row.label,
              compareCellOverrides,
            ),
            row.label,
            wrapWidth,
          ),
        ),
      ]);
      rowKinds.push(EXCEL_ROW_KIND.DATA);
    });

    appendSpacer();
  });

  if (totalRows.length > 0) {
    rows.push(["합계", ...Array(Math.max(header.length - 1, 0)).fill("")]);
    rowKinds.push(EXCEL_ROW_KIND.SECTION);
    rows.push([...header]);
    rowKinds.push(EXCEL_ROW_KIND.HEADER);

    totalRows.forEach((row) => {
      rows.push([
        row.label,
        ...suppliers.map((supplier) =>
          formatCompareCellValue(
            applyCompareCellOverride(
              row.cells?.[supplier.id],
              supplier.id,
              row.label,
              compareCellOverrides,
            ),
            row.label,
            wrapWidth,
          ),
        ),
      ]);
      rowKinds.push(EXCEL_ROW_KIND.DATA);
    });
  }

  return { rows, rowKinds };
}

function padSheetRow(row, columnCount) {
  const padded = [...row];
  while (padded.length < columnCount) {
    padded.push("");
  }
  return padded;
}

function mergeSheetSections(...sections) {
  const columnCount = Math.max(
    1,
    ...sections.flatMap((section) => section.rows.map((row) => row.length)),
  );
  const rows = [];
  const rowKinds = [];

  sections.forEach((section, sectionIndex) => {
    if (sectionIndex > 0) {
      rows.push(padSheetRow([], columnCount));
      rowKinds.push(EXCEL_ROW_KIND.SPACER);
    }

    section.rows.forEach((row, rowIndex) => {
      rows.push(padSheetRow(row, columnCount));
      rowKinds.push(section.rowKinds[rowIndex]);
    });
  });

  return { rows, rowKinds, columnCount };
}

function getCompareSectionStartIndex(rows) {
  return rows.findIndex((row) => row[0] === "견적 비교표");
}

function applyWrapRowHeights(worksheet, rows, rowKinds) {
  if (!worksheet["!rows"]) worksheet["!rows"] = [];

  const compareSectionStart = getCompareSectionStartIndex(rows);

  rows.forEach((row, rowIndex) => {
    const kind = rowKinds?.[rowIndex];
    const isSpecialNotesRow = row[0] === "특이사항";
    const isCompareSectionRow =
      compareSectionStart >= 0 && rowIndex >= compareSectionStart;
    const isCompareTableRow =
      isCompareSectionRow && kind === EXCEL_ROW_KIND.DATA;
    const isCompareTableHeaderRow =
      isCompareSectionRow &&
      kind === EXCEL_ROW_KIND.HEADER &&
      row[0] === "항목(요구사항)";
    const shouldAdjust =
      isSpecialNotesRow ||
      kind === EXCEL_ROW_KIND.SUMMARY ||
      kind === EXCEL_ROW_KIND.DATA ||
      kind === EXCEL_ROW_KIND.EXPLANATION_FIELD ||
      kind === EXCEL_ROW_KIND.META;

    if (isCompareTableHeaderRow) {
      worksheet["!rows"][rowIndex] = { hpt: 30 };
      return;
    }

    if (!shouldAdjust) return;

    const maxLineCount = row.reduce((max, cellValue) => {
      const lineCount = String(cellValue ?? "").split("\n").length;
      return Math.max(max, lineCount);
    }, 1);

    if (
      maxLineCount <= 1 &&
      (kind === EXCEL_ROW_KIND.DATA ||
        kind === EXCEL_ROW_KIND.EXPLANATION_FIELD) &&
      !isSpecialNotesRow
    ) {
      if (isCompareTableRow) {
        worksheet["!rows"][rowIndex] = { hpt: 28 };
      }
      return;
    }

    const baseMinHeight = kind === EXCEL_ROW_KIND.SUMMARY ? 44 : 28;
    const minHeight = baseMinHeight;

    worksheet["!rows"][rowIndex] = {
      hpt: Math.min(
        Math.max(20 * maxLineCount + 8, minHeight),
        320,
      ),
    };
  });
}

function getRowColumnCount(rows) {
  return rows.reduce((max, row) => Math.max(max, row.length), 1);
}

function getHeaderStyle(suppliers, columnIndex) {
  const supplier = suppliers[columnIndex - 1];
  if (supplier?.recommended) {
    return EXCEL_STYLES.headerRecommended;
  }
  return EXCEL_STYLES.header;
}

function applySheetVisualStyles(worksheet, rows, rowKinds, suppliers) {
  const columnCount = getRowColumnCount(rows);
  const merges = [];

  if (!worksheet["!rows"]) worksheet["!rows"] = [];

  rows.forEach((row, rowIndex) => {
    const rowKind = rowKinds[rowIndex] ?? EXCEL_ROW_KIND.DATA;

    if (rowKind === EXCEL_ROW_KIND.SPACER) {
      worksheet["!rows"][rowIndex] = { hpt: 8 };
      return;
    }

    if (rowKind === EXCEL_ROW_KIND.TITLE) {
      worksheet["!rows"][rowIndex] = { hpt: 38 };
    }

    if (rowKind === EXCEL_ROW_KIND.SECTION) {
      worksheet["!rows"][rowIndex] = { hpt: 26 };
    }

    if (
      rowKind === EXCEL_ROW_KIND.SECTION ||
      rowKind === EXCEL_ROW_KIND.TITLE ||
      rowKind === EXCEL_ROW_KIND.SUMMARY
    ) {
      merges.push({
        s: { r: rowIndex, c: 0 },
        e: { r: rowIndex, c: columnCount - 1 },
      });
    }

    for (let columnIndex = 0; columnIndex < columnCount; columnIndex += 1) {
      const cellRef = XLSX.utils.encode_cell({ r: rowIndex, c: columnIndex });
      if (!worksheet[cellRef]) {
        worksheet[cellRef] = { t: "s", v: "" };
      }

      const cell = worksheet[cellRef];
      if (rowKind === EXCEL_ROW_KIND.TITLE) {
        cell.s = EXCEL_STYLES.title;
        continue;
      }
      if (rowKind === EXCEL_ROW_KIND.SECTION) {
        cell.s = EXCEL_STYLES.section;
        continue;
      }
      if (rowKind === EXCEL_ROW_KIND.HEADER) {
        cell.s = getHeaderStyle(suppliers, columnIndex);
        continue;
      }
      if (rowKind === EXCEL_ROW_KIND.SUMMARY) {
        cell.s = EXCEL_STYLES.summary;
        continue;
      }
      if (rowKind === EXCEL_ROW_KIND.META) {
        cell.s =
          columnIndex === 0 ? EXCEL_STYLES.metaLabel : EXCEL_STYLES.metaValue;
        continue;
      }
      if (
        rowKind === EXCEL_ROW_KIND.DATA ||
        rowKind === EXCEL_ROW_KIND.EXPLANATION_FIELD
      ) {
        const isTotalRow = row[0] === "견적 총액";
        if (columnIndex === 0) {
          cell.s = isTotalRow
            ? {
                ...EXCEL_STYLES.dataLabel,
                font: { ...EXCEL_STYLES.dataLabel.font, bold: true, sz: 13 },
              }
            : EXCEL_STYLES.dataLabel;
        } else {
          cell.s = isTotalRow
            ? {
                ...EXCEL_STYLES.dataValue,
                font: { ...EXCEL_STYLES.dataValue.font, bold: true, sz: 13 },
                fill: { fgColor: { rgb: "F0F9FF" } },
              }
            : EXCEL_STYLES.dataValue;
        }
      }
    }
  });

  if (merges.length > 0) {
    worksheet["!merges"] = merges;
  }
}

function applySheetColumnWidths(worksheet, rows, options = {}) {
  const {
    rowKinds = null,
    labelColumnMax = 20,
    valueColumnMax = 36,
    suppliers = [],
    skipRowKinds = new Set([
      EXCEL_ROW_KIND.TITLE,
      EXCEL_ROW_KIND.SUMMARY,
      EXCEL_ROW_KIND.SECTION,
      EXCEL_ROW_KIND.SPACER,
    ]),
  } = options;
  const columnWidths = [];

  rows.forEach((row, rowIndex) => {
    const kind = rowKinds?.[rowIndex];
    if (kind && skipRowKinds.has(kind)) return;

    row.forEach((cell, columnIndex) => {
      let cellWidth = getCellDisplayWidth(cell) + 2;
      if (columnIndex === 0) {
        cellWidth = Math.min(cellWidth, labelColumnMax);
      } else if (
        kind === EXCEL_ROW_KIND.EXPLANATION_FIELD ||
        kind === EXCEL_ROW_KIND.DATA ||
        kind === EXCEL_ROW_KIND.HEADER
      ) {
        cellWidth = Math.min(cellWidth, valueColumnMax);
      }
      columnWidths[columnIndex] = Math.max(
        columnWidths[columnIndex] ?? 8,
        cellWidth,
      );
    });
  });

  const maxColumnIndex = Math.max(columnWidths.length - 1, 0);
  let uniformWidth = 14;

  if (maxColumnIndex >= 1) {
    const supplierWidths = Array.from(
      { length: maxColumnIndex },
      (_, index) => columnWidths[index + 1] ?? 14,
    );
    uniformWidth = Math.min(
      valueColumnMax,
      Math.max(
        14,
        Math.round(
          supplierWidths.reduce((sum, width) => sum + width, 0) /
            supplierWidths.length,
        ),
      ),
    );
    for (let index = 1; index <= maxColumnIndex; index += 1) {
      columnWidths[index] = uniformWidth;
    }
  }

  worksheet["!cols"] = Array.from(
    { length: maxColumnIndex + 1 },
    (_, index) => {
      if (index === 0) {
        const width = columnWidths[0] ?? 10;
        return { wch: Math.min(Math.max(width, 12), labelColumnMax) };
      }
      const isRecommended = suppliers?.[index - 1]?.recommended;
      const base = uniformWidth;
      const wch = isRecommended
        ? Math.min(base + 4, valueColumnMax)
        : Math.max(base - 2, 14);
      return { wch };
    },
  );
}

function applySheetPageSetup(worksheet, supplierCount) {
  worksheet["!pageSetup"] = {
    orientation: supplierCount > 4 ? "landscape" : "portrait",
    fitToPage: true,
    fitToWidth: 1,
    fitToHeight: 0,
  };
}

function applySheetFreeze(worksheet, freezeRow, freezeColumn) {
  const topLeftCell = XLSX.utils.encode_cell({ r: freezeRow, c: freezeColumn });
  worksheet["!views"] = [
    {
      state: "frozen",
      xSplit: freezeColumn,
      ySplit: freezeRow,
      topLeftCell,
      activeCell: topLeftCell,
    },
  ];
}

function exportToExcel({
  projectName,
  projectInfoSummary = "",
  overallSummary,
  supplierExplanations,
  suppliers,
  comparisonSections,
  totalRows,
  compareCellOverrides = {},
}) {
  const exportExplanations = buildExportSupplierExplanations(
    suppliers,
    supplierExplanations,
  );
  const columnLayout = getColumnLayout(suppliers.length);
  const previewColumnCount = Math.max(suppliers.length + 1, 2);

  const metaSection = buildMetaSheetRows({
    projectName,
    projectInfoSummary,
    supplierCount: suppliers.length,
    columnCount: previewColumnCount,
  });
  const explanationSection = buildExplanationSheetRows(
    overallSummary,
    exportExplanations,
    suppliers,
    columnLayout.wrapWidth,
  );
  const compareSection = buildCompareSheetRows(
    suppliers,
    comparisonSections,
    totalRows,
    compareCellOverrides,
    columnLayout.wrapWidth,
  );
  const { rows, rowKinds } = mergeSheetSections(
    metaSection,
    explanationSection,
    compareSection,
  );

  const workbook = XLSX.utils.book_new();
  const reportSheet = XLSX.utils.aoa_to_sheet(rows);
  applySheetVisualStyles(reportSheet, rows, rowKinds, suppliers);
  applySheetColumnWidths(reportSheet, rows, {
    rowKinds,
    labelColumnMax: columnLayout.labelColumnMax,
    valueColumnMax: columnLayout.valueColumnMax,
    suppliers,
  });
  applyWrapRowHeights(reportSheet, rows, rowKinds);
  applySheetPageSetup(reportSheet, suppliers.length);

  const compareHeaderRowIndex = rows.findIndex(
    (row, index) =>
      rowKinds[index] === EXCEL_ROW_KIND.HEADER && row[0] === "항목(요구사항)",
  );
  if (compareHeaderRowIndex >= 0) {
    applySheetFreeze(reportSheet, compareHeaderRowIndex + 1, 1);
  }

  XLSX.utils.book_append_sheet(workbook, reportSheet, "고객 보고서");

  const safeName = String(projectName || "프로젝트").replace(
    /[\\/:*?"<>|]/g,
    "_",
  );
  XLSX.writeFile(workbook, `${safeName}_고객보고서.xlsx`);
}

export { exportToExcel };
