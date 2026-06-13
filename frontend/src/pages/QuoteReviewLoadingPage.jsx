import { useEffect, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectStepTabs from "../components/ProjectStepTabs";
import { uploadProjectQuotes, runProjectMatch } from "../api/apiClient";
import { createMatchViewModel } from "../utils/matchAdapter";

const REVIEW_STEPS = [
  {
    title: "견적서 파일 확인",
    detail: "업로드된 견적서와 업체 정보를 비교 검토 대상으로 정리합니다.",
  },
  {
    title: "OCR/파싱 결과 평가",
    detail: "금액, 납기, 보증, 별도 비용 항목을 추출하고 누락값을 확인합니다.",
  },
  {
    title: "비교 항목 정규화",
    detail: "업체별 표현 차이를 같은 비교 기준으로 맞춥니다.",
  },
  {
    title: "AI 추천 기준 분석",
    detail: "예산, 납기, 유지보수, 리스크 조건을 함께 반영합니다.",
  },
  {
    title: "검토 화면 구성",
    detail: "비교표, 추천 사유, 확인 필요 항목을 화면에 표시할 준비를 합니다.",
  },
];

export default function QuoteReviewLoadingPage({
  projectData,
  onBack,
  onComplete,
  onProjectDataChange,
  onGoHome,
}) {
  const [activeStep, setActiveStep] = useState(0);
  const [timerDone, setTimerDone] = useState(false);
  const [analysisState, setAnalysisState] = useState("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [redirectCountdown, setRedirectCountdown] = useState(null);
  const isComplete = timerDone && analysisState === "ready";

  const runQuoteReviewAnalysis = async () => {
    setAnalysisState("loading");
    setErrorMessage("");

    try {
      const projectApiId = projectData.projectApiId;
      if (!projectApiId) {
        throw new Error("프로젝트 API ID가 없어 견적 비교 분석을 실행할 수 없습니다.");
      }

      let quoteIds = projectData.quoteIds ?? [];
      if (!quoteIds.length) {
        const quoteFiles = projectData.quoteFiles ?? [];
        if (!quoteFiles.length) {
          throw new Error("업로드할 견적서가 없습니다. 견적 수신 화면에서 파일을 선택해 주세요.");
        }

        const uploadResult = await uploadProjectQuotes(projectApiId, quoteFiles);
        quoteIds =
          uploadResult.quote_ids ??
          uploadResult.quotes?.map((quote) => quote.quote_id ?? quote.id) ??
          [];

        onProjectDataChange((current) => ({
          ...current,
          quoteFiles,
          quoteIds,
          quoteUploadResult: uploadResult,
        }));
      }

      if (!quoteIds.length) {
        throw new Error("업로드된 견적서 ID가 없어 견적 비교 분석을 실행할 수 없습니다.");
      }

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
      setErrorMessage(error.message || "견적 비교 분석 중 오류가 발생했습니다.");
    }
  };

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveStep((current) => {
        if (current >= REVIEW_STEPS.length - 1) {
          window.clearInterval(timer);
          window.setTimeout(() => setTimerDone(true), 350);
          return current;
        }
        return current + 1;
      });
    }, 900);

    return () => window.clearInterval(timer);
  }, []);

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

  return (
    <div className="flow-page matching-loading-page">
      <FlowTopbar
        onHome={onGoHome}
        trail="프로젝트 상세 > 견적 비교 분석"
        action={
          <>
            <div className="avatar" />
            <div className="user-name">
              <b>김담당자</b>
              <small>구매팀</small>
            </div>
          </>
        }
      />

      <main className="matching-loading-main">
        <section className="matching-loading-card">
          <ProjectStepTabs activeStep={4} onGoQuoteWaiting={onBack} />
          <div
            className={`matching-loading-symbol${
              analysisState === "error" ? " is-error" : isComplete ? " is-complete" : ""
            }`}
            aria-hidden="true"
          >
            {analysisState === "error" ? (
              <span>!</span>
            ) : isComplete ? (
              <span>✓</span>
            ) : (
              <span />
            )}
          </div>
          <Badge tone={isComplete ? "green" : analysisState === "error" ? "red" : "blue"}>
            {analysisState === "error"
              ? "분석 오류"
              : isComplete
                ? "비교 검토 준비 완료"
                : "견적 비교 분석중"}
          </Badge>
          <h1>
            {analysisState === "error"
              ? "견적 비교 분석을 완료하지 못했습니다"
              : isComplete
                ? "모든 분석을 마쳤어요."
                : "수신한 견적서를 비교 분석하고 있습니다"}
          </h1>
          <p>
            {isComplete ? (
              <span aria-live="polite">{redirectCountdown ?? 3}초 후 검토 화면으로 이동합니다.</span>
            ) : (
              <>
                {projectData.projectName || projectData.companyName || "프로젝트"}의 업로드된 견적서를
                기준으로 비교표와 추천 사유를 준비합니다.
              </>
            )}
          </p>

          {errorMessage ? (
            <div className="analysis-error-box">{errorMessage}</div>
          ) : null}

          <div className="matching-loading-steps">
            {REVIEW_STEPS.map((step, index) => {
              const isDone = isComplete || index < activeStep;
              const isActive = !isComplete && index === activeStep;

              return (
                <article
                  className={`${isDone ? "done" : ""} ${isActive ? "active" : ""}`}
                  key={step.title}
                >
                  <span>{isDone ? "✓" : index + 1}</span>
                  <div>
                    <b>{step.title}</b>
                    <small>{step.detail}</small>
                  </div>
                </article>
              );
            })}
          </div>

          <div className="matching-loading-actions">
            <button className="button" onClick={onBack} type="button">
              견적 수신으로 돌아가기
            </button>
            {analysisState === "error" ? (
              <button className="button button-blue" onClick={runQuoteReviewAnalysis} type="button">
                다시 분석
              </button>
            ) : null}
            <button
              className="button action-primary"
              disabled={!isComplete}
              onClick={onComplete}
              type="button"
            >
              견적 검토 화면 보기
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
