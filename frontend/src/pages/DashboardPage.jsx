import { useEffect, useMemo, useState } from 'react';
import Badge from '../components/Badge';
import useCompareResult from '../hooks/useCompareResult';
import useExplanationResult from '../hooks/useExplanationResult';
import { getStatusUi } from '../utils/statusMap';

const VISIBLE_SUPPLIER_COUNT = 3;

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
  onGoProjects,
  onProjectDataChange,
}) {
  const [selectedVendor, setSelectedVendor] = useState(projectData.selectedVendor ?? "");
  const isFailureScenario = Boolean(projectData.failureScenario);
  const projectId = projectData.projectId || projectData.projectApiId || "프로젝트";
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
    [supplierExplanations]
  );
  const defaultOpenSections = useMemo(
    () => comparisonSections.reduce((sections, section) => ({
      ...sections,
      [section.id]: isFailureScenario ? true : section.defaultOpen,
    }), { total: true }),
    [comparisonSections, isFailureScenario]
  );
  const [openSections, setOpenSections] = useState(defaultOpenSections);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [selectionFinalized, setSelectionFinalized] = useState(projectData.workflowStatus === "완료");
  const [toastVisible, setToastVisible] = useState(false);
  const [followupVisible, setFollowupVisible] = useState(false);
  const [prosOpen, setProsOpen] = useState(true);
  const maxMemoLength = 1000;
  const [reviewMemo, setReviewMemo] = useState(projectData.reviewMemo ?? "");
  const [draftMemo, setDraftMemo] = useState(projectData.reviewMemo ?? "");
  const [isMemoEditing, setIsMemoEditing] = useState(false);
  const [supplierStartIndex, setSupplierStartIndex] = useState(0);
  const supplierCount = suppliers.length;
  const canNavigateSuppliers = supplierCount > VISIBLE_SUPPLIER_COUNT;
  const maxSupplierStartIndex =
    supplierCount <= VISIBLE_SUPPLIER_COUNT
      ? 0
      : Math.floor((supplierCount - 1) / VISIBLE_SUPPLIER_COUNT) * VISIBLE_SUPPLIER_COUNT;
  const visibleSuppliers = useMemo(
    () => suppliers.slice(supplierStartIndex, supplierStartIndex + VISIBLE_SUPPLIER_COUNT),
    [suppliers, supplierStartIndex]
  );
  const selectableVendors = useMemo(() => {
    const vendorMap = new Map();
    suppliers.forEach((supplier) => {
      const vendorName = supplier.vendorName ?? supplier.name;
      if (!vendorMap.has(vendorName)) {
        vendorMap.set(vendorName, {
          ...supplier,
          name: vendorName,
        });
      }
    });
    return Array.from(vendorMap.values());
  }, [suppliers]);
  const canGoPrevSuppliers = canNavigateSuppliers && supplierStartIndex > 0;
  const canGoNextSuppliers = canNavigateSuppliers && supplierStartIndex < maxSupplierStartIndex;

  useEffect(() => {
    setSupplierStartIndex(0);
  }, [supplierCount]);

  useEffect(() => {
    if (!selectableVendors.length) return;
    setSelectedVendor((current) =>
      current && selectableVendors.some((supplier) => supplier.name === current)
        ? current
        : projectData.selectedVendor && selectableVendors.some((supplier) => supplier.name === projectData.selectedVendor)
          ? projectData.selectedVendor
        : selectableVendors[0].name,
    );
  }, [projectData.selectedVendor, selectableVendors]);

  useEffect(() => {
    setSelectionFinalized(projectData.workflowStatus === "완료");
  }, [projectData.workflowStatus]);

  useEffect(() => {
    const memo = projectData.reviewMemo ?? "";
    setReviewMemo(memo);
    setDraftMemo(memo);
    setIsMemoEditing(false);
  }, [projectId, projectData.reviewMemo]);

  const goPrevSuppliers = () => {
    setSupplierStartIndex((current) => Math.max(0, current - VISIBLE_SUPPLIER_COUNT));
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
      return "AI 근거 요약을 불러오는 중입니다.";
    }

    return explanationByVendor.get(supplier.vendorName ?? supplier.name)?.cardSummary ?? "";
  };

  const toggleSection = (sectionId) => {
    setOpenSections((current) => ({
      ...current,
      [sectionId]: !(current[sectionId] ?? defaultOpenSections[sectionId] ?? false),
    }));
  };

  const getStatusBadge = (status) => {
    const statusUi = getStatusUi(status);
    if (!statusUi) return null;
    return <Badge tone={statusUi.tone}>{statusUi.badge}</Badge>;
  };

  const getSupplierCostBadge = (supplier, key, label) => {
    const row = comparisonSections
      .flatMap((section) => section.rows)
      .find((item) => item.label === key);
    const cell = row?.cells?.[supplier.id];
    const status = cell?.status;
    const value = cell?.value || "";

    if (status === "included" || value.includes("포함")) {
      return <Badge tone="green" key={key}>{label} 포함</Badge>;
    }
    if (status === "separate" || value.includes("별도")) {
      return <Badge tone="gray" key={key}>{label} 별도</Badge>;
    }
    if (status === "parseFail") {
      return <Badge tone="red" key={key}>{label} OCR 분석 실패</Badge>;
    }
    if (status === "toBeDiscussed" || value.includes("검토") || value.includes("확인")) {
      return <Badge tone="orange" key={key}>{label} 검토 필요</Badge>;
    }
    return null;
  };

  const renderCompareCell = (supplier, row) => {
    const cell = row.cells?.[supplier.id] ?? { value: "—" };
    const status = cell.status;
    const highlight = cell.highlight;
    const value = cell.value || "—";
    const cellClasses = [
      "compare-cell",
      status ? `cell-${status}` : "",
      highlight ? `cell-${highlight}` : "",
    ].filter(Boolean).join(" ");

    return (
      <div className={cellClasses}>
        <span className={highlight === "bestPrice" ? "price-best" : ""}>{value}</span>
        {getStatusBadge(status)}
        {getStatusBadge(highlight)}
      </div>
    );
  };

  const startMemoEdit = () => {
    setDraftMemo(reviewMemo);
    setIsMemoEditing(true);
  };

  const saveMemo = () => {
    setReviewMemo(draftMemo);
    setIsMemoEditing(false);
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
      selectedVendor,
      workflowStatus: "완료",
      lastScreen: "dashboard",
    }));
    window.setTimeout(() => setToastVisible(false), 3200);
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-zone">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
          </div>
          <div className="brand-title">견적 검토 쿼파일럿</div>
          <Badge tone="gray">v1.3.2</Badge>
          <div className="top-divider" />
          <span className="breadcrumb-muted">프로젝트 목록</span>
          <span className="breadcrumb-arrow">›</span>
          <span className="breadcrumb-current">
            프로젝트 <b>{projectId}</b>
          </span>
        </div>
        <div className="user-zone">
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
            <h1>{projectData.projectName || `프로젝트 ${projectId}`}</h1>
            <button
              className="icon-button"
              disabled
              title="프로젝트명 수정 API 연결 후 사용할 수 있습니다."
              type="button"
            >
              ✎
            </button>
            <Badge>{selectionFinalized ? "검토 완료" : "견적 검토"}</Badge>
          </div>
          <div className="project-actions">
            <button className="button action-secondary" onClick={onGoProjects} type="button">
              프로젝트 목록
            </button>
            <button
              className={selectionFinalized ? "button button-green" : "button button-blue"}
              disabled
              title="상태는 현재 화면 진행에 따라 자동 반영됩니다."
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
            <strong>{selectionFinalized ? "검토 완료" : projectData.currentStage}</strong>
          </div>
          <div className="meta-item">
            <span>예산/프리셋</span>
            <strong>
              {projectData.budgetAmount ? `${projectData.budgetAmount}원` : "예산 미정"} ·{" "}
              {projectData.reviewPreset}
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
              <b>실패 상태 UI 점검용 mock 데이터</b>
              <span>업로드 실패, OCR 일부 실패, 파싱 실패, 총액 미확정, LLM fallback이 어떻게 보이는지 확인하는 프로젝트입니다.</span>
            </div>
            <div className="failure-state-row">
              <Badge tone="red">업로드 실패</Badge>
              <Badge tone="red">OCR 일부 실패</Badge>
              <Badge tone="red">수정 필요</Badge>
              <Badge tone="gray">총액 미확정</Badge>
              <Badge tone="orange">LLM fallback</Badge>
            </div>
          </section>
        )}

        {compareState === "ready" && (
        <div className="content-grid">
          <div className="main-column">
            <section className="panel supplier-panel">
              <div className="panel-title-row">
                <div className="panel-title">
                  공급사 매칭 현황 ({supplierCount}/{supplierCount}) <span>ⓘ</span>
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
                    <div className="supplier-row">
                      <div className="supplier-name">
                        <span className="rank">{supplier.rank}</span>
                        <span className={`supplier-logo ${supplier.logoClass}`}>{supplier.logo}</span>
                        <b>{supplier.name}</b>
                        {supplier.recommended && <Badge>AI 추천</Badge>}
                      </div>
                      <div className="fit">
                        적합도 <b className={supplier.fitClass}>{supplier.fit}%</b>
                      </div>
                    </div>
                    <div className="supplier-cost-badges">
                      <small>비용 조건</small>
                      <div className="badge-row">
                        {getSupplierCostBadge(supplier, "설치 공사비", "설치 공사비")}
                        {getSupplierCostBadge(supplier, "출장비", "출장비")}
                      </div>
                    </div>
                    <p className="supplier-card-summary">{cardSummary}</p>
                    <div className="supplier-foot">
                      <div>
                        <small>제출 상태</small>
                        <span className={isFailureScenario && supplier.id === "c" ? "submitted submitted-warning" : "submitted"}>
                          {isFailureScenario && supplier.id === "c"
                            ? "△ OCR 일부 실패 · 2개 항목 수정 필요"
                            : `○ ${supplier.submitted}`}
                        </span>
                      </div>
                      <div>
                        <small>과거 성과</small>
                        <div className="badge-row">
                          {isFailureScenario && supplier.id === "b" && <Badge tone="orange">파싱 신뢰도 낮음</Badge>}
                          {isFailureScenario && supplier.id === "c" && <Badge tone="gray">총액 미확정</Badge>}
                          {supplier.badges
                            .filter((badge) => badge !== "프리미엄 파트너")
                            .map((badge, index) => (
                            <Badge tone={index === 0 ? "orange" : "green"} key={badge}>
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
                        <th className={supplier.recommended ? "ai-col" : ""} key={supplier.id}>
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
                      <b>{(openSections[section.id] ?? defaultOpenSections[section.id]) ? "⌃" : "›"}</b>
                    </button>

                    {(openSections[section.id] ?? defaultOpenSections[section.id]) && (
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
                    <b>{(openSections.total ?? defaultOpenSections.total) ? "⌃" : "›"}</b>
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
                                  <span className="vat-note">VAT 별도</span>
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
              <h2>✦ AI 근거 요약</h2>
              {explanationIsFallback && (
                <div className="fallback-notice">
                  AI 설명 생성이 일시적으로 실패해 기본 규칙 기반 요약을 표시합니다.
                </div>
              )}
              <p>{overallSummary}</p>
              <button className="side-title side-title-button" onClick={() => setProsOpen((open) => !open)} type="button">
                <span>공급사 장단점</span>
                <b>{prosOpen ? "⌃" : "›"}</b>
              </button>
              {prosOpen && (
                <div className="pros-list">
                  {supplierExplanations.map((supplier) => (
                    <div className="pros-item" key={supplier.quoteId ?? supplier.vendorName}>
                      <div className="pros-brand">
                        <span className={`supplier-logo ${supplier.logoClass}`}>{supplier.logo}</span>
                        <b>{supplier.vendorName}</b>
                      </div>
                      <div>
                        <div>장점: {supplier.strengths}</div>
                        <div>단점: {supplier.weaknesses}</div>
                      </div>
                      <span>›</span>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <div className="side-split">
              <section className="panel compact-panel">
                <h3>검토 메모 <small>(내부용)</small></h3>
                <div className="compact-panel-body">
                  <textarea
                    className={isMemoEditing ? "" : "memo-readonly"}
                    onChange={(event) =>
                      setDraftMemo(event.target.value.slice(0, maxMemoLength))
                    }
                    placeholder="검토 메모를 입력하세요...&#10;(내부 공유용입니다.)"
                    readOnly={!isMemoEditing}
                    value={memoValue}
                  />
                  <div className="counter">
                    {memoValue.length} / {maxMemoLength.toLocaleString()}
                  </div>
                </div>
                <div className="memo-actions">
                  <button className="button" onClick={startMemoEdit} type="button">
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
              <h3>최종 선정 <small>(담당자 선택)</small></h3>
              <div className="choice-grid">
                {selectableVendors.map((supplier) => (
                  <label
                    className={`choice-card ${selectedVendor === supplier.name ? "selected" : ""}`}
                    key={supplier.name}
                  >
                    <input
                      checked={selectedVendor === supplier.name}
                      onChange={() => setSelectedVendor(supplier.name)}
                      type="radio"
                    />
                    <b>{supplier.name}</b>
                    {supplier.recommended && (
                      <div>
                        <Badge>추천</Badge>
                        <Badge>AI 추천</Badge>
                      </div>
                    )}
                  </label>
                ))}
              </div>
              <div className="notice">
                <b>유의 사항</b>
                <span>
                  본 비교는 AI가 추출한 정보 기반입니다. 최종 선정 전 모든 항목을 반드시 확인하고,
                  필요 시 공급사에 추가 확인하시기 바랍니다.
                </span>
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
          disabled
          title="검토 메모 저장은 우측 메모 영역에서만 가능합니다."
          type="button"
        >
          ▣ 임시 저장
        </button>
        <button
          className="button action-secondary"
          disabled
          title="고객 보고서 기능은 이번 통합 범위 밖이라 아직 사용할 수 없습니다."
          type="button"
        >
          고객 보고서로 내보내기
        </button>
        <button
          className={selectionFinalized ? "button selection-complete-button" : "button action-primary"}
          disabled={selectionFinalized || !selectedVendor}
          onClick={() => setConfirmOpen(true)}
          type="button"
        >
          {selectionFinalized ? "선정 완료" : "◎ 최종 선정 확정"}
        </button>
      </footer>
      )}
      {confirmOpen && (
        <div className="confirm-layer" role="presentation">
          <div className="confirm-dialog" role="dialog" aria-modal="true" aria-label="최종 선정 확인">
            <h2>최종 선정 업체 확정</h2>
            <p>{selectedVendor}를 최종 선정 업체로 확정하시겠습니까?</p>
            <div className="confirm-actions">
              <button className="button" onClick={() => setConfirmOpen(false)} type="button">
                취소
              </button>
              <button className="button action-primary" onClick={confirmSelection} type="button">
                확정
              </button>
            </div>
          </div>
        </div>
      )}
      {toastVisible && (
        <div className="selection-toast" role="status">
          {selectedVendor}가 최종 선정 업체로 확정되었습니다.
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
          <b>{selectedVendor}가 최종 선정 업체로 확정되었습니다.</b>
          <span>프로젝트 상태가 검토 완료로 변경되었습니다.</span>
          <div>
            <button className="button" onClick={onGoProjects} type="button">프로젝트 목록으로 이동</button>
          </div>
        </div>
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
          <h2>견적 비교 데이터를 불러오는 중입니다</h2>
          <p>공급사 정보, 견적 항목, AI 근거 요약을 준비하고 있습니다.</p>
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
          <h2>견적 비교 데이터를 불러오지 못했습니다</h2>
          <p>{message}</p>
          <div className="state-actions">
            <button className="button action-primary" onClick={onRetry} type="button">
              다시 시도
            </button>
            <button className="button action-secondary" onClick={onGoProjects} type="button">
              프로젝트 목록으로 이동
            </button>
          </div>
        </div>
      </div>
      <div className="error-guide">
        <b>확인할 항목</b>
        <span>API 응답 형식, 프로젝트 ID, 업로드된 견적서 상태, 네트워크 연결을 확인해주세요.</span>
      </div>
    </section>
  );
}
