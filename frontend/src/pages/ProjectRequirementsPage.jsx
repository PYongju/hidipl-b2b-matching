import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectStepTabs from "../components/ProjectStepTabs";

const priorityOptions = ["최저가 우선", "납기 우선", "보증/A/S 우선", "스펙 우선", "균형 추천"];

export default function ProjectRequirementsPage({
  projectData,
  onBack,
  onNext,
  onProjectDataChange,
  isPartnerMatchingLoading = false,
}) {
  const checks = getMatchingChecks(projectData);
  const readiness = getReadinessScore(checks);
  const displayUnit = projectData.displayUnit || inferDisplayUnit(projectData.displaySize);
  const isDisplayInch = displayUnit === "inch";
  const displayWidthValue = projectData.displayWidth ?? parseDisplayDimension(projectData.displaySize, "width");
  const displayHeightValue = projectData.displayHeight ?? parseDisplayDimension(projectData.displaySize, "height");
  const displayInchValue = projectData.displayInch ?? parseDisplayInch(projectData.displaySize);

  const updateField = (field, value) => {
    onProjectDataChange((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const updateDisplaySize = (nextValues) => {
    onProjectDataChange((current) => {
      const nextUnit = nextValues.displayUnit ?? current.displayUnit ?? displayUnit;
      const nextWidth = nextValues.displayWidth ?? current.displayWidth ?? displayWidthValue;
      const nextHeight = nextValues.displayHeight ?? current.displayHeight ?? displayHeightValue;
      const nextInch = nextValues.displayInch ?? current.displayInch ?? displayInchValue;
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
        trail="프로젝트 상세 > 요구사항"
        action={
          <>
            <button className="button action-secondary" onClick={onBack} type="button">
              목록
            </button>
            <div className="avatar" />
            <div className="user-name">
              <b>김담당자</b>
              <small>구매팀</small>
            </div>
          </>
        }
      />

      <main className="requirements-main">
        <section className="requirements-header">
          <div>
            <button className="partner-back" onClick={onBack} type="button" aria-label="목록으로">
              ‹
            </button>
            <div>
              <p>프로젝트 상세</p>
              <h1>{projectData.projectName || "신규 검토 건"}</h1>
            </div>
          </div>
          <div className="requirements-status">
            <Badge tone="gray">{projectData.currentStage || "요구사항"}</Badge>
            <span>저장됨</span>
            <span>마지막 수정자 김담당자</span>
          </div>
        </section>

        <ProjectStepTabs activeStep={1} onGoPartnerMatching={onNext} />

        <section className="requirements-layout">
          <form className="requirements-form">
            <div className="requirements-section-title">
              <div>
                <h2>요구사항 작성</h2>
                <p>발주사 기본 정보와 디스플레이 요구사항을 기준에 맞춰 정리합니다.</p>
              </div>
            </div>

            <section className="requirement-input-block">
              <div className="requirement-block-title">
                <span>1</span>
                <div>
                  <b>발주사 및 기본 정보</b>
                  <small>회사명, 설치 위치, 프로젝트명과 활용 목적을 입력합니다.</small>
                </div>
              </div>
              <div className="requirements-form-grid">
                <label>
                  <span>회사명 *</span>
                  <input
                    onChange={(event) => updateField("companyName", event.target.value)}
                    placeholder="예: 삼성전자"
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
                <span>활용 용도 및 디스플레이 요구사항</span>
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
                  <small>화면 크기, 수량, 운영 조건과 카테고리를 입력합니다.</small>
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
                <label>
                  <span>카테고리</span>
                  <select
                    onChange={(event) => updateField("category", event.target.value)}
                    value={projectData.category || "디스플레이"}
                  >
                    <option>디스플레이</option>
                    <option>사이니지</option>
                    <option>키오스크</option>
                    <option>화상회의/회의실</option>
                    <option>기타</option>
                  </select>
                </label>
              </div>
            </section>

            <section className="requirement-input-block">
              <div className="requirement-block-title">
                <span>3</span>
                <div>
                  <b>예산과 검토 기준</b>
                  <small>매칭 우선순위와 요청 가능 범위를 판단합니다.</small>
                </div>
              </div>
              <div className="requirements-form-grid">
                <label>
                  <span>예산 상한</span>
                  <div className="requirements-money-field">
                    <input
                      inputMode="numeric"
                      onChange={(event) => updateField("budgetAmount", event.target.value)}
                      placeholder="예: 120,000,000"
                      value={projectData.budgetAmount || ""}
                    />
                    <em>원</em>
                  </div>
                </label>
                <label>
                  <span>현재 단계</span>
                  <select
                    onChange={(event) => updateField("currentStage", event.target.value)}
                    value={projectData.currentStage || "요구사항"}
                  >
                    <option>정보 탐색</option>
                    <option>요구사항</option>
                    <option>파트너 매칭 필요</option>
                    <option>견적 요청 전</option>
                    <option>견적 수신중</option>
                    <option>비교 검토중</option>
                  </select>
                </label>
              </div>
              <div className="priority-chip-row">
                {priorityOptions.map((option) => (
                  <button
                    className={projectData.reviewPreset === option ? "priority-chip active" : "priority-chip"}
                    key={option}
                    onClick={() => updateField("reviewPreset", option)}
                    type="button"
                  >
                    {option}
                  </button>
                ))}
              </div>
            </section>

            <section className="requirement-input-block">
              <div className="requirement-block-title">
                <span>4</span>
                <div>
                  <b>추가 메모</b>
                  <small>A/S, 납기, 설치 제한, 첨부 자료에 대한 메모를 남깁니다.</small>
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
              <label>
                <span>첨부 메모</span>
                <textarea
                  onChange={(event) => updateField("attachmentMemo", event.target.value)}
                  placeholder="도면, 사진, 기존 견적서, 담당자 요청사항 등 첨부 자료에 대한 메모"
                  value={projectData.attachmentMemo || ""}
                />
              </label>
            </section>
          </form>

          <aside className="matching-check-panel refined">
            <div className="requirements-section-title">
              <div>
                <h2>매칭 가능성 체크</h2>
                <p>현재 입력값 기준 사전 검증 결과입니다.</p>
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
              <p>
                현재 정보만으로도 파트너 매칭을 시작할 수 있습니다. 세부 모델과 설치 방식은
                후보 검토 과정에서 보완해 주세요.
              </p>
            </div>

            <div className="matching-next-guide refined">
              <b>다음 단계 안내</b>
              <p>
                파트너 매칭 화면에서 AI 추천 순위와 적합도 점수를 확인하고, 견적 요청을
                보낼 업체를 선택할 수 있습니다.
              </p>
            </div>
          </aside>
        </section>
      </main>

      <footer className="requirements-bottom-actions">
        <span>요구사항은 빈 값이어도 저장할 수 있습니다.</span>
        <div>
          <button className="button action-secondary" onClick={onSaveDraft} type="button">
            임시 저장
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

function getMatchingChecks(data) {
  const stage = data.currentStage || "";
  const schedule = getScheduleState(data.projectDate);
  const hasCompany = Boolean(data.companyName?.trim());
  const hasLocation = Boolean(data.location?.trim());
  const hasUsage = Boolean(data.usage?.trim());
  const hasDisplayDimension = Boolean(
    data.displaySize?.trim() ||
      data.displayInch?.trim() ||
      (data.displayWidth?.trim() && data.displayHeight?.trim()),
  );
  const hasSpec = Boolean(hasDisplayDimension || data.quantity?.trim());
  const hasBudget = Boolean(data.budgetAmount?.trim());
  const hasCategory = Boolean(data.category?.trim());

  return [
    {
      title: "필수값 충족",
      level: hasCompany && hasLocation && hasUsage ? "ok" : "warn",
      message:
        hasCompany && hasLocation && hasUsage
          ? "회사명, 설치 위치, 활용 목적이 입력되었습니다."
          : "회사명, 설치 위치, 활용 목적을 입력하면 추천 정확도가 높아집니다.",
    },
    {
      title: "정보 탐색 단계 확인 필요",
      level: stage.includes("정보 탐색") ? "warn" : "ok",
      message: stage.includes("정보 탐색")
        ? "정보 탐색 단계는 자동 매칭이 제한될 수 있습니다."
        : "현재 단계 기준으로 파트너 매칭 검토가 가능합니다.",
    },
    {
      title: "일정 6개월 이내",
      level: schedule.level,
      message: schedule.message,
    },
    {
      title: "스펙/예산 보완",
      level: hasSpec && hasBudget ? "ok" : "warn",
      message:
        hasSpec && hasBudget
          ? "디스플레이 스펙과 예산 조건이 입력되었습니다."
          : "디스플레이 크기, 수량, 예산을 입력하면 후보군을 더 정확히 좁힐 수 있습니다.",
    },
    {
      title: "카테고리 적합성",
      level: hasCategory ? "ok" : "warn",
      message: hasCategory
        ? `${data.category} 파트너 풀과 매칭할 수 있습니다.`
        : "카테고리를 입력하면 후보군을 더 정확히 좁힐 수 있습니다.",
    },
  ];
}

function getReadinessScore(checks) {
  const base = 42;
  const score = checks.reduce((sum, check) => sum + (check.level === "ok" ? 11 : 5), base);
  return Math.min(score, 96);
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

function getScheduleState(value) {
  if (!value) {
    return {
      level: "warn",
      message: "일정이 없으면 납기 기준 매칭 정확도가 낮아집니다.",
    };
  }

  const target = new Date(value);
  if (Number.isNaN(target.getTime())) {
    return {
      level: "warn",
      message: "일정 형식을 확인해야 합니다.",
    };
  }

  const sixMonthsLater = new Date();
  sixMonthsLater.setMonth(sixMonthsLater.getMonth() + 6);

  if (target > sixMonthsLater) {
    return {
      level: "warn",
      message: "일정이 6개월을 초과해 우선 매칭 보류 대상으로 표시됩니다.",
    };
  }

  return {
    level: "ok",
    message: "프로젝트 기간이 가능한 범위입니다.",
  };
}
