import { useEffect, useMemo, useRef, useState } from "react";
import * as XLSX from "xlsx";
import AutoSaveStatus from "../components/AutoSaveStatus";
import Badge from "../components/Badge";
import BrandHomeButton from "../components/BrandHomeButton";
import useCompareResult from "../hooks/useCompareResult";
import useExplanationResult from "../hooks/useExplanationResult";
import { updateProject } from "../api/apiClient";
import { getStatusUi } from "../utils/statusMap";
import {
  applyCompareCellOverride,
  getCompareCellOverrideKey,
  resolveCompareCellOverrides,
  saveCompareCellOverridesToStorage,
} from "../utils/compareCellOverrides";
import { withObjectParticle, withSubjectParticle } from "../utils/josa";
import {
  AI_COMPARE_NOTICE,
  AI_FALLBACK_NOTICE,
  FINAL_SELECTION,
} from "../constants/uiText";

const VISIBLE_SUPPLIER_COUNT = 3;

/** 미기재로 간주하는 셀 표시값 */
const MISSING_COMPARE_CELL_VALUES = ["-", "미기재", "—"];

/** 비교 테이블 인라인 편집 제외 행 — 제외할 행이 생기면 이 배열만 수정 */
const NON_EDITABLE_COMPARE_ROW_LABELS = [];

function isMissingCompareCellValue(value) {
  if (typeof value !== "string") return false;
  const displayValue = value.trim() || "—";
  return MISSING_COMPARE_CELL_VALUES.includes(displayValue);
}

function isEditableMissingCompareCell(rowLabel, cell) {
  if (NON_EDITABLE_COMPARE_ROW_LABELS.includes(rowLabel)) return false;
  if (cell?.status === "missing") return true;
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
        ‹
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
        ›
      </button>
    </div>
  );
}

