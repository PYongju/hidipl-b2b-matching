import FlowTopbar from "../components/FlowTopbar";

export default function AnalysisPage({
  errorMessage,
  onBack,
  onDashboard,
  onRetry,
  onGoHome,
  state = "loading",
}) {
  const isError = state === "error";
  const isReady = state === "ready";

  return (
    <div className="flow-page analysis-page">
      <FlowTopbar
        action={
          <button
            className="button action-secondary"
            onClick={onGoHome}
            type="button"
          >
            목록
          </button>
        }
        onHome={onGoHome}
        trail="새 프로젝트 생성 > AI 분석"
      />
      <main className="analysis-card">
        {isError ? (
          <>
            <div className="analysis-symbol error">!</div>
            <h1>AI 분석을 시작하지 못했어요</h1>
            <p>
              {errorMessage ||
                "분석을 시작하는 중에 문제가 생겼어요. 잠시 후 다시 시도해 주세요."}
            </p>
            <div className="analysis-actions">
              <button className="button" onClick={onBack} type="button">
                이전 단계로 돌아가기
              </button>
              <button
                className="button action-primary"
                onClick={onRetry}
                type="button"
              >
                다시 시도
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="analysis-symbol">AI</div>
            <h1>
              {isReady
                ? "AI 분석 준비가 완료됐어요"
                : "AI가 견적서를 분석하고 있어요"}
            </h1>
            <p>
              프로젝트 생성, 견적서 업로드, 공급사 매칭 실행 흐름을 순서대로
              처리하고 있어요.
            </p>
            <div className="analysis-progress">
              <span className={isReady ? "complete" : ""} />
            </div>
            <div className="analysis-steps">
              <div className="done">
                <b>프로젝트 생성</b>
                <small>{isReady ? "완료" : "진행 중"}</small>
              </div>
              <div className={isReady ? "done" : "active"}>
                <b>견적서 업로드</b>
                <small>{isReady ? "완료" : "대기 또는 진행 중"}</small>
              </div>
              <div className={isReady ? "done" : ""}>
                <b>공급사 매칭 실행</b>
                <small>{isReady ? "완료" : "대기 중"}</small>
              </div>
              <div className={isReady ? "done" : ""}>
                <b>비교 대시보드 연결</b>
                <small>{isReady ? "준비 완료" : "대기 중"}</small>
              </div>
            </div>
            <button
              className="button action-primary"
              disabled={!isReady}
              onClick={onDashboard}
              type="button"
            >
              분석 완료 화면 보기
            </button>
          </>
        )}
      </main>
    </div>
  );
}
