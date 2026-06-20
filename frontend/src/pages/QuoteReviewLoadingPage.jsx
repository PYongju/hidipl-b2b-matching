import { useEffect, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectDetailHeader from "../components/ProjectDetailHeader";
import { uploadProjectQuotes, runProjectMatch } from "../api/apiClient";
import { createMatchViewModel } from "../utils/matchAdapter";
import { saveQuoteIdsToStorage } from "../utils/projectQuoteIds";
import { buildProjectInfoSummary } from "../utils/projectRequestText";
import { getUserDisplayName, USER } from "../constants/uiText";

const REVIEW_STEPS = [
  {
    id: "upload",
    title: "견적서 업로드",
    detail: "선택한 견적서를 서버에 업로드하고 비교 대상을 등록해요.",
    skippedDetail: "이미 업로드된 견적서를 사용해요.",
  },
  {
    id: "match",
    title: "견적 비교 분석",
    detail: "견적서를 매칭하고 AI 추천·비교 데이터를 생성해요.",
  },
];

function getStepVisualState({
  index,
  activeStep,
  analysisState,
  uploadSkipped,
}) {
  const isComplete = analysisState === "ready";
  const isError = analysisState === "error";

  if (isComplete || index < activeStep) {
    return "done";
  }
  if (isError && index === activeStep) {
    return "error";
  }
  if (index === activeStep && analysisState === "loading") {
    return "active";
  }
  if (index === 0 && uploadSkipped && activeStep === 1 && analysisState === "loading") {
    return "done";
  }
  return "pending";
}

export default function QuoteReviewLoadingPage({
  projectData,
  onBack,
  onComplete,
  onProjectDataChange,
  onGoHome,
  userRole = "member",
}) {
  const [activeStep, setActiveStep] = useState(0);
  const [uploadSkipped, setUploadSkipped] = useState(false);
  const [analysisState, setAnalysisState] = useState("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [redirectCountdown, setRedirectCountdown] = useState(null);
  const isComplete = analysisState === "ready";

  const runQuoteReviewAnalysis = async () => {
    setActiveStep(0);
    setUploadSkipped(false);
    setRedirectCountdown(null);
    setAnalysisState("loading");
    setErrorMessage("");

    try {
      const projectApiId = projectData.projectApiId;
      if (!projectApiId) {
        throw new Error(
          "프로젝트 정보가 없어 견적 비교 분석을 시작할 수 없어요.",
        );
      }

      const quoteFiles = projectData.quoteFiles ?? [];
      let quoteIds;

      if (quoteFiles.length) {
        setActiveStep(0);
        const uploadResult = await uploadProjectQuotes(projectApiId, quoteFiles);
        quoteIds =
          uploadResult.quote_ids ??
          uploadResult.quotes?.map((quote) => quote.quote_id ?? quote.id) ??
          [];
        saveQuoteIdsToStorage(projectApiId, quoteIds);
        onProjectDataChange((current) => ({
          ...current,
          quoteFiles,
          quoteIds,
          quoteUploadResult: uploadResult,
        }));
      } else if (projectData.quoteIds?.length) {
        quoteIds = projectData.quoteIds;
        setUploadSkipped(true);
      } else {
        throw new Error(
          "업로드할 견적서가 없어요. 견적 수신 화면에서 파일을 다시 선택해 주세요.",
        );
      }

      if (!quoteIds.length) {
        throw new Error(
          "업로드된 견적서가 없어 견적 비교 분석을 시작할 수 없어요.",
        );
      }

      setActiveStep(1);
      const matchResult = await runProjectMatch(projectApiId);
      const matchViewModel = createMatchViewModel(matchResult);
      const matchId = matchViewModel.matchId;

      onProjectDataChange((current) => ({
        ...current,
        matchId,
        matchResult: matchViewModel,
      }));
      setAnalysisState("ready");
    } catch (error) {
      setAnalysisState("error");
      setErrorMessage(
        error.message ||
          "견적 비교 분석 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
      );
    }
  };

  useEffect(() => {
    runQuoteReviewAnalysis();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isComplete) return undefined;

    setRedirectCountdown(3);
    let remaining = 3;

    const interval = window.setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        window.clearInterval(interval);
        onComplete();
        return;
      }
      setRedirectCountdown(remaining);
    }, 1000);

    return () => window.clearInterval(interval);
  }, [isComplete, onComplete]);

  const projectInfoSummary = buildProjectInfoSummary(projectData, {
    includeLocation: true,
  });

  return (
    <div className="flow-page matching-loading-page">
      <FlowTopbar
        onHome={onGoHome}
        trail="프로젝트 상세 > 견적 비교 분석"
        action={
          <>
            <button
              className="button action-secondary"
              onClick={onGoHome}
              type="button"
            >
              목록
            </button>
            <div className="avatar" />
            <div className="user-name">
              <b>{getUserDisplayName(userRole)}</b>
              <small>{USER.team}</small>
            </div>
          </>
        }
      />

      <main className="matching-loading-main">
        <ProjectDetailHeader
          infoSummary={projectInfoSummary}
          onBack={onBack}
          projectName={projectData.projectName || "새 프로젝트"}
        />

        <section className="matching-loading-card">
          <div
            className={`matching-loading-symbol${
              analysisState === "error"
                ? " is-error"
                : isComplete
                  ? " is-complete"
                  : ""
            }`}
            aria-hidden="true"
          >
            {analysisState === "error" ? (
              <span>
                <i className="fa-solid fa-exclamation" />
              </span>
            ) : isComplete ? (
              <span>
                <i className="fa-solid fa-check" />
              </span>
            ) : (
              <span />
            )}
          </div>

          <Badge
            tone={
              isComplete ? "green" : analysisState === "error" ? "red" : "blue"
            }
          >
            {analysisState === "error"
              ? "분석 오류"
              : isComplete
                ? "비교 검토 준비 완료"
                : "견적 비교 분석중"}
          </Badge>

          <h1>
            {analysisState === "error"
              ? "견적 비교 분석을 완료하지 못했어요"
              : isComplete
                ? "모든 분석이 마무리됐어요."
                : "수신한 견적서를 비교 분석하고 있어요"}
          </h1>

          <p>
            {isComplete ? (
              <span aria-live="polite">
                {redirectCountdown ?? 3}초 후 견적 검토 화면으로 이동해요.
              </span>
            ) : (
              <>
                {projectData.projectName || projectData.companyName || "프로젝트"}
                의 견적서를 업로드한 뒤 비교·추천 데이터를 준비해요.
              </>
            )}
          </p>

          {analysisState === "error" ? (
            <div className="matching-loading-message warning">
              <b>분석 실패</b>
              <span>{errorMessage}</span>
            </div>
          ) : null}

          {analysisState !== "error" ? (
            <div className="matching-loading-steps">
              {REVIEW_STEPS.map((step, index) => {
                const visualState = getStepVisualState({
                  index,
                  activeStep,
                  analysisState,
                  uploadSkipped,
                });
                const isDone = visualState === "done";
                const isActive = visualState === "active";
                const isErrorStep = visualState === "error";
                const detail =
                  index === 0 && uploadSkipped && (isDone || isActive)
                    ? step.skippedDetail
                    : step.detail;

                return (
                  <article
                    className={`${isDone ? "done" : ""} ${isActive ? "active" : ""} ${isErrorStep ? "error" : ""}`.trim()}
                    key={step.id}
                  >
                    <span>
                      {isDone ? (
                        <i className="fa-solid fa-check" />
                      ) : isErrorStep ? (
                        <i className="fa-solid fa-exclamation" />
                      ) : (
                        index + 1
                      )}
                    </span>
                    <div>
                      <b>{step.title}</b>
                      <small>{detail}</small>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}

          <div className="matching-loading-actions">
            <button
              className="button action-secondary"
              onClick={onBack}
              type="button"
            >
              이전
            </button>
            {analysisState === "error" ? (
              <button
                className="button button-blue"
                onClick={runQuoteReviewAnalysis}
                type="button"
              >
                다시 분석
              </button>
            ) : null}
            <button
              className="button action-primary"
              disabled={!isComplete}
              onClick={onComplete}
              type="button"
            >
              다음: 견적 검토 결과
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
