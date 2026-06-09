import { useEffect, useMemo, useState } from 'react';
import Badge from '../components/Badge';
import ProjectStepTabs from '../components/ProjectStepTabs';
import ReviewDrawer from '../components/ReviewDrawer';
import useCompareResult from '../hooks/useCompareResult';
import useExplanationResult from '../hooks/useExplanationResult';
import { getStatusUi } from '../utils/statusMap';

export default function DashboardPage({
  projectData,
  onGoProjects,
  onGoQuoteWaiting,
  onGoReport,
}) {
  const [selectedVendor, setSelectedVendor] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const isFailureScenario = Boolean(projectData.failureScenario);
  const projectId = projectData.projectId || "PV-2025-0421";
  const {
    compareErrorMessage,
    compareState,
    comparisonSections,
    suppliers,
    totalRows,
  } = useCompareResult(projectData);
  const {
    isFallback: explanationIsFallback,
    overallSummary,
    supplierExplanations,
  } = useExplanationResult(projectData, suppliers);
  const mergedSuppliers = useMemo(() => {
    if (!supplierExplanations.length) return suppliers;
    return [...suppliers]
      .map((supplier) => {
        const exp = supplierExplanations.find((e) => e.vendorName === supplier.name);
        return {
          ...supplier,
          rank: exp?.rank ?? supplier.rank,
          cardSummary: exp?.cardSummary ?? "",
        };
      })
      .sort((a, b) => a.rank - b.rank);
  }, [suppliers, supplierExplanations]);

  useEffect(() => {
    if (selectedVendor) return;
    const rank1 = supplierExplanations.find((e) => e.rank === 1);
    if (rank1) {
      setSelectedVendor(rank1.vendorName);
    } else if (suppliers.length > 0) {
      setSelectedVendor(suppliers[0].name);
    }
  }, [supplierExplanations, suppliers]);

  const defaultOpenSections = useMemo(
    () => comparisonSections.reduce((sections, section) => ({
      ...sections,
      [section.id]: isFailureScenario ? true : section.defaultOpen,
    }), { total: true }),
    [comparisonSections, isFailureScenario]
  );
  const [openSections, setOpenSections] = useState(defaultOpenSections);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [selectionFinalized, setSelectionFinalized] = useState(false);
  const [toastVisible, setToastVisible] = useState(false);
  const [followupVisible, setFollowupVisible] = useState(false);
  const [prosOpen, setProsOpen] = useState(true);

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

  const confirmSelection = () => {
    setConfirmOpen(false);
    setSelectionFinalized(true);
    setFollowupVisible(true);
    setToastVisible(true);
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
          <div className="bell">♧<span>3</span></div>
          <div className="help">?</div>
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
            <h1>프로젝트 {projectId}</h1>
            <button className="icon-button" type="button">✎</button>
            <Badge>{projectData.projectName}</Badge>
          </div>
          <div className="project-actions">
            <button className="button action-secondary" onClick={onGoProjects} type="button">
              프로젝트 목록
            </button>
            <button className="button action-primary project-create" onClick={() => setDrawerOpen(true)} type="button">
              + 검토 건 생성
            </button>
            <button className={selectionFinalized ? "button button-green" : "button button-blue"} type="button">
              {selectionFinalized ? "검토 완료" : "검토 진행 중"}
            </button>
            <button className="button" type="button">D-2</button>
            <button className="button button-green" type="button">정시 진행</button>
          </div>
        </section>

        <ProjectStepTabs activeStep={4} onGoQuoteWaiting={onGoQuoteWaiting} />

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
              <div className="panel-title">
                공급사 매칭 현황 (3/3) <span>ⓘ</span>
              </div>
              <div className="supplier-grid">
                {mergedSuppliers.map((supplier) => (
                  <article
                    className={`supplier-card ${supplier.recommended ? "recommended" : ""}`}
                    key={supplier.name}
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
                    <p>{supplier.cardSummary || supplier.summary}</p>
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
                          {supplier.badges.map((badge, index) => (
                            <Badge tone={index === 0 ? "orange" : "green"} key={badge}>
                              {badge}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="panel compare-panel">
              <div className="compare-header">
                <div>
                  <b>견적 비교</b>
                  <span>(추출 기준일: 2025-04-22)</span>
                </div>
                <button className="button button-small" type="button">⊙ 행 근거 보기</button>
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
                      {mergedSuppliers.map((supplier) => (
                        <th className={supplier.recommended ? "ai-col" : ""} key={supplier.name}>
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
                              {mergedSuppliers.map((supplier) => (
                                <td key={supplier.name + row.label}>
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
                                <Badge tone="blue">핵심 비교</Badge>
                              </div>
                            </td>
                            {mergedSuppliers.map((supplier) => (
                              <td key={supplier.name + row.label}>
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
                <h3>근거 출처 <small>(비교 행 연결)</small></h3>
                <p>3. 단가(공급가) <a>A-03, B-03, C-03</a></p>
                <p>7. 납기 <a>A-07, B-07, C-07</a></p>
                <p>8. 품질 보증 <a>A-08, B-08, C-08</a></p>
                <button className="button full" type="button">전체 근거 보기</button>
              </section>
              <section className="panel compact-panel">
                <h3>검토 메모 <small>(내부용)</small></h3>
                <textarea placeholder="검토 메모를 입력하세요...&#10;(내부 공유용입니다.)" />
                <div className="counter">0 / 1,000</div>
              </section>
            </div>

            <section className="panel final-panel">
              <h3>최종 선정 <small>(담당자 선택)</small></h3>
              <div className="choice-grid">
                {mergedSuppliers.map((supplier) => (
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
                        <Badge>AI 추천 / 최저가</Badge>
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

            <section className="panel export-panel">
              <h3>보고서/내보내기</h3>
              <div>
                <button className="button full" type="button">비교표 다운로드 (Excel)</button>
                <button className="button full" onClick={onGoReport} type="button">고객 보고서 미리보기</button>
              </div>
            </section>
          </aside>
        </div>
        )}
      </main>

      {compareState === "ready" && (
      <footer className="bottom-actions">
        <button className="button action-secondary" type="button">▣ 임시 저장</button>
        <button className="button action-secondary" onClick={onGoReport} type="button">□ 고객 보고서로 내보내기</button>
        <button
          className={selectionFinalized ? "button selection-complete-button" : "button action-primary"}
          disabled={selectionFinalized}
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
            <button className="button action-primary" onClick={onGoReport} type="button">고객 보고서 미리보기</button>
          </div>
        </div>
      )}
      <ReviewDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
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
