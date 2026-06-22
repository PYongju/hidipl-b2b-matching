import { useEffect, useMemo, useRef, useState } from "react";
import AutoSaveStatus from "../components/AutoSaveStatus";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import useCompareResult from "../hooks/useCompareResult";
import useExplanationResult from "../hooks/useExplanationResult";
import { confirmAdminProject, saveInternalNotes, updateProject } from "../api/apiClient";
import { getStatusUi } from "../utils/statusMap";
import {
  applyCompareCellOverride,
  getCompareCellOverrideKey,
  resolveCompareCellOverrides,
  saveCompareCellOverridesToStorage,
} from "../utils/compareCellOverrides";
import { saveReviewMemoToStorage as persistReviewMemoToStorage } from "../utils/reviewMemoStorage";
import { buildProjectInfoSummary } from "../utils/projectRequestText";
import { exportToExcel } from "../utils/reportExcelExport";
import { withObjectParticle, withSubjectParticle } from "../utils/josa";
import {
  AI_COMPARE_NOTICE,
  AI_FALLBACK_NOTICE,
  FINAL_SELECTION,
  getUserDisplayName,
  REVIEW_COMPLETE,
  USER,
} from "../constants/uiText";

const VISIBLE_SUPPLIER_COUNT = 3;

function isSelectionFinalizedStatus(workflowStatus) {
  return (
    workflowStatus === "완료" ||
    workflowStatus === "컨펌 요청" ||
    workflowStatus === "확정 완료"
  );
}

function isAdminSelectionComplete(workflowStatus) {
  return workflowStatus === "완료" || workflowStatus === "확정 완료";
}

/** 최종 선정 라디오와 동일한 견적서 업체 표시명 (회사명 + N안) */
function resolveSelectedSupplierLabel(supplier, fallbackVendor = "") {
  return (
    supplier?.name?.trim() ||
    supplier?.vendorName?.trim() ||
    fallbackVendor.trim() ||
    ""
  );
}

function buildFinalSelectionConfirmMessage(supplier, fallbackVendor = "") {
  const vendorLabel = resolveSelectedSupplierLabel(supplier, fallbackVendor);
  if (!vendorLabel) return FINAL_SELECTION.dialogMessage;
  return `${withObjectParticle(vendorLabel)} 최종 선정 업체로 확정하시겠습니까?`;
}

function buildReviewCompleteConfirmMessage(supplier, fallbackVendor = "") {
  const vendorLabel = resolveSelectedSupplierLabel(supplier, fallbackVendor);
  if (!vendorLabel) return REVIEW_COMPLETE.dialogMessage;
  return `${withObjectParticle(vendorLabel)} 최종 선정하여 결재를 요청할까요?`;
}

/** 미기재로 간주하는 셀 표시값 */
const MISSING_COMPARE_CELL_VALUES = ["-", "미기재", "—"];

/** 비교 테이블 인라인 편집 제외 행 — 제외할 행이 생기면 이 배열만 수정 */
const NON_EDITABLE_COMPARE_ROW_LABELS = [];

function isMissingCompareCellValue(value) {
  if (typeof value !== "string") return false;
  const displayValue = value.trim() || "—";
  return MISSING_COMPARE_CELL_VALUES.includes(displayValue);
}

function isMissingCompareCell(cell) {
  if (!cell) return true;
  return (
    cell.status === "missing" ||
    cell.value === "미기재" ||
    isMissingCompareCellValue(cell.value)
  );
}

function getCompareCellDisplayValue(cell, rowLabel) {
  if (rowLabel === "특이사항") {
    const value = cell?.value;
    if (!value || isMissingCompareCellValue(value)) return "";
    return value;
  }

  let value;
  if (isMissingCompareCell(cell)) {
    value = "-";
  } else {
    value = cell?.value || "-";
  }

  return stripVatFromAmountDisplay(value);
}

function stripVatFromAmountDisplay(value) {
  if (typeof value !== "string" || !/VAT\s*(미포함|포함)/i.test(value)) {
    return value;
  }

  const stripped = value
    .replace(/\s*[\r\n]+\s*\(?\s*VAT\s*미포함\s*\)?/gi, "")
    .replace(/\s*[\r\n]+\s*\(?\s*VAT\s*포함\s*\)?/gi, "")
    .replace(/\s*\(?\s*VAT\s*미포함\s*\)?/gi, "")
    .replace(/\s*\(?\s*VAT\s*포함\s*\)?/gi, "")
    .trim();

  return stripped || "-";
}

function isEditableMissingCompareCell(rowLabel, cell) {
  if (NON_EDITABLE_COMPARE_ROW_LABELS.includes(rowLabel)) return false;
  if (rowLabel === "특이사항" && cell?.status === "editable") return true;
  if (cell?.status === "missing" || cell?.status === "editable") return true;
  return isMissingCompareCellValue(cell?.value);
}

