import FlowTopbar from '../components/FlowTopbar';

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
      <FlowTopbar onHome={onGoHome} trail="새 프로젝트 생성 > AI 분석" />
      <main className="analysis-card">
        {isError ? (
          <>
            <div className="analysis-symbol error">!</div>
            <h1>AI 분석을 시작하지 못했습니다</h1>
            <p>{errorMessage || "프로젝트 생성, 견적 업로드, 매칭 실행 중 오류가 발생했습니다."}</p>
            <div className="analysis-actions">
              <button className="button" onClick={onBack} type="button">
                입력 화면으로 돌아가기
              </button>
              <button className="button action-primary" onClick={onRetry} type="button">
                다시 시도
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="analysis-symbol">✦</div>
            <h1>{isReady ? "AI 분석 준비가 완료되었습니다" : "AI가 견적서를 분석 중입니다"}</h1>
            <p>프로젝트 생성, 견적서 업로드, 매칭 실행 흐름을 순서대로 처리하고 있습니다.</p>
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
            <button className="button action-primary" disabled={!isReady} onClick={onDashboard} type="button">
              분석 완료 화면 보기
            </button>
          </>
        )}
      </main>
    </div>
  );
}