export default function DashboardPage({
  projectData,
  onBack,
  onGoProjects,
  onProjectDataChange,
}) {
  const [selectedSupplierId, setSelectedSupplierId] = useState(
    projectData.selectedSupplierId ?? "",
  );
  const isFailureScenario = Boolean(projectData.failureScenario);
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
  const explanationByVendor = useMemo(
    () => new Map(supplierExplanations.map((item) => [item.vendorName, item])),
    [supplierExplanations],
  );
  const defaultOpenSections = useMemo(
    () =>
      comparisonSections.reduce(
        (sections, section) => ({
          ...sections,
          [section.id]: isFailureScenario ? true : section.defaultOpen,
        }),
        { total: true },
      ),
    [comparisonSections, isFailureScenario],
  );
  const [openSections, setOpenSections] = useState(defaultOpenSections);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [selectionFinalized, setSelectionFinalized] = useState(
    projectData.workflowStatus === "완료",
  );
  const [toastVisible, setToastVisible] = useState(false);
  const [followupVisible, setFollowupVisible] = useState(false);
  const [prosOpen, setProsOpen] = useState(true);
  const maxMemoLength = 1000;
  const [reviewMemo, setReviewMemo] = useState(projectData.reviewMemo ?? "");
  const [draftMemo, setDraftMemo] = useState(projectData.reviewMemo ?? "");
  const [isMemoEditing, setIsMemoEditing] = useState(false);
  const [autoSaveStatus, setAutoSaveStatus] = useState("idle");
  const [isProjectNameEditing, setIsProjectNameEditing] = useState(false);
  const [draftProjectName, setDraftProjectName] = useState(
    projectData.projectName ?? "",
  );
  const [isProjectNameSaving, setIsProjectNameSaving] = useState(false);
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
    setSelectionFinalized(projectData.workflowStatus === "완료");
  }, [projectData.workflowStatus]);

  useEffect(() => {
    const memo = projectData.reviewMemo ?? "";
    setReviewMemo(memo);
    setDraftMemo(memo);
    setIsMemoEditing(false);
  }, [projectId, projectData.reviewMemo]);

  useEffect(() => {
    setDraftProjectName(projectData.projectName ?? "");
    setIsProjectNameEditing(false);
    setIsProjectNameSaving(false);
  }, [projectId, projectData.projectName]);

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
      explanationByVendor.get(supplier.vendorName ?? supplier.name)
        ?.cardSummary ?? ""
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
    const value = cell.value || "—";
    const canEditCompareCell =
      overriddenValue !== undefined ||
      isEditableMissingCompareCell(row.label, baseCell);

    if (canEditCompareCell) {
      return (
        <EditableCompareCell
          cell={cell}
          onSave={(nextValue) =>
            handleCompareCellSave(supplier, row.label, nextValue)
          }
          rowLabel={row.label}
          statusBadge={
            overriddenValue === undefined
              ? getStatusBadge(baseCell.status ?? "missing")
              : null
          }
        />
      );
    }

    const cellClasses = [
      "compare-cell",
      status ? `cell-${status}` : "",
      highlight ? `cell-${highlight}` : "",
    ]
      .filter(Boolean)
      .join(" ");

    return (
      <div className={cellClasses}>
        <span className={highlight === "bestPrice" ? "price-best" : ""}>
          {value}
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
    setDraftMemo(reviewMemo);
    setIsMemoEditing(true);
  };

  const saveMemo = () => {
    showAutoSaveStatus("saving");
    setReviewMemo(draftMemo);
    setIsMemoEditing(false);
    onProjectDataChange?.((current) => ({
      ...current,
      reviewMemo: draftMemo,
      lastScreen: "dashboard",
    }));
    showAutoSaveStatus("saved");
  };

  const startProjectNameEdit = () => {
    if (isProjectNameSaving) return;
    setDraftProjectName(projectData.projectName ?? "");
    setIsProjectNameEditing(true);
  };

  const cancelProjectNameEdit = () => {
    setDraftProjectName(projectData.projectName ?? "");
    setIsProjectNameEditing(false);
  };

  const saveProjectName = async () => {
    if (isProjectNameSaving) return;

    const trimmed = draftProjectName.trim();
    if (!trimmed) {
      cancelProjectNameEdit();
      return;
    }

    const previousName = projectData.projectName ?? "";
    const apiProjectId = projectData.projectApiId ?? projectData.projectId;

    setIsProjectNameSaving(true);
    showAutoSaveStatus("saving");
    onProjectDataChange?.((current) => ({
      ...current,
      projectName: trimmed,
      lastScreen: "dashboard",
    }));

    try {
      if (apiProjectId) {
        await updateProject(apiProjectId, { project_name: trimmed });
      }
      setIsProjectNameEditing(false);
      showAutoSaveStatus("saved");
    } catch (error) {
      console.error("프로젝트명 저장 실패:", error);
      onProjectDataChange?.((current) => ({
        ...current,
        projectName: previousName,
      }));
      setDraftProjectName(previousName);
      showAutoSaveStatus("error");
    } finally {
      setIsProjectNameSaving(false);
    }
  };

  const memoValue = isMemoEditing ? draftMemo : reviewMemo;

  const confirmSelection = () => {
    setConfirmOpen(false);
    setSelectionFinalized(true);
    setFollowupVisible(true);
    setToastVisible(true);
    onProjectDataChange?.((current) => ({
      ...current,
      currentStage: "검토 완료",
      selectedSupplierId,
      selectedVendor: selectedSupplier?.name ?? "",
      workflowStatus: "완료",
      lastScreen: "dashboard",
    }));
    const apiProjectId = projectData.projectApiId ?? projectData.projectId;
    if (apiProjectId) {
      updateProject(apiProjectId, { workflow_status: "completed" }).catch(
        (error) => console.error("완료 상태 저장 실패:", error),
      );
    }
    window.setTimeout(() => setToastVisible(false), 3200);
  };

  const handleExportToExcel = () => {
    exportToExcel({
      projectName:
        projectData.projectName || projectData.companyName || projectId,
      overallSummary,
      supplierExplanations,
      suppliers,
      comparisonSections,
      totalRows,
      compareCellOverrides,
    });
  };

  const canExportReport = explanationState === "ready";

  return (
    <div className="app-shell">
      <header className="topbar flow-topbar">
        <div className="brand-zone">
          <BrandHomeButton onClick={onGoProjects} />
          <Badge tone="gray">v1.3.2</Badge>
          <div className="top-divider" />
          <span className="dashboard-breadcrumb-live">프로젝트 목록</span>
          <span className="dashboard-breadcrumb-live-arrow">›</span>
          <span className="dashboard-breadcrumb-live-current">
            프로젝트 <b>{projectTitle}</b>
          </span>
          <span className="breadcrumb-muted">프로젝트 목록</span>
          <span className="breadcrumb-arrow">›</span>
          <span className="breadcrumb-current">
            프로젝트 <b>{projectId}</b>
          </span>
        </div>
        <div className="user-zone">
          <AutoSaveStatus status={autoSaveStatus} />
          <div className="avatar" />
          <div className="user-name">
            <b>김담당자</b>
            <small>구매검토팀</small>
          </div>
        </div>
      </header>

      <main className="dashboard">
        <section className="project-head">
          <div className="project-title">
            <div className="project-title-edit-shell">
              {isProjectNameEditing ? (
                <div className="project-title-edit">
                  <input
                    className="project-title-input"
                    disabled={isProjectNameSaving}
                    onChange={(event) => setDraftProjectName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        void saveProjectName();
                      }
                      if (event.key === "Escape") {
                        event.preventDefault();
                        cancelProjectNameEdit();
                      }
                    }}
                    type="text"
                    value={draftProjectName}
                  />
                  <button
                    className="button button-small"
                    disabled={isProjectNameSaving}
                    onClick={() => {
                      void saveProjectName();
                    }}
                    type="button"
                  >
                    저장
                  </button>
                </div>
              ) : (
                <div className="project-title-display">
                  <h1>{projectData.projectName || `프로젝트 ${projectId}`}</h1>
                  <button
                    className="icon-button project-title-edit-button"
                    onClick={startProjectNameEdit}
                    title="프로젝트 이름 수정"
                    type="button"
                  >
                    ✎
                  </button>
                </div>
              )}
            </div>
            <h1>{projectData.projectName || `프로젝트 ${projectId}`}</h1>
            <button
              className="icon-button"
              disabled
              title="프로젝트명 수정은 곧 사용할 수 있어요."
              type="button"
            >
              ✎
            </button>
            <Badge>{selectionFinalized ? "검토 완료" : "견적 검토"}</Badge>
          </div>
          <div className="project-actions">
            <button
              className="button action-secondary"
              onClick={onGoProjects}
              type="button"
            >
              프로젝트 목록
            </button>
            <button
              className={
                selectionFinalized
                  ? "button button-green"
                  : "button button-blue"
              }
              disabled
              title="상태는 화면 진행에 따라 자동으로 반영돼요."
              type="button"
            >
              {selectionFinalized ? "검토 완료" : "검토 진행 중"}
            </button>
          </div>
        </section>

        <section className="panel meta-panel">
          <div className="panel-title">프로젝트 정보</div>
          <div className="meta-grid">
            <div className="meta-item">
              <span>회사명</span>
              <strong>{projectData.companyName}</strong>
            </div>
            <div className="meta-item">
              <span>설치 위치</span>
              <strong>{projectData.location}</strong>
            </div>
            <div className="meta-item">
              <span>프로젝트 일정</span>
              <input
                aria-label="프로젝트 일정"
                className="meta-date-input"
                readOnly
                type="date"
                value={projectData.projectDate}
              />
            </div>
            <div className="meta-item">
              <span>활용 용도</span>
              <strong>{projectData.usage}</strong>
            </div>
            <div className="meta-item">
              <span>현재 단계</span>
              <strong>
                {selectionFinalized ? "검토 완료" : projectData.currentStage}
              </strong>
            </div>
            <div className="meta-item">
              <span>예산/프리셋</span>
              <strong>
                {projectData.budgetAmount
                  ? `${projectData.budgetAmount}원`
                  : "예산 미정"}{" "}
                · {projectData.reviewPreset}
              </strong>
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

        {compareState === "ready" && isFailureScenario && (
          <section className="failure-scenario-panel">
            <div>
              <b>실패 상태 표시 점검용 예시 데이터</b>
              <span>
                업로드 실패, 내용 추출 실패, 총액 미확정, 기본 요약이 어떻게
                보이는지 확인하는 프로젝트예요.
              </span>
            </div>
            <div className="failure-state-row">
              <Badge tone="red">업로드 실패</Badge>
              <Badge tone="red">수정 필요</Badge>
              <Badge tone="gray">총액 미확정</Badge>
              <Badge tone="orange">기본 요약</Badge>
            </div>
          </section>
        )}

        {compareState === "ready" && (
          <div className="content-grid">
            <div className="main-column">
              <section className="panel supplier-panel">
                <div className="panel-title-row">
                  <div className="panel-title">
                    공급사 매칭 현황 ({supplierCount}/{supplierCount}){" "}
                    <span>ⓘ</span>
                  </div>
                  <SupplierPager {...supplierPagerProps} />
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
                            <span
                              className={`supplier-logo ${supplier.logoClass}`}
                            >
                              {supplier.logo}
                            </span>
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
                            <span
                              className={
                                isFailureScenario && supplier.id === "c"
                                  ? "submitted submitted-warning"
                                  : "submitted"
                              }
                            >
                              {isFailureScenario && supplier.id === "c"
                                ? "△ 일부 항목 인식 실패 · 2개 항목 수정 필요"
                                : `○ ${supplier.submitted}`}
                            </span>
                          </div>
                          <div>
                            <small>과거 성과</small>
                            <div className="badge-row">
                              {isFailureScenario && supplier.id === "b" && (
                                <Badge tone="orange">인식 신뢰도 낮음</Badge>
                              )}
                              {isFailureScenario && supplier.id === "c" && (
                                <Badge tone="gray">총액 미확정</Badge>
                              )}
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
                        <b>
                          {(openSections[section.id] ??
                          defaultOpenSections[section.id])
                            ? "⌃"
                            : "›"}
                        </b>
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
                      <b>
                        {(openSections.total ?? defaultOpenSections.total)
                          ? "⌃"
                          : "›"}
                      </b>
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

            <aside className="side-column">
              <section className="panel ai-panel">
                <h2>AI 근거 요약</h2>
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
                  <b>{prosOpen ? "⌃" : "›"}</b>
                </button>
                {prosOpen && (
                  <div className="pros-list">
                    {supplierExplanations.map((supplier) => (
                      <div
                        className="pros-item"
                        key={supplier.quoteId ?? supplier.vendorName}
                      >
                        <div className="pros-brand">
                          <span
                            className={`supplier-logo ${supplier.logoClass}`}
                          >
                            {supplier.logo}
                          </span>
                          <b>{supplier.vendorName}</b>
                        </div>
                        <div className="pros-detail">
                          <ProsConsGroup
                            label="장점"
                            value={supplier.strengths}
                          />
                          <ProsConsGroup
                            label="단점"
                            value={supplier.weaknesses}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <div className="side-split">
                <section className="panel compact-panel">
                  <h3>
                    검토 메모 <small>(내부용)</small>
                  </h3>
                  <div className="compact-panel-body">
                    <textarea
                      className={isMemoEditing ? "memo-editing" : "memo-readonly"}
                      onChange={(event) =>
                        setDraftMemo(event.target.value.slice(0, maxMemoLength))
                      }
                      onClick={!isMemoEditing ? startMemoEdit : undefined}
                      placeholder="검토 메모를 입력해 주세요...&#10;(내부 공유용이에요.)"
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
                      onClick={startMemoEdit}
                      type="button"
                    >
                      수정하기
                    </button>
                    <button
                      className="button action-primary"
                      disabled={!isMemoEditing}
                      onClick={saveMemo}
                      type="button"
                    >
                      저장하기
                    </button>
                  </div>
                </section>
              </div>

              <section className="panel final-panel">
                <h3>
                  최종 선정 <small>(담당자 선택)</small>
                </h3>
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
        <footer className="bottom-actions">
          <button
            className="button action-secondary"
            onClick={onBack ?? onGoProjects}
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
          <button
            className={
              selectionFinalized
                ? "button selection-complete-button"
                : "button action-primary"
            }
            disabled={selectionFinalized || !selectedSupplier}
            onClick={() => setConfirmOpen(true)}
            type="button"
          >
            {selectionFinalized ? "선정 완료" : "최종 선정 확정"}
          </button>
        </footer>
      )}
      {confirmOpen && (
        <div className="confirm-layer" role="presentation">
          <div
            className="confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="최종 선정 확인"
          >
            <h2>{FINAL_SELECTION.dialogTitle}</h2>
            <p>
              {withObjectParticle(selectedSupplier?.name ?? "")} 최종 선정
              공급사로 확정할까요?
            </p>
            <p className="confirm-result-note">{FINAL_SELECTION.dialogResult}</p>
            <div className="confirm-actions">
              <button
                className="button"
                onClick={() => setConfirmOpen(false)}
                type="button"
              >
                취소
              </button>
              <button
                className="button action-primary"
                onClick={confirmSelection}
                type="button"
              >
                확정
              </button>
            </div>
          </div>
        </div>
      )}
      {toastVisible && (
        <div className="selection-toast" role="status">
          {withSubjectParticle(selectedSupplier?.name ?? "")} 최종 선정
          공급사로 확정됐어요.
        </div>
      )}
      {selectionFinalized && followupVisible && (
        <div className="selection-followup">
          <button
            aria-label="선정 완료 안내 닫기"
            className="selection-followup-close"
            onClick={() => setFollowupVisible(false)}
            type="button"
          >
            ×
          </button>
          <b>{FINAL_SELECTION.doneEmotion}</b>
          <span>
            {withSubjectParticle(selectedSupplier?.name ?? "")} 최종 선정
            공급사로 확정됐어요. {FINAL_SELECTION.statusChanged}
          </span>
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

const EXCEL_ROW_KIND = {
  TITLE: "title",
  SECTION: "section",
  HEADER: "header",
  DATA: "data",
  SUMMARY: "summary",
  SPACER: "spacer",
  EXPLANATION_VENDOR: "explanationVendor",
  EXPLANATION_FIELD: "explanationField",
};

const EXCEL_BORDER = {
  top: { style: "thin", color: { rgb: "CBD5E1" } },
  bottom: { style: "thin", color: { rgb: "CBD5E1" } },
  left: { style: "thin", color: { rgb: "CBD5E1" } },
  right: { style: "thin", color: { rgb: "CBD5E1" } },
};

const EXCEL_LABEL_COLUMN_MAX = 18;
const EXCEL_VALUE_COLUMN_MAX = 36;

const EXCEL_STYLES = {
  title: {
    font: { bold: true, sz: 16, color: { rgb: "0F172A" } },
    fill: { fgColor: { rgb: "F1F5F9" } },
    alignment: { vertical: "center" },
  },
  section: {
    font: { bold: true, sz: 13, color: { rgb: "1E3A8A" } },
    fill: { fgColor: { rgb: "E2E8F0" } },
    alignment: { vertical: "center" },
  },
  header: {
    font: { bold: true, sz: 12, color: { rgb: "0F172A" } },
    fill: { fgColor: { rgb: "DBEAFE" } },
    alignment: { horizontal: "center", vertical: "center", wrapText: true },
    border: EXCEL_BORDER,
  },
  dataLabel: {
    font: { bold: true, sz: 12, color: { rgb: "475569" } },
    fill: { fgColor: { rgb: "F8FAFC" } },
    alignment: { vertical: "top", wrapText: true },
    border: EXCEL_BORDER,
  },
  dataValue: {
    font: { sz: 12, color: { rgb: "0F172A" } },
    alignment: { vertical: "top", wrapText: true },
    border: EXCEL_BORDER,
  },
  summary: {
    font: { sz: 12, color: { rgb: "0F172A" } },
    fill: { fgColor: { rgb: "F8FAFC" } },
    alignment: { vertical: "top", wrapText: true },
    border: EXCEL_BORDER,
  },
};

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

function ComparePencilIcon() {
  return (
    <svg
      aria-hidden="true"
      className="compare-inline-edit-icon"
      fill="none"
      height="12"
      viewBox="0 0 24 24"
      width="12"
    >
      <path
        d="M4 20h4l10.5-10.5a1.4 1.4 0 0 0 0-2L16.5 5.5a1.4 1.4 0 0 0-2 0L4 16v4Z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.75"
      />
      <path
        d="m13.5 6.5 4 4"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.75"
      />
    </svg>
  );
}

function EditableCompareCell({ cell, rowLabel, onSave, statusBadge }) {
  const value = cell.value || "—";
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
      typeof value === "string" && !isMissingCompareCellValue(value)
        ? value
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
        statusBadge ? "cell-missing" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span>{value}</span>
      {statusBadge}
      <button
        aria-label={`${rowLabel} 수정`}
        className="compare-inline-edit-trigger"
        onClick={startEditing}
        type="button"
      >
        <ComparePencilIcon />
      </button>
    </div>
  );
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

function formatSpecialNotesForExcel(value) {
  const text = String(value ?? "—").trim();
  if (!text || text === "—" || text === "-") return text;

  const parts = text.includes(", ")
    ? text
        .split(/,\s+/)
        .map((part) => part.trim())
        .filter(Boolean)
    : [text];

  return parts.flatMap((part) => wrapSingleLine(part, 44)).join("\n");
}

function formatReadableCompareValue(value, rowLabel) {
  if (rowLabel === "특이사항") return formatSpecialNotesForExcel(value);

  const text = String(value ?? "—");
  if (text === "—" || getCellDisplayWidth(text) <= 28) return text;
  return wrapSingleLine(text, 28).join("\n");
}

function formatCompareCellValue(cell, rowLabel) {
  const rawValue = cell?.value || "—";
  const value = formatReadableCompareValue(rawValue, rowLabel);
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

function buildCompareSheetRows(
  suppliers,
  comparisonSections,
  totalRows,
  compareCellOverrides = {},
) {
  const header = [
    "항목(요구사항)",
    ...suppliers.map((supplier) => supplier.name),
  ];
  const rows = [
    ["견적 비교표", ...Array(Math.max(header.length - 1, 0)).fill("")],
  ];
  const rowKinds = [EXCEL_ROW_KIND.TITLE];

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
          ),
        ),
      ]);
      rowKinds.push(EXCEL_ROW_KIND.DATA);
    });
  }

  return { rows, rowKinds };
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

function applyWrapRowHeights(worksheet, rows, rowKinds) {
  if (!worksheet["!rows"]) worksheet["!rows"] = [];

  rows.forEach((row, rowIndex) => {
    const kind = rowKinds?.[rowIndex];
    const isSpecialNotesRow = row[0] === "특이사항";
    const shouldAdjust =
      isSpecialNotesRow ||
      kind === EXCEL_ROW_KIND.SUMMARY ||
      kind === EXCEL_ROW_KIND.DATA ||
      kind === EXCEL_ROW_KIND.EXPLANATION_FIELD;

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
      return;
    }

    worksheet["!rows"][rowIndex] = {
      hpt: Math.min(
        Math.max(
          20 * maxLineCount + 8,
          kind === EXCEL_ROW_KIND.SUMMARY ? 40 : 28,
        ),
        260,
      ),
    };
  });
}

function getRowColumnCount(rows) {
  return rows.reduce((max, row) => Math.max(max, row.length), 1);
}

function applySheetVisualStyles(worksheet, rows, rowKinds) {
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
      rowKind === EXCEL_ROW_KIND.SUMMARY ||
      rowKind === EXCEL_ROW_KIND.EXPLANATION_VENDOR
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
      if (rowKind === EXCEL_ROW_KIND.EXPLANATION_VENDOR) {
        cell.s = EXCEL_STYLES.section;
        continue;
      }
      if (rowKind === EXCEL_ROW_KIND.HEADER) {
        cell.s = EXCEL_STYLES.header;
        continue;
      }
      if (rowKind === EXCEL_ROW_KIND.SUMMARY) {
        cell.s = EXCEL_STYLES.summary;
        continue;
      }
      if (
        rowKind === EXCEL_ROW_KIND.DATA ||
        rowKind === EXCEL_ROW_KIND.EXPLANATION_FIELD
      ) {
        cell.s =
          columnIndex === 0 ? EXCEL_STYLES.dataLabel : EXCEL_STYLES.dataValue;
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
    columnMaxWidths = null,
    skipRowKinds = new Set([
      EXCEL_ROW_KIND.TITLE,
      EXCEL_ROW_KIND.SUMMARY,
      EXCEL_ROW_KIND.SECTION,
      EXCEL_ROW_KIND.SPACER,
      EXCEL_ROW_KIND.EXPLANATION_VENDOR,
    ]),
  } = options;
  const columnWidths = [];

  rows.forEach((row, rowIndex) => {
    const kind = rowKinds?.[rowIndex];
    if (kind && skipRowKinds.has(kind)) return;

    row.forEach((cell, columnIndex) => {
      let cellWidth = getCellDisplayWidth(cell) + 2;
      if (columnIndex === 0) {
        cellWidth = Math.min(cellWidth, EXCEL_LABEL_COLUMN_MAX);
      } else if (kind === EXCEL_ROW_KIND.EXPLANATION_FIELD) {
        cellWidth = Math.min(cellWidth, EXCEL_VALUE_COLUMN_MAX);
      }
      columnWidths[columnIndex] = Math.max(
        columnWidths[columnIndex] ?? 8,
        cellWidth,
      );
    });
  });

  const maxColumnIndex = Math.max(columnWidths.length - 1, 0);

  if (maxColumnIndex >= 1) {
    const supplierWidths = Array.from(
      { length: maxColumnIndex },
      (_, index) => columnWidths[index + 1] ?? 14,
    );
    const uniformWidth = Math.min(
      EXCEL_VALUE_COLUMN_MAX,
      Math.max(
        16,
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
      const width = columnWidths[index] ?? 10;
      const max =
        columnMaxWidths?.[index] ??
        (index === 0 ? EXCEL_LABEL_COLUMN_MAX : EXCEL_VALUE_COLUMN_MAX);
      const min = index === 0 ? 12 : 14;
      return { wch: Math.min(Math.max(width, min), max) };
    },
  );
}

function buildExplanationSheetRows(overallSummary, supplierExplanations) {
  const rows = [
    ["AI 근거 요약"],
    [formatWrappedTextForExcel(overallSummary, 56)],
    [],
    ["공급사별 상세"],
  ];
  const rowKinds = [
    EXCEL_ROW_KIND.TITLE,
    EXCEL_ROW_KIND.SUMMARY,
    EXCEL_ROW_KIND.SPACER,
    EXCEL_ROW_KIND.SECTION,
  ];

  const header = [
    "항목",
    ...supplierExplanations.map((item) => item.vendorName || "-"),
  ];
  rows.push(header);
  rowKinds.push(EXCEL_ROW_KIND.HEADER);

  const fieldDefs = [
    {
      label: "요약",
      getValue: (item) => formatWrappedTextForExcel(item.cardSummary, 44),
    },
    {
      label: "장점",
      getValue: (item) => formatExplanationListForExcel(item.strengths, 44),
    },
    {
      label: "단점",
      getValue: (item) => formatExplanationListForExcel(item.weaknesses, 44),
    },
    {
      label: "확인 필요",
      getValue: (item) =>
        formatExplanationListForExcel(
          Array.isArray(item.checkRequired) && item.checkRequired.length > 0
            ? item.checkRequired.join(", ")
            : "-",
          44,
        ),
    },
  ];

  fieldDefs.forEach(({ label, getValue }) => {
    rows.push([label, ...supplierExplanations.map((item) => getValue(item))]);
    rowKinds.push(EXCEL_ROW_KIND.EXPLANATION_FIELD);
  });

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

function exportToExcel({
  projectName,
  overallSummary,
  supplierExplanations,
  suppliers,
  comparisonSections,
  totalRows,
  compareCellOverrides = {},
}) {
  const workbook = XLSX.utils.book_new();

  const explanationSection = buildExplanationSheetRows(
    overallSummary,
    supplierExplanations,
  );
  const compareSection = buildCompareSheetRows(
    suppliers,
    comparisonSections,
    totalRows,
    compareCellOverrides,
  );
  const { rows, rowKinds } = mergeSheetSections(
    explanationSection,
    compareSection,
  );

  const reportSheet = XLSX.utils.aoa_to_sheet(rows);
  applySheetVisualStyles(reportSheet, rows, rowKinds);
  applySheetColumnWidths(reportSheet, rows, { rowKinds });
  applyWrapRowHeights(reportSheet, rows, rowKinds);
  XLSX.utils.book_append_sheet(workbook, reportSheet, "고객 보고서");

  const safeName = String(projectName || "프로젝트").replace(
    /[\\/:*?"<>|]/g,
    "_",
  );
  XLSX.writeFile(workbook, `${safeName}_고객보고서.xlsx`);
}

function splitProsConsItems(value) {
  const text = String(value ?? "").trim();
  if (!text || text === "-") return [];

  return text
    .split(/,\s*/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function ProsConsGroup({ label, value }) {
  const items = splitProsConsItems(value);
  const hasMultiple = items.length > 1;

  return (
    <div className="pros-detail-group">
      <span className="pros-detail-label">{label}</span>
      {items.length === 0 ? (
        <span className="pros-detail-empty">-</span>
      ) : hasMultiple ? (
        <ul className="pros-detail-list">
          {items.map((item) => (
            <li key={`${label}-${item}`}>
              <span className="pros-detail-marker">•</span>
              <span className="pros-detail-text">{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <span>{items[0]}</span>
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