function SupplierPager({
  canNavigate,
  canGoPrev,
  canGoNext,
  onPrev,
  onNext,
  startIndex,
  total,
}) {
  if (!canNavigate) return null;

  const visibleEnd = Math.min(startIndex + VISIBLE_SUPPLIER_COUNT, total);

  return (
    <div className="supplier-pager">
      <button
        aria-label="이전 견적서 보기"
        className="supplier-pager-btn"
        disabled={!canGoPrev}
        onClick={onPrev}
        type="button"
      >
        <i aria-hidden="true" className="fa-solid fa-angle-left" />
      </button>
      <span className="supplier-pager-count">
        {startIndex + 1}–{visibleEnd} / {total}
      </span>
      <button
        aria-label="다음 견적서 보기"
        className="supplier-pager-btn"
        disabled={!canGoNext}
        onClick={onNext}
        type="button"
      >
        <i aria-hidden="true" className="fa-solid fa-angle-right" />
      </button>
    </div>
  );
}

export default function DashboardPage({
  projectData,
  onBack,
  onGoProjects,
  onProjectDataChange,
  userRole = "member",
}) {
  const [selectedSupplierId, setSelectedSupplierId] = useState(
    projectData.selectedSupplierId ?? "",
  );
  const projectId =
    projectData.projectId || projectData.projectApiId || "프로젝트";
  const projectTitle =
    projectData.projectName?.trim() || `프로젝트 ${projectId}`;
  const {
    compareErrorMessage,
    compareState,
    comparisonSections,
    suppliers,
    totalRows,
  } = useCompareResult(projectData);
  const {
    explanationState,
    isFallback: explanationIsFallback,
    overallSummary,
    supplierExplanations,
  } = useExplanationResult(projectData, suppliers);
  const explanationByQuote = useMemo(
    () => new Map(supplierExplanations.map((item) => [item.quoteId, item])),
    [supplierExplanations],
  );
  const explanationByVendor = useMemo(
    () => new Map(supplierExplanations.map((item) => [item.vendorName, item])),
    [supplierExplanations],
  );
  const defaultOpenSections = useMemo(
    () =>
      comparisonSections.reduce(
        (sections, section) => ({
          ...sections,
          [section.id]: section.defaultOpen,
        }),
        { total: true },
      ),
    [comparisonSections],
  );
  const [openSections, setOpenSections] = useState(defaultOpenSections);
  const [confirmAction, setConfirmAction] = useState(null);
  const [backConfirmOpen, setBackConfirmOpen] = useState(false);
  const [permissionDeniedOpen, setPermissionDeniedOpen] = useState(false);
  const [successFeedback, setSuccessFeedback] = useState(FINAL_SELECTION);
  const [confirmInProgress, setConfirmInProgress] = useState(false);
  const [selectionFinalized, setSelectionFinalized] = useState(
    isSelectionFinalizedStatus(projectData.workflowStatus),
  );
  const [toastVisible, setToastVisible] = useState(false);
  const [followupVisible, setFollowupVisible] = useState(false);
  const [prosOpen, setProsOpen] = useState(true);
  const maxMemoLength = 1000;
  const [reviewMemo, setReviewMemo] = useState(projectData.reviewMemo ?? "");
  const [draftMemo, setDraftMemo] = useState(projectData.reviewMemo ?? "");
  const [isMemoEditing, setIsMemoEditing] = useState(false);
  const [isMemoSaving, setIsMemoSaving] = useState(false);
  const [autoSaveStatus, setAutoSaveStatus] = useState("idle");
  const autoSaveStatusTimerRef = useRef(null);
  const [supplierStartIndex, setSupplierStartIndex] = useState(0);
  const [compareCellOverrides, setCompareCellOverrides] = useState(() =>
    resolveCompareCellOverrides(projectData),
  );
  const supplierCount = suppliers.length;
  const canNavigateSuppliers = supplierCount > VISIBLE_SUPPLIER_COUNT;
  const maxSupplierStartIndex =
    supplierCount <= VISIBLE_SUPPLIER_COUNT
      ? 0
      : Math.floor((supplierCount - 1) / VISIBLE_SUPPLIER_COUNT) *
        VISIBLE_SUPPLIER_COUNT;
  const visibleSuppliers = useMemo(
    () =>
      suppliers.slice(
        supplierStartIndex,
        supplierStartIndex + VISIBLE_SUPPLIER_COUNT,
      ),
    [suppliers, supplierStartIndex],
  );
  const selectableSuppliers = suppliers;
  const selectedSupplier = useMemo(
    () =>
      selectableSuppliers.find(
        (supplier) => supplier.id === selectedSupplierId,
      ) ?? null,
    [selectableSuppliers, selectedSupplierId],
  );
  const canGoPrevSuppliers = canNavigateSuppliers && supplierStartIndex > 0;
  const canGoNextSuppliers =
    canNavigateSuppliers && supplierStartIndex < maxSupplierStartIndex;

  const showAutoSaveStatus = (status) => {
    if (autoSaveStatusTimerRef.current) {
      window.clearTimeout(autoSaveStatusTimerRef.current);
      autoSaveStatusTimerRef.current = null;
    }

    setAutoSaveStatus(status);

    if (status === "saved" || status === "error") {
      autoSaveStatusTimerRef.current = window.setTimeout(() => {
        setAutoSaveStatus("idle");
        autoSaveStatusTimerRef.current = null;
      }, status === "saved" ? 1800 : 3000);
    }
  };

  useEffect(() => {
    setSupplierStartIndex(0);
  }, [supplierCount]);

  useEffect(() => {
    if (!selectableSuppliers.length) return;
    setSelectedSupplierId((current) =>
      current && selectableSuppliers.some((supplier) => supplier.id === current)
        ? current
        : projectData.selectedSupplierId &&
            selectableSuppliers.some(
              (supplier) => supplier.id === projectData.selectedSupplierId,
            )
          ? projectData.selectedSupplierId
          : selectableSuppliers[0].id,
    );
  }, [projectData.selectedSupplierId, selectableSuppliers]);

  useEffect(() => {
    setSelectionFinalized(isSelectionFinalizedStatus(projectData.workflowStatus));
  }, [projectData.workflowStatus]);

  useEffect(() => {
    const memo = projectData.reviewMemo ?? "";
    setReviewMemo(memo);
    setDraftMemo(memo);
    setIsMemoEditing(false);
  }, [projectId, projectData.reviewMemo]);

  useEffect(() => {
    setCompareCellOverrides(resolveCompareCellOverrides(projectData));
  }, [projectData.projectApiId, projectData.projectId]);

  useEffect(
    () => () => {
      if (autoSaveStatusTimerRef.current) {
        window.clearTimeout(autoSaveStatusTimerRef.current);
      }
    },
    [],
  );

  const goPrevSuppliers = () => {
    setSupplierStartIndex((current) =>
      Math.max(0, current - VISIBLE_SUPPLIER_COUNT),
    );
  };

  const goNextSuppliers = () => {
    setSupplierStartIndex((current) =>
      Math.min(maxSupplierStartIndex, current + VISIBLE_SUPPLIER_COUNT),
    );
  };

  const supplierPagerProps = {
    canGoNext: canGoNextSuppliers,
    canGoPrev: canGoPrevSuppliers,
    canNavigate: canNavigateSuppliers,
    onNext: goNextSuppliers,
    onPrev: goPrevSuppliers,
    startIndex: supplierStartIndex,
    total: supplierCount,
  };

  const getSupplierCardSummary = (supplier) => {
    if (explanationState === "loading") {
      return "AI 근거 요약을 불러오고 있어요.";
    }

    return (
      explanationByQuote.get(supplier.id)?.cardSummary ??
      explanationByVendor.get(supplier.vendorName ?? supplier.name)
        ?.cardSummary ??
      ""
    );
  };

  const toggleSection = (sectionId) => {
    setOpenSections((current) => ({
      ...current,
      [sectionId]: !(
        current[sectionId] ??
        defaultOpenSections[sectionId] ??
        false
      ),
    }));
  };

  const getStatusBadge = (status) => {
    const statusUi = getStatusUi(status);
    if (!statusUi) return null;
    // parseFail 등 원인 보조문구(note)가 있으면 배지 툴팁으로 노출 (가이드 §4 #2)
    return (
      <Badge tone={statusUi.tone} title={statusUi.note}>
        {statusUi.badge}
      </Badge>
    );
  };

  const getSupplierCostBadge = (supplier, key, label) => {
    const row = comparisonSections
      .flatMap((section) => section.rows)
      .find((item) => item.label === key);
    const cell = row?.cells?.[supplier.id];
    const status = cell?.status;
    const value = cell?.value || "";

    if (status === "included" || value.includes("포함")) {
      return (
        <Badge tone="green" key={key}>
          {label} 포함
        </Badge>
      );
    }
    if (status === "separate" || value.includes("별도")) {
      return (
        <Badge tone="gray" key={key}>
          {label} 별도
        </Badge>
      );
    }
    if (status === "parseFail") {
      return (
        <Badge tone="red" key={key}>
          {label} 수정 필요
        </Badge>
      );
    }
    if (
      status === "toBeDiscussed" ||
      value.includes("검토") ||
      value.includes("확인")
    ) {
      return (
        <Badge tone="orange" key={key}>
          {label} 확인 필요
        </Badge>
      );
    }
    return null;
  };

  const renderCompareCell = (supplier, row) => {
    const overrideKey = getCompareCellOverrideKey(supplier.id, row.label);
    const baseCell = row.cells?.[supplier.id] ?? { value: "—" };
    const overriddenValue = compareCellOverrides[overrideKey];
    const cell =
      overriddenValue !== undefined
        ? { ...baseCell, value: overriddenValue, status: undefined, highlight: undefined }
        : baseCell;
    const status = cell.status;
    const highlight = cell.highlight;
    const displayValue = getCompareCellDisplayValue(cell, row.label);
    const canEditCompareCell =
      overriddenValue !== undefined ||
      isEditableMissingCompareCell(row.label, baseCell);

    if (canEditCompareCell) {
      return (
        <EditableCompareCell
          cell={{ ...cell, value: displayValue }}
          onSave={(nextValue) =>
            handleCompareCellSave(supplier, row.label, nextValue)
          }
          rowLabel={row.label}
          statusBadge={
            overriddenValue === undefined
              ? getStatusBadge(
                  row.label === "특이사항"
                    ? "editable"
                    : (baseCell.status ?? "missing"),
                )
              : null
          }
        />
      );
    }

    const cellClasses = [
      "compare-cell",
      status ? `cell-${status}` : "",
      row.label === "출장비" &&
      displayValue === "확인 필요" &&
      overriddenValue === undefined
        ? "cell-toBeDiscussed"
        : "",
      highlight ? `cell-${highlight}` : "",
    ]
      .filter(Boolean)
      .join(" ");

    return (
      <div className={cellClasses}>
        <span className={highlight === "bestPrice" ? "price-best" : ""}>
          {displayValue}
        </span>
        {getStatusBadge(status)}
        {getStatusBadge(highlight)}
      </div>
    );
  };

  const handleCompareCellSave = async (supplier, rowLabel, nextValue) => {
    const overrideKey = getCompareCellOverrideKey(supplier.id, rowLabel);
    const previousOverrides = compareCellOverrides;
    const nextOverrides = {
      ...previousOverrides,
      [overrideKey]: nextValue,
    };
    const apiProjectId = projectData.projectApiId ?? projectData.projectId;

    showAutoSaveStatus("saving");
    setCompareCellOverrides(nextOverrides);

    try {
      onProjectDataChange?.((current) => ({
        ...current,
        compareCellOverrides: nextOverrides,
        lastScreen: "dashboard",
      }));

      if (apiProjectId) {
        saveCompareCellOverridesToStorage(apiProjectId, nextOverrides);
      }
      showAutoSaveStatus("saved");
    } catch (error) {
      console.error("비교 테이블 셀 저장 실패:", error);
      setCompareCellOverrides(previousOverrides);
      showAutoSaveStatus("error");
      throw error;
    }
  };

  const startMemoEdit = () => {
    if (isMemoSaving) return;
    setDraftMemo(reviewMemo);
    setIsMemoEditing(true);
  };

  const saveMemo = async () => {
    if (isMemoSaving) return;

    const nextMemo = draftMemo;
    const previousMemo = reviewMemo;
    const memoProjectId = projectData.projectApiId ?? projectData.projectId;

    setIsMemoSaving(true);
    showAutoSaveStatus("saving");
    setReviewMemo(nextMemo);
    onProjectDataChange?.((current) => ({
      ...current,
      reviewMemo: nextMemo,
      lastScreen: "dashboard",
    }));

    try {
      if (memoProjectId) {
        await saveInternalNotes(memoProjectId, {
          screen: "dashboard",
          note: nextMemo,
        });
        persistReviewMemoToStorage(memoProjectId, nextMemo);
      }
      setIsMemoEditing(false);
      showAutoSaveStatus("saved");
    } catch (error) {
      console.error("검토 메모 저장 실패:", error);
      setReviewMemo(previousMemo);
      setDraftMemo(nextMemo);
      onProjectDataChange?.((current) => ({
        ...current,
        reviewMemo: previousMemo,
      }));
      showAutoSaveStatus("error");
    } finally {
      setIsMemoSaving(false);
    }
  };

  const memoValue = isMemoEditing ? draftMemo : reviewMemo;

  const canExportReport = explanationState === "ready";
  const projectInfoSummary = buildProjectInfoSummary(projectData);
  const isMember = userRole !== "admin";
  const workflowStatus = projectData.workflowStatus ?? "";
  const isApprovalPending = workflowStatus === "컨펌 요청";
  const isAdminSelectionDone = isAdminSelectionComplete(workflowStatus);
  const confirmCopy =
    confirmAction === "review-complete" ? REVIEW_COMPLETE : FINAL_SELECTION;
  const finalSelectionConfirmMessage = buildFinalSelectionConfirmMessage(
    selectedSupplier,
    projectData.selectedVendor,
  );
  const reviewCompleteConfirmMessage = buildReviewCompleteConfirmMessage(
    selectedSupplier,
    projectData.selectedVendor,
  );

  const submitApprovalRequest = async () => {
    const apiProjectId = projectData.projectApiId ?? projectData.projectId;
    if (!apiProjectId) return;

    setConfirmInProgress(true);
    try {
      await updateProject(apiProjectId, { workflow_status: "컨펌 요청" });
      setConfirmAction(null);
      setSuccessFeedback(REVIEW_COMPLETE);
      setSelectionFinalized(true);
      setFollowupVisible(true);
      setToastVisible(true);
      onProjectDataChange?.(
        (current) => ({
          ...current,
          currentStage: "결재 요청",
          selectedSupplierId,
          selectedVendor: selectedSupplier?.name ?? "",
          workflowStatus: "컨펌 요청",
          lastScreen: "dashboard",
        }),
        {
          status: "컨펌 요청",
          statusTone: "purple",
          desc: "결재 요청",
        },
      );
      window.setTimeout(() => setToastVisible(false), 3200);
    } catch (error) {
      console.error("결재 요청 실패:", error);
    } finally {
      setConfirmInProgress(false);
    }
  };

  const submitAdminFinalSelection = async () => {
    const apiProjectId = projectData.projectApiId ?? projectData.projectId;
    if (!apiProjectId) return;

    setConfirmInProgress(true);
    try {
      await confirmAdminProject(apiProjectId);
      setConfirmAction(null);
      setSuccessFeedback(FINAL_SELECTION);
      setSelectionFinalized(true);
      setFollowupVisible(true);
      setToastVisible(true);
      onProjectDataChange?.(
        (current) => ({
          ...current,
          currentStage: "확정 완료",
          selectedSupplierId,
          selectedVendor: selectedSupplier?.name ?? "",
          workflowStatus: "확정 완료",
          lastScreen: "dashboard",
        }),
        {
          status: "확정 완료",
          statusTone: "green",
          desc: "확정 완료",
        },
      );
      window.setTimeout(() => setToastVisible(false), 3200);
    } catch (error) {
      console.error("최종 선정 실패:", error);
    } finally {
      setConfirmInProgress(false);
    }
  };

  const handleConfirmSubmit = async () => {
    if (confirmAction === "admin-approve") {
      await submitAdminFinalSelection();
      return;
    }
    await submitApprovalRequest();
  };

  const handleExportToExcel = () => {
    exportToExcel({
      projectName:
        projectData.projectName || projectData.companyName || projectId,
      projectInfoSummary,
      overallSummary,
      supplierExplanations,
      suppliers,
      comparisonSections,
      totalRows,
      compareCellOverrides,
    });
  };

  return (
    <div className="flow-page dashboard-page">
      <FlowTopbar
        onHome={onGoProjects}
        trail={`프로젝트 목록 > 프로젝트 ${projectTitle}`}
        action={
          <>
            <div className="topbar-actions">
              <button
                className="button action-secondary"
                onClick={onGoProjects}
                type="button"
              >
                프로젝트 목록
              </button>
              <button
                className="button action-secondary"
                disabled
                title="상태는 화면 진행에 따라 자동으로 반영돼요."
                type="button"
              >
                {isAdminSelectionDone
                  ? "확정 완료"
                  : selectionFinalized
                    ? "검토 완료"
                    : "검토 진행 중"}
              </button>
            </div>
            <AutoSaveStatus status={autoSaveStatus} />
            <div className="avatar" />
            <div className="user-name">
              <b>{getUserDisplayName(userRole)}</b>
              <small>{USER.team}</small>
            </div>
          </>
        }
      />

      <main className="dashboard">
        <section className="project-head">
          <div className="project-title">
            <div className="project-title-edit-shell">
              <div className="project-title-display">
                <h1 className="project-title-with-meta">
                  <span className="project-title-name">
                    {projectData.projectName || `프로젝트 ${projectId}`}
                  </span>
                  {projectInfoSummary ? (
                    <>
                      <span
                        aria-hidden="true"
                        className="project-title-inline-divider"
                      >
                        {" "}
                        ·{" "}
                      </span>
                      <span className="project-title-inline-meta">
                        {projectInfoSummary}
                      </span>
                    </>
                  ) : null}
                </h1>
                <Badge className="project-title-status-badge">
                  {isAdminSelectionDone
                    ? "확정 완료"
                    : selectionFinalized
                      ? "검토 완료"
                      : "견적 검토"}
                </Badge>
              </div>
            </div>
          </div>
        </section>

        {compareState === "loading" && <CompareLoadingState />}

        {compareState === "error" && (
          <CompareErrorState
            message={compareErrorMessage}
            onGoProjects={onGoProjects}
            onRetry={() => window.location.reload()}
          />
        )}

        {compareState === "ready" && (
          <div className="content-grid">
            <div className="main-column">
              <section className="panel supplier-panel">
                <div className="requirements-section-title partner-section-header">
                  <div>
                    <div className="partner-section-header-row">
                      <div className="partner-section-title-with-badge">
                        <h2>공급사 매칭 현황</h2>
                        <span className="partner-section-count">
                          {supplierCount}/{supplierCount}
                        </span>
                      </div>
                      <div className="dashboard-section-header-actions">
                        <SupplierPager {...supplierPagerProps} />
                      </div>
                    </div>
                  </div>
                </div>
                <div className="supplier-grid">
                  {visibleSuppliers.map((supplier) => {
                    const cardSummary = getSupplierCardSummary(supplier);

                    return (
                      <article
                        className={`supplier-card ${supplier.recommended ? "recommended" : ""}`}
                        key={supplier.id}
                      >
                        {supplier.recommended ? (
                          <div className="supplier-ai-badge">
                            <Badge>AI 추천</Badge>
                          </div>
                        ) : null}
                        <div className="supplier-row">
                          <div className="supplier-name">
                            <span className="rank">{supplier.rank}</span>
                            <b>{supplier.name}</b>
                          </div>
                          <div className="fit">
                            적합도{" "}
                            <b className={supplier.fitClass}>{supplier.fit}%</b>
                          </div>
                        </div>
                        <div className="supplier-cost-badges">
                          <small>비용 조건</small>
                          <div className="badge-row">
                            {getSupplierCostBadge(
                              supplier,
                              "설치 공사비",
                              "설치 공사비",
                            )}
                            {getSupplierCostBadge(supplier, "출장비", "출장비")}
                          </div>
                        </div>
                        <p className="supplier-card-summary">{cardSummary}</p>
                        <div className="supplier-foot">
                          <div>
                            <small>제출 상태</small>
                            <span className="submitted">
                              {`○ ${supplier.submitted}`}
                            </span>
                          </div>
                          <div>
                            <small>과거 성과</small>
                            <div className="badge-row">
                              {supplier.badges
                                .filter((badge) => badge !== "프리미엄 파트너")
                                .map((badge, index) => (
                                  <Badge
                                    tone={index === 0 ? "orange" : "green"}
                                    key={badge}
                                  >
                                    {badge}
                                  </Badge>
                                ))}
                            </div>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>

              <section className="panel compare-panel">
                <div className="compare-header">
                  <div>
                    <b>견적 비교</b>
                    <span>업로드된 견적서 기준</span>
                  </div>
                  <div className="compare-header-actions">
                    <SupplierPager {...supplierPagerProps} />
                  </div>
                </div>
                <div className="legend">
                  <Badge>AI 추천</Badge>
                  <Badge tone="green">최저가</Badge>
                  <Badge tone="gray">검토 필요</Badge>
                  <Badge tone="red">수정 필요</Badge>
                  <Badge tone="orange">확인 필요</Badge>
                </div>
                <div className="table-wrap accordion-wrap">
                  <table className="compare-table">
                    <thead>
                      <tr>
                        <th>항목(요구사항)</th>
                        {visibleSuppliers.map((supplier) => (
                          <th
                            className={supplier.recommended ? "ai-col" : ""}
                            key={supplier.id}
                          >
                            {supplier.name}
                            {supplier.recommended && <Badge>AI 추천</Badge>}
                          </th>
                        ))}
                      </tr>
                    </thead>
                  </table>

                  {comparisonSections.map((section) => (
                    <div className="compare-section" key={section.id}>
                      <button
                        className="compare-section-toggle"
                        onClick={() => toggleSection(section.id)}
                        type="button"
                      >
                        <span>{section.title}</span>
                        <i
                          aria-hidden="true"
                          className={`fa-solid ${
                            (openSections[section.id] ??
                            defaultOpenSections[section.id])
                              ? "fa-angle-down"
                              : "fa-angle-right"
                          }`}
                        />
                      </button>

                      {(openSections[section.id] ??
                        defaultOpenSections[section.id]) && (
                        <table className="compare-table compare-section-table">
                          <tbody>
                            {section.rows.map((row) => (
                              <tr key={row.label}>
                                <td>{row.label}</td>
                                {visibleSuppliers.map((supplier) => (
                                  <td key={`${supplier.id}-${row.label}`}>
                                    {renderCompareCell(supplier, row)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  ))}

                  <div className="compare-section total-section">
                    <button
                      className="compare-section-toggle"
                      onClick={() => toggleSection("total")}
                      type="button"
                    >
                      <span>합계 행</span>
                      <i
                        aria-hidden="true"
                        className={`fa-solid ${
                          (openSections.total ?? defaultOpenSections.total)
                            ? "fa-angle-down"
                            : "fa-angle-right"
                        }`}
                      />
                    </button>

                    {(openSections.total ?? defaultOpenSections.total) && (
                      <table className="compare-table compare-section-table compare-total-table">
                        <tbody>
                          {totalRows.map((row) => (
                            <tr className="required-amount-row" key={row.label}>
                              <td>
                                <div className="required-label">
                                  <span>{row.label}</span>
                                  {row.label === "견적 총액" && (
                                    <span className="vat-note">VAT 미포함</span>
                                  )}
                                </div>
                              </td>
                              {visibleSuppliers.map((supplier) => (
                                <td key={`${supplier.id}-${row.label}`}>
                                  {renderCompareCell(supplier, row)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </section>
            </div>

            <aside className="side-column panel-static">
              <section className="panel ai-panel">
                <div className="requirements-section-title">
                  <div>
                    <h2>AI 근거 요약</h2>
                  </div>
                </div>
                {explanationIsFallback && (
                  <div className="fallback-notice">{AI_FALLBACK_NOTICE}</div>
                )}
                <p>{overallSummary}</p>
                <button
                  className="side-title side-title-button"
                  onClick={() => setProsOpen((open) => !open)}
                  type="button"
                >
                  <span>공급사 장단점</span>
                  <i
                    aria-hidden="true"
                    className={`fa-solid ${prosOpen ? "fa-angle-down" : "fa-angle-right"}`}
                  />
                </button>
                {prosOpen && (
                  <div className="pros-list">
                    {supplierExplanations.map((supplier) => (
                      <div
                        className={`pros-item${
                          supplier.recommended ? " recommended" : ""
                        }`}
                        key={supplier.quoteId ?? supplier.displayName}
                      >
                        <div className="pros-brand">
                          <span className="rank">{supplier.rank}</span>
                          <b>{supplier.displayName ?? supplier.vendorName}</b>
                        </div>
                        <div className="pros-detail">
                          <ProsConsGroup
                            items={supplier.strengthItems}
                            label="장점"
                          />
                          <ProsConsGroup
                            items={supplier.weaknessItems}
                            label="단점"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="panel compact-panel memo-panel-full">
                <div className="requirements-section-title">
                  <div>
                    <h2>
                      검토 메모 <small>(내부용)</small>
                    </h2>
                  </div>
                </div>
                <div className="compact-panel-body">
                  <textarea
                    className={isMemoEditing ? "memo-editing" : "memo-readonly"}
                    disabled={isMemoSaving}
                    onChange={(event) =>
                      setDraftMemo(event.target.value.slice(0, maxMemoLength))
                    }
                    onClick={!isMemoEditing ? startMemoEdit : undefined}
                    placeholder="팀 내부에서 공유되는 메모예요."
                    readOnly={!isMemoEditing}
                    value={memoValue}
                  />
                  <div className="counter">
                    {memoValue.length} / {maxMemoLength.toLocaleString()}
                  </div>
                </div>
                <div className="memo-actions">
                  <button
                    className="button"
                    disabled={isMemoSaving}
                    onClick={startMemoEdit}
                    type="button"
                  >
                    수정하기
                  </button>
                  <button
                    className="button action-primary"
                    disabled={!isMemoEditing || isMemoSaving}
                    onClick={() => {
                      void saveMemo();
                    }}
                    type="button"
                  >
                    저장하기
                  </button>
                </div>
              </section>

              <section className="panel final-panel">
                <div className="requirements-section-title">
                  <div>
                    <h2>
                      최종 선정 <small>(담당자 선택)</small>
                    </h2>
                  </div>
                </div>
                <div className="choice-grid">
                  {selectableSuppliers.map((supplier) => (
                    <label
                      className={`choice-card ${selectedSupplierId === supplier.id ? "selected" : ""}`}
                      key={supplier.id}
                    >
                      <input
                        checked={selectedSupplierId === supplier.id}
                        onChange={() => setSelectedSupplierId(supplier.id)}
                        type="radio"
                      />
                      <b>{supplier.name}</b>
                      {supplier.recommended && (
                        <div>
                          <Badge>AI 추천</Badge>
                        </div>
                      )}
                    </label>
                  ))}
                </div>
                <div className="notice">
                  <b>유의 사항</b>
                  <span>{AI_COMPARE_NOTICE}</span>
                </div>
              </section>
            </aside>
          </div>
        )}
      </main>

      {compareState === "ready" && (
        <footer className="dashboard-bottom-actions">
          <span>
            {isAdminSelectionDone
              ? "상태: 확정 완료"
              : selectionFinalized
                ? "상태: 검토 완료 · 결재 대기"
                : "상태: 견적 검토 진행 중"}
          </span>
          <div>
            <button
              className="button action-secondary"
              onClick={() => setBackConfirmOpen(true)}
              type="button"
            >
              이전
            </button>
          <button
            className="button action-secondary"
            disabled
            title="검토 메모 저장은 오른쪽 메모 영역에서만 할 수 있어요."
            type="button"
          >
            임시 저장
          </button>
          <button
            className="button action-secondary"
            disabled={!canExportReport}
            onClick={handleExportToExcel}
            title={
              canExportReport
                ? "AI 근거 요약을 고객 보고서(엑셀)로 내보내요."
                : "AI 근거 요약을 불러온 뒤 내보낼 수 있어요."
            }
            type="button"
          >
            고객 보고서로 내보내기
          </button>
          {isMember ? (
            <>
              <button
                className="button action-secondary button-looks-disabled"
                onClick={() => setPermissionDeniedOpen(true)}
                type="button"
              >
                최종 선정
              </button>
              <button
                className={
                  selectionFinalized
                    ? "button selection-complete-button"
                    : "button action-primary"
                }
                disabled={selectionFinalized || !selectedSupplier}
                onClick={() => setConfirmAction("review-complete")}
                type="button"
              >
                {selectionFinalized ? "결재 요청됨" : "검토 완료"}
              </button>
            </>
          ) : (
            <button
              className={
                isAdminSelectionDone
                  ? "button selection-complete-button"
                  : isApprovalPending
                    ? "button action-primary"
                    : "button action-secondary button-looks-disabled"
              }
              disabled={isAdminSelectionDone || !isApprovalPending}
              onClick={() => setConfirmAction("admin-approve")}
              title={
                !isApprovalPending && !isAdminSelectionDone
                  ? "결재 요청된 프로젝트만 최종 선정할 수 있어요."
                  : undefined
              }
              type="button"
            >
              {isAdminSelectionDone ? "확정 완료" : "최종 선정"}
            </button>
          )}
          </div>
        </footer>
      )}
      {backConfirmOpen && (
        <div className="confirm-layer" role="presentation">
          <div
            className="confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dashboard-back-confirm-title"
          >
            <h2 id="dashboard-back-confirm-title">이전 단계로 이동할까요?</h2>
            <p>작성 중인 내용이 저장되지 않을 수 있어요.</p>
            <div className="confirm-actions">
              <button
                className="button"
                onClick={() => setBackConfirmOpen(false)}
                type="button"
              >
                취소
              </button>
              <button
                className="button action-primary"
                onClick={() => {
                  setBackConfirmOpen(false);
                  (onBack ?? onGoProjects)?.();
                }}
                type="button"
              >
                이동
              </button>
            </div>
          </div>
        </div>
      )}
      {permissionDeniedOpen && (
        <div className="confirm-layer" role="presentation">
          <div
            className="confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="permission-denied-title"
          >
            <h2 id="permission-denied-title">{FINAL_SELECTION.noPermissionTitle}</h2>
            <p>{FINAL_SELECTION.noPermission}</p>
            <div className="confirm-actions">
              <button
                className="button action-primary"
                onClick={() => setPermissionDeniedOpen(false)}
                type="button"
              >
                확인
              </button>
            </div>
          </div>
        </div>
      )}
      {confirmAction && (
        <div className="confirm-layer" role="presentation">
          <div
            className="confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-label={confirmCopy.dialogTitle}
          >
            <h2>{confirmCopy.dialogTitle}</h2>
            <p>
              {confirmAction === "review-complete"
                ? reviewCompleteConfirmMessage
                : finalSelectionConfirmMessage}
            </p>
            {confirmAction === "review-complete" && (
              <p className="confirm-result-note">{confirmCopy.dialogResult}</p>
            )}
            <div className="confirm-actions">
              <button
                className="button"
                disabled={confirmInProgress}
                onClick={() => setConfirmAction(null)}
                type="button"
              >
                취소
              </button>
              <button
                className="button action-primary"
                disabled={confirmInProgress}
                onClick={handleConfirmSubmit}
                type="button"
              >
                {confirmAction === "review-complete"
                  ? "결재 요청"
                  : confirmAction === "admin-approve"
                    ? "확정"
                    : "확정"}
              </button>
            </div>
          </div>
        </div>
      )}
      {toastVisible && (
        <div className="selection-toast" role="status">
          {successFeedback.toast}
        </div>
      )}
      {selectionFinalized && followupVisible && (
        <div className="selection-followup">
          <button
            aria-label="확정 완료 안내 닫기"
            className="selection-followup-close"
            onClick={() => setFollowupVisible(false)}
            type="button"
          >
            <i aria-hidden="true" className="fa-solid fa-xmark" />
          </button>
          <b>{successFeedback.doneEmotion}</b>
          <span>{successFeedback.statusChanged}</span>
          <div>
            <button className="button" onClick={onGoProjects} type="button">
              프로젝트 목록으로 이동
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function EditableCompareCell({ cell, rowLabel, onSave, statusBadge }) {
  const displayValue = getCompareCellDisplayValue(cell, rowLabel);
  const isMissing =
    rowLabel === "특이사항"
      ? cell?.status === "editable" && !displayValue
      : isMissingCompareCell(cell);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
    }
  }, [editing]);

  const startEditing = () => {
    if (saving) return;
    const initialDraft =
      typeof displayValue === "string" && !isMissingCompareCellValue(displayValue)
        ? displayValue
        : "";
    setDraft(initialDraft);
    setEditing(true);
  };

  const cancelEditing = () => {
    setDraft("");
    setEditing(false);
  };

  const commitEdit = async () => {
    if (saving) return;

    const trimmed = draft.trim();
    if (!trimmed || isMissingCompareCellValue(trimmed)) {
      cancelEditing();
      return;
    }

    setSaving(true);
    try {
      await onSave(trimmed);
      setEditing(false);
    } catch (error) {
      setDraft("");
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void commitEdit();
    }
    if (event.key === "Escape") {
      event.preventDefault();
      cancelEditing();
    }
  };

  if (editing) {
    return (
      <div className="compare-cell compare-cell-editing cell-missing">
        <input
          className="compare-inline-edit-input"
          disabled={saving}
          onBlur={() => {
            void commitEdit();
          }}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`${rowLabel} 입력`}
          ref={inputRef}
          type="text"
          value={draft}
        />
      </div>
    );
  }

  return (
    <div
      className={[
        "compare-cell",
        "compare-inline-edit",
        isMissing || statusBadge ? "cell-missing" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span>{displayValue || null}</span>
      {statusBadge}
      <button
        aria-label={`${rowLabel} 수정`}
        className="compare-inline-edit-trigger"
        onClick={startEditing}
        type="button"
      >
        <i aria-hidden="true" className="fa-solid fa-pencil compare-inline-edit-icon" />
      </button>
    </div>
  );
}

function splitProsConsItems(value) {
  const text = String(value ?? "").trim();
  if (!text || text === "-") return [];

  return text
    .split(/,\s*/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function ProsConsGroup({ label, items = [] }) {
  const list = Array.isArray(items) ? items.filter(Boolean) : [];
  const hasMultiple = list.length > 1;

  return (
    <div className="pros-detail-group">
      <span className="pros-detail-label">{label}</span>
      {list.length === 0 ? (
        <span className="pros-detail-empty">-</span>
      ) : hasMultiple ? (
        <ul className="pros-detail-list">
          {list.map((item) => (
            <li key={`${label}-${item}`}>
              <span className="pros-detail-marker">•</span>
              <span className="pros-detail-text">{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <span>{list[0]}</span>
      )}
    </div>
  );
}

function CompareLoadingState() {
  return (
    <section className="compare-state-panel" aria-busy="true">
      <div className="state-card state-card-loading">
        <div className="state-icon loading-icon" />
        <div>
          <h2>견적 비교 데이터를 불러오고 있어요</h2>
          <p>공급사 정보, 견적 항목, AI 근거 요약을 준비하고 있어요.</p>
        </div>
      </div>
      <div className="loading-layout">
        <div className="loading-main">
          <div className="skeleton-row skeleton-title" />
          <div className="skeleton-grid">
            <div className="skeleton-card" />
            <div className="skeleton-card" />
            <div className="skeleton-card" />
          </div>
          <div className="skeleton-table">
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>
        </div>
        <div className="loading-side">
          <div className="skeleton-card tall" />
          <div className="skeleton-card" />
        </div>
      </div>
    </section>
  );
}

function CompareErrorState({ message, onGoProjects, onRetry }) {
  return (
    <section className="compare-state-panel">
      <div className="state-card state-card-error">
        <div className="state-icon error-icon">!</div>
        <div>
          <h2>견적 비교 데이터를 불러오지 못했어요</h2>
          <p>{message}</p>
          <div className="state-actions">
            <button
              className="button action-primary"
              onClick={onRetry}
              type="button"
            >
              다시 시도
            </button>
            <button
              className="button action-secondary"
              onClick={onGoProjects}
              type="button"
            >
              프로젝트 목록으로 이동
            </button>
          </div>
        </div>
      </div>
      <div className="error-guide">
        <b>이렇게 해보세요</b>
        <span>
          잠시 후 다시 시도해 주세요. 문제가 계속되면 업로드한 견적서 상태와
          네트워크 연결을 확인해 주세요.
        </span>
      </div>
    </section>
  );
}
