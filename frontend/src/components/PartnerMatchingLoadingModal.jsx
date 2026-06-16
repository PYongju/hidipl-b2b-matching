export const PARTNER_MATCHING_LOADING_STEPS = {
  "creating-project": "요구사항을 분석하고 있어요",
  "fetching-candidates": "조건에 맞는 공급사를 찾고 있어요",
  finishing: "AI 추천 결과를 정리하고 있어요",
};

export const PARTNER_MATCHING_TIMELINE_STEPS = [
  { key: "creating-project", label: "요구사항 분석" },
  { key: "fetching-candidates", label: "공급사 탐색" },
  { key: "finishing", label: "결과 정리" },
];

function hasDisplayText(value) {
  return Boolean(String(value ?? "").trim());
}

export default function PartnerMatchingLoadingModal({
  open,
  status = "loading",
  loadingStep = "creating-project",
  errorMessage = "",
  companyName = "",
  category = "",
  onCancel,
  onRetry,
}) {
  const isLoading = status === "loading";
  const statusMessage =
    PARTNER_MATCHING_LOADING_STEPS[loadingStep] ??
    PARTNER_MATCHING_LOADING_STEPS["creating-project"];
  const displayCompanyName = String(companyName ?? "").trim();
  const displayCategory = String(category ?? "").trim();
  const showMeta =
    hasDisplayText(displayCompanyName) || hasDisplayText(displayCategory);
  const activeStepIndex = Math.max(
    0,
    PARTNER_MATCHING_TIMELINE_STEPS.findIndex((step) => step.key === loadingStep),
  );
  const timelineProgress =
    PARTNER_MATCHING_TIMELINE_STEPS.length <= 1
      ? 100
      : Math.round((activeStepIndex / (PARTNER_MATCHING_TIMELINE_STEPS.length - 1)) * 100);

  if (!open) return null;

  return (
    <div className="partner-match-popup-layer" role="presentation">
      <div
        aria-busy={isLoading}
        aria-labelledby="partner-match-popup-title"
        aria-live="polite"
        className="partner-match-popup"
        role="dialog"
      >
        {isLoading ? (
          <>
            <div aria-hidden="true" className="partner-match-popup-spinner">
              <span />
              <span />
              <span />
            </div>
            <p className="partner-match-popup-eyebrow">AI 공급사 추천</p>
            <h2 id="partner-match-popup-title">맞춤 공급사 추천을 진행하고 있어요</h2>
            <p className="partner-match-popup-status" key={loadingStep}>
              {statusMessage}
            </p>
            {showMeta ? (
              <div className="partner-match-popup-meta">
                {hasDisplayText(displayCompanyName) ? (
                  <p>
                    <span>회사명</span>
                    <b>{displayCompanyName}</b>
                  </p>
                ) : null}
                {hasDisplayText(displayCategory) ? (
                  <p>
                    <span>카테고리</span>
                    <b>{displayCategory}</b>
                  </p>
                ) : null}
              </div>
            ) : null}
            <div
              aria-label={`진행 단계 ${activeStepIndex + 1} / ${PARTNER_MATCHING_TIMELINE_STEPS.length}`}
              aria-valuemax={PARTNER_MATCHING_TIMELINE_STEPS.length}
              aria-valuemin={1}
              aria-valuenow={activeStepIndex + 1}
              className="partner-match-popup-timeline"
              role="progressbar"
            >
              <div className="partner-match-popup-timeline-rail" aria-hidden="true">
                <div
                  className="partner-match-popup-timeline-fill"
                  style={{ width: `${timelineProgress}%` }}
                />
              </div>
              <ol className="partner-match-popup-timeline-steps">
                {PARTNER_MATCHING_TIMELINE_STEPS.map((step, index) => {
                  const isDone = index < activeStepIndex;
                  const isActive = index === activeStepIndex;

                  return (
                    <li
                      className={`${isDone ? "done" : ""} ${isActive ? "active" : ""}`.trim()}
                      key={step.key}
                    >
                      <span aria-hidden="true">{isDone ? "✓" : index + 1}</span>
                      <small>{step.label}</small>
                    </li>
                  );
                })}
              </ol>
            </div>
            <p className="partner-match-popup-hint">완료되면 AI 추천 화면으로 이동해요</p>
          </>
        ) : (
          <>
            <h2 id="partner-match-popup-title">AI 공급사 추천을 시작하지 못했어요</h2>
            <p className="partner-match-popup-status partner-match-popup-error-text">
              {errorMessage || "AI 공급사 추천 준비 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요."}
            </p>
            <div className="partner-match-popup-actions">
              <button className="button action-secondary" onClick={onCancel} type="button">
                닫기
              </button>
              <button className="button action-primary" onClick={onRetry} type="button">
                다시 시도
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
