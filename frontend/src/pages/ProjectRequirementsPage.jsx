import { useEffect, useRef, useState } from "react";
import AutoSaveStatus from "../components/AutoSaveStatus";
import FlowTopbar from "../components/FlowTopbar";
import ProjectDetailHeader from "../components/ProjectDetailHeader";
import ProjectStepTabs from "../components/ProjectStepTabs";
import { formatNumberInput } from "../utils/formatters";
import {
  buildProjectRequestPayload,
  formatProjectSolutions,
  normalizeProjectSolutions,
} from "../utils/projectRequestText";
import SolutionTagPicker, { SolutionTagChipList } from "../components/SolutionTagPicker";

const priorityOptions = ["최저가", "납기", "보증/A/S", "스펙", "균형 추천"];

function isReviewPresetSelected(current, option) {
  const normalized = String(current ?? "")
    .replace(/ 우선$/, "")
    .trim();
  return normalized === option;
}

export default function ProjectRequirementsPage({
  projectData,
  onBack,
  onNext,
  onProjectDataChange,
  onAutoSave,
  isPartnerMatchingLoading = false,
  onGoHome,
}) {
  const autoSaveTimerRef = useRef(null);
  const autoSaveStatusTimerRef = useRef(null);
  const lastAutoSavePayloadRef = useRef("");
  const [autoSaveStatus, setAutoSaveStatus] = useState("idle");

  const showAutoSaveStatus = (status) => {
    if (autoSaveStatusTimerRef.current) {
      clearTimeout(autoSaveStatusTimerRef.current);
      autoSaveStatusTimerRef.current = null;
    }

    setAutoSaveStatus(status);

    if (status === "saved" || status === "error") {
      autoSaveStatusTimerRef.current = setTimeout(() => {
        setAutoSaveStatus("idle");
        autoSaveStatusTimerRef.current = null;
      }, status === "saved" ? 1800 : 3000);
    }
  };

  useEffect(() => {
    if (!onAutoSave) return;

    const payload = buildProjectRequestPayload(projectData);
    const payloadSnapshot = JSON.stringify(payload);

    if (!lastAutoSavePayloadRef.current) {
      lastAutoSavePayloadRef.current = payloadSnapshot;
      return;
    }

    if (lastAutoSavePayloadRef.current === payloadSnapshot) return;

    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }

    autoSaveTimerRef.current = setTimeout(async () => {
      showAutoSaveStatus("saving");
      try {
        await onAutoSave(payload);
        lastAutoSavePayloadRef.current = payloadSnapshot;
        showAutoSaveStatus("saved");
      } catch (error) {
        console.error("? ? ?:", error);
        showAutoSaveStatus("error");
      }
    }, 1200);

    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
      if (autoSaveStatusTimerRef.current) {
        clearTimeout(autoSaveStatusTimerRef.current);
      }
    };
  }, [
    onAutoSave,
    projectData.companyName,
    projectData.location,
    projectData.projectDate,
    projectData.projectName,
    projectData.usage,
    projectData.displaySize,
    projectData.displayUnit,
    projectData.displayWidth,
    projectData.displayHeight,
    projectData.displayInch,
    projectData.quantity,
    projectData.operationTime,
    projectData.solutions,
    projectData.budgetAmount,
    projectData.currentStage,
    projectData.reviewPreset,
    projectData.otherConditions,
    projectData.attachmentMemo,
  ]);

  const checks = getMatchingChecks(projectData);
  const readiness = getReadinessScore(projectData, checks);
  const readinessMessage = getReadinessMessage(readiness, checks);
  const displayUnit = projectData.displayUnit || inferDisplayUnit(projectData.displaySize);
  const isDisplayInch = displayUnit === "inch";
  const displayWidthValue =
    projectData.displayWidth ??
    parseDisplayDimension(projectData.displaySize, "width");
  const displayHeightValue =
    projectData.displayHeight ??
    parseDisplayDimension(projectData.displaySize, "height");
  const displayInchValue =
    projectData.displayInch ?? parseDisplayInch(projectData.displaySize);

  const selectedSolutions = normalizeProjectSolutions(projectData);

  const updateField = (field, value) => {
    onProjectDataChange((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const updateDisplaySize = (nextValues) => {
    onProjectDataChange((current) => {
      const nextUnit =
        nextValues.displayUnit ?? current.displayUnit ?? displayUnit;
      const nextWidth =
        nextValues.displayWidth ?? current.displayWidth ?? displayWidthValue;
      const nextHeight =
        nextValues.displayHeight ?? current.displayHeight ?? displayHeightValue;
      const nextInch =
        nextValues.displayInch ?? current.displayInch ?? displayInchValue;
      const nextDisplaySize =
        nextUnit === "inch"
          ? formatInchSize(nextInch)
          : formatDimensionSize(nextWidth, nextHeight, nextUnit);

      return {
        ...current,
        displayUnit: nextUnit,
        displayWidth: nextUnit === "inch" ? "" : nextWidth,
        displayHeight: nextUnit === "inch" ? "" : nextHeight,
        displayInch: nextUnit === "inch" ? nextInch : "",
        displaySize: nextDisplaySize,
      };
    });
  };

  return (
    <div className="flow-page requirements-page">
      <FlowTopbar
        onHome={onGoHome}
        trail="프로젝트 상세 > 요구사항"
        action={
          <>
            <AutoSaveStatus status={autoSaveStatus} />
            <button className="button action-secondary" onClick={onBack} type="button">
              목록
            </button>
            <div className="avatar" />
            <div className="user-name">
              <b>김담당자</b>
              <small>구매검토팀</small>
            </div>
          </>
        }
      />

      <main className="requirements-main">
        <ProjectDetailHeader
          onBack={onBack}
          projectName={projectData.projectName || "새 프로젝트"}
        />

        <ProjectStepTabs activeStep={1} onGoPartnerMatching={onNext} />

        <section className="requirements-layout">
          <form className="requirements-form">
            <div className="requirements-section-title">
              <div>
                <h2>요구사항 작성</h2>
                <p>발주사 기본 정보와 디스플레이 요구사항을 기준에 맞춰 정리해요.</p>
              </div>
            </div>

            <section className="requirement-input-block">
              <div className="requirement-block-title">
                <span>1</span>
                <div>
                  <b>발주사 및 기본 정보</b>
                  <small>회사명, 설치 위치, 프로젝트명과 활용 목적을 입력해요.</small>
                </div>
              </div>
              <div className="requirements-form-grid">
                <label>
                  <span>회사명 *</span>
                  <input
                    onChange={(event) => updateField("companyName", event.target.value)}
                    placeholder="예: Microsoft"
                    value={projectData.companyName || ""}
                  />
                </label>
                <label>
                  <span>설치 위치 *</span>
                  <input
                    onChange={(event) => updateField("location", event.target.value)}
                    placeholder="예: 수원사업장 본관 로비"
                    value={projectData.location || ""}
                  />
                </label>
                <label>
                  <span>프로젝트명</span>
                  <input
                    onChange={(event) => updateField("projectName", event.target.value)}
                    placeholder="예: 본사 로비 사이니지 구축"
                    value={projectData.projectName || ""}
                  />
                </label>
                <label>
                  <span>프로젝트 일정</span>
                  <input
                    onChange={(event) => updateField("projectDate", event.target.value)}
                    type="date"
                    value={projectData.projectDate || ""}
                  />
                </label>
              </div>
              <label>
                <span>활용 용도 및 디스플레이 요구사항 *</span>
                <textarea
                  onChange={(event) => updateField("usage", event.target.value)}
                  placeholder="예: 사내 브리핑/방문객 안내용 디스플레이, 설치 환경, 화면 밝기, 운영 조건 등을 입력해주세요."
                  value={projectData.usage || ""}
                />
              </label>
            </section>

            <section className="requirement-input-block">
              <div className="requirement-block-title">
                <span>2</span>
                <div>
                  <b>디스플레이 스펙</b>
                  <small>화면 크기, 수량, 운영 조건과 카테고리를 입력해요.</small>
                </div>
              </div>
              <div className="requirements-form-grid">
                <label className="display-size-field">
                  <span>디스플레이 크기</span>
                  <div className={isDisplayInch ? "display-size-control inch" : "display-size-control dimension"}>
                    {isDisplayInch ? (
                      <input
                        inputMode="decimal"
                        onChange={(event) => updateDisplaySize({ displayInch: event.target.value.trim() })}
                        placeholder="예: 55"
                        value={displayInchValue}
                      />
                    ) : (
                      <>
                        <input
                          inputMode="decimal"
                          onChange={(event) => updateDisplaySize({ displayWidth: event.target.value.trim() })}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") {
                              event.preventDefault();
                              event.currentTarget.nextElementSibling?.focus();
                            }
                          }}
                          placeholder="W 12000"
                          value={displayWidthValue}
                        />
                        <input
                          inputMode="decimal"
                          onChange={(event) => updateDisplaySize({ displayHeight: event.target.value.trim() })}
                          placeholder="H 3000"
                          value={displayHeightValue}
                        />
                      </>
                    )}
                    <select
                      aria-label="display size unit"
                      onChange={(event) => updateDisplaySize({ displayUnit: event.target.value })}
                      value={displayUnit}
                    >
                      <option value="mm">mm</option>
                      <option value="cm">cm</option>
                      <option value="m">m</option>
                      <option value="inch">인치</option>
                    </select>
                  </div>
                </label>
                <label>
                  <span>수량</span>
                  <input
                    inputMode="numeric"
                    onChange={(event) => updateField("quantity", event.target.value)}
                    placeholder="예: 10"
                    value={projectData.quantity || ""}
                  />
                </label>
                <label>
                  <span>운영 시간</span>
                  <select
                    onChange={(event) => updateField("operationTime", event.target.value)}
                    value={projectData.operationTime || "24/7"}
                  >
                    <option>업무 시간</option>
                    <option>12시간</option>
                    <option>24/7</option>
                    <option>이벤트 기간 지정</option>
                  </select>
                </label>
                <label className="requirements-solution-field">
                  <span>솔루션</span>
                  <SolutionTagPicker
                    onChange={(solutions) => updateField("solutions", solutions)}
                    showChips={false}
                    value={selectedSolutions}
                  />
                </label>
                {selectedSolutions.length > 0 && (
                  <>
                    <div aria-hidden="true" className="requirements-form-grid-spacer" />
                    <div className="requirements-solution-chips">
                      <SolutionTagChipList
                        onChange={(solutions) => updateField("solutions", solutions)}
                        value={selectedSolutions}
                      />
                    </div>
                  </>
                )}
              </div>
            </section>

            <section className="requirement-input-block">
              <div className="requirement-block-title">
                <span>3</span>
                <div>
                  <b>예산과 검토 기준</b>
                  <small>매칭 우선순위와 요청 가능 범위를 판단해요.</small>
                </div>
              </div>
              <div className="requirements-form-grid">
                <label>
                  <span>예산 상한</span>
                  <div className="requirements-money-field">
                    <input
                      inputMode="numeric"
                      onChange={(event) =>
                        updateField("budgetAmount", formatNumberInput(event.target.value))
                      }
                      placeholder="예: 120,000,000"
                      value={projectData.budgetAmount || ""}
                    />
                    <em>원</em>
                  </div>
                </label>
                <div className="requirements-priority-field">
                  <span>매칭 우선순위</span>
                  <div className="priority-chip-row">
                    {priorityOptions.map((option) => (
                      <button
                        className={
                          isReviewPresetSelected(projectData.reviewPreset, option)
                            ? "priority-chip active"
                            : "priority-chip"
                        }
                        key={option}
                        onClick={() => updateField("reviewPreset", option)}
                        type="button"
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </section>

            <section className="requirement-input-block">
              <div className="requirement-block-title">
                <span>4</span>
                <div>
                  <b>추가 메모</b>
                  <small>A/S, 납기, 설치 제한, 첨부 자료에 대한 메모를 남겨요.</small>
                </div>
              </div>
              <label>
                <span>추가 요청사항</span>
                <textarea
                  onChange={(event) => updateField("otherConditions", event.target.value)}
                  placeholder="A/S, 납기, 설치 제한, 현장 실측 필요 여부 등을 적어주세요."
                  value={projectData.otherConditions || ""}
                />
              </label>
            </section>
          </form>

          <aside className="matching-check-panel refined panel-sticky">
            <div className="requirements-section-title">
              <div>
                <h2>매칭 가능성 체크</h2>
                <p>현재 입력값 기준 사전 검증 결과예요.</p>
              </div>
            </div>

            <div className="matching-check-list">
              {checks.map((check) => (
                <article className={`matching-check ${check.level}`} key={check.title}>
                  <span>{check.level === "ok" ? "✓" : "!"}</span>
                  <div>
                    <strong>{check.title}</strong>
                    <p>{check.message}</p>
                  </div>
                </article>
              ))}
            </div>

            <div className="matching-readiness">
              <div>
                <b>매칭 준비도</b>
                <strong>{readiness}%</strong>
              </div>
              <div className="matching-readiness-bar">
                <span style={{ width: `${readiness}%` }} />
              </div>
              <p>{readinessMessage}</p>
            </div>

            <div className="matching-next-guide refined">
              <b>다음 단계 안내</b>
              <p>
                파트너 매칭 화면에서 AI 추천 순위와 적합도 점수를 확인하고, 견적 요청을
                보낼 공급사를 선택할 수 있어요.
              </p>
            </div>
          </aside>
        </section>
      </main>

      <footer className="requirements-bottom-actions">
        <span>요구사항은 빈 값이어도 저장할 수 있어요.</span>
        <div>
          <button className="button action-secondary" onClick={onBack} type="button">
            이전
          </button>
          <button
            className="button action-primary"
            disabled={isPartnerMatchingLoading}
            onClick={onNext}
            type="button"
          >
            {isPartnerMatchingLoading ? "파트너 매칭 준비 중..." : "다음: 파트너 매칭"}
          </button>
        </div>
      </footer>
    </div>
  );
}

function hasDisplayDimension(data) {
  return Boolean(
    data.displaySize?.trim() ||
      data.displayInch?.trim() ||
      (data.displayWidth?.trim() && data.displayHeight?.trim()),
  );
}

function getMatchingChecks(data) {
  const stage = data.currentStage || "";
  const hasCompany = Boolean(data.companyName?.trim());
  const hasLocation = Boolean(data.location?.trim());
  const hasUsage = Boolean(data.usage?.trim());

  const requiredFilledCount = [hasCompany, hasLocation, hasUsage].filter(Boolean).length;

  return [
    {
      title: "필수값 충족",
      weight: 24,
      level: requiredFilledCount === 3 ? "ok" : "warn",
      message:
        requiredFilledCount === 3
          ? "회사명, 설치 위치, 활용 목적이 입력됐어요."
          : `회사명, 설치 위치, 활용 목적 중 ${requiredFilledCount}/3개가 입력됐어요.`,
    },
    {
      title: "정보 탐색 단계 확인 필요",
      weight: 16,
      level: stage.includes("정보 탐색") ? "warn" : "ok",
      message: stage.includes("정보 탐색")
        ? "정보 탐색 단계는 자동 매칭이 제한될 수 있어요."
        : "현재 단계 기준으로 파트너 매칭 검토가 가능해요.",
    },
  ];
}

function getFieldReadinessScore(data) {
  const hasCompany = Boolean(data.companyName?.trim());
  const hasLocation = Boolean(data.location?.trim());
  const hasUsage = Boolean(data.usage?.trim());
  const hasProjectName = Boolean(data.projectName?.trim());
  const hasProjectDate = Boolean(data.projectDate?.trim());
  const hasDisplay = hasDisplayDimension(data);
  const hasQuantity = Boolean(data.quantity?.trim());
  const hasBudget = Boolean(data.budgetAmount?.trim());
  const hasSolutions = normalizeProjectSolutions(data).length > 0;
  const hasReviewPreset = Boolean(data.reviewPreset?.trim());

  const items = [
    { filled: hasCompany, weight: 14 },
    { filled: hasLocation, weight: 14 },
    { filled: hasUsage, weight: 14 },
    { filled: hasProjectName, weight: 6 },
    { filled: hasProjectDate, weight: 8 },
    { filled: hasDisplay, weight: 16 },
    { filled: hasQuantity, weight: 10 },
    { filled: hasBudget, weight: 14 },
    { filled: hasSolutions, weight: 6 },
    { filled: hasReviewPreset, weight: 8 },
  ];

  const totalWeight = items.reduce((sum, item) => sum + item.weight, 0);
  const earnedWeight = items.reduce(
    (sum, item) => sum + (item.filled ? item.weight : 0),
    0,
  );

  return totalWeight > 0 ? Math.round((earnedWeight / totalWeight) * 100) : 0;
}

function getChecksReadinessScore(checks) {
  if (!checks.length) return 0;

  const earnedWeight = checks.reduce(
    (sum, check) => sum + (check.level === "ok" ? check.weight : 0),
    0,
  );
  const totalWeight = checks.reduce((sum, check) => sum + check.weight, 0);

  return totalWeight > 0 ? Math.round((earnedWeight / totalWeight) * 100) : 0;
}

function getReadinessScore(data, checks) {
  const fieldScore = getFieldReadinessScore(data);
  const checkScore = getChecksReadinessScore(checks);

  return Math.round(fieldScore * 0.55 + checkScore * 0.45);
}

function getReadinessMessage(readiness, checks) {
  const warnCount = checks.filter((check) => check.level !== "ok").length;

  if (readiness >= 85 && warnCount === 0) {
    return "입력과 사전 검증이 충분해요. 지금 상태로 파트너 매칭을 진행해도 좋아요.";
  }
  if (readiness >= 60) {
    return "기본 조건은 갖춰졌어요. 남은 항목을 보완하면 추천 정확도가 더 높아져요.";
  }
  if (warnCount > 0) {
    return "매칭 가능성 체크에서 확인이 필요한 항목이 있어요. 경고 항목을 먼저 보완해 주세요.";
  }
  return "필수 정보와 스펙/예산을 입력하면 매칭 준비도가 올라가요.";
}

function inferDisplayUnit(displaySize = "") {
  if (/인치|inch/i.test(displaySize)) return "inch";
  const unitMatch = displaySize?.match(/\b(mm|cm|m)\b/i);
  return unitMatch?.[1]?.toLowerCase() || "mm";
}

function parseDisplayInch(displaySize = "") {
  const match = displaySize?.match(/([\d,.]+)\s*(?:인치|inch)/i);
  return match?.[1] || "";
}

function parseDisplayDimension(displaySize = "", axis) {
  const axisPattern = axis === "width" ? /W\s*([\d,.]+)/i : /H\s*([\d,.]+)/i;
  const axisMatch = displaySize?.match(axisPattern);
  if (axisMatch?.[1]) return axisMatch[1];

  const pairMatch = displaySize?.match(/([\d,.]+)\s*(?:x|×)\s*([\d,.]+)/i);
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

function getScheduleState(value) {
  if (!value) {
    return {
      level: "warn",
      message: "일정이 없으면 납기 기준 매칭 정확도가 낮아져요.",
    };
  }

  const target = new Date(value);
  if (Number.isNaN(target.getTime())) {
    return {
      level: "warn",
      message: "일정 형식을 확인해 주세요.",
    };
  }

  const sixMonthsLater = new Date();
  sixMonthsLater.setMonth(sixMonthsLater.getMonth() + 6);

  if (target > sixMonthsLater) {
    return {
      level: "warn",
      message: "일정이 6개월을 초과해 우선 매칭 보류 대상으로 표시돼요.",
    };
  }

  return {
    level: "ok",
    message: "프로젝트 기간이 가능한 범위예요.",
  };
}
