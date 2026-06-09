import { useEffect, useMemo, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectStepTabs from "../components/ProjectStepTabs";

const REVIEW_STEPS = [
  {
    title: "견적서 파일 확인",
    detail: "수신된 견적서와 업체 정보를 비교 검토 대상으로 정리합니다.",
  },
  {
    title: "OCR 파싱 결과 점검",
    detail: "금액, 납기, 보증, 별도 비용 항목을 추출하고 누락을 확인합니다.",
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
}) {
  const [activeStep, setActiveStep] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  const progress = useMemo(() => {
    if (isComplete) return 100;
    return Math.min(96, Math.round(((activeStep + 1) / REVIEW_STEPS.length) * 92));
  }, [activeStep, isComplete]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveStep((current) => {
        if (current >= REVIEW_STEPS.length - 1) {
          window.clearInterval(timer);
          window.setTimeout(() => setIsComplete(true), 350);
          return current;
        }
        return current + 1;
      });
    }, 900);

    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="flow-page matching-loading-page">
      <FlowTopbar
        trail="프로젝트 상세 > 견적 비교 분석"
        action={
          <button className="button action-secondary" onClick={onBack} type="button">
            견적 수신으로 돌아가기
          </button>
        }
      />

      <main className="matching-loading-main">
        <section className="matching-loading-card">
          <ProjectStepTabs activeStep={4} onGoQuoteWaiting={onBack} />
          <div className="matching-loading-symbol" aria-hidden="true">
            <span />
          </div>
          <Badge tone={isComplete ? "green" : "blue"}>
            {isComplete ? "비교 검토 준비 완료" : "견적 비교 분석중"}
          </Badge>
          <h1>
            {isComplete
              ? "견적 검토 화면을 열 준비가 완료되었습니다"
              : "수신된 견적서를 비교 분석하고 있습니다"}
          </h1>
          <p>
            {projectData.projectName || projectData.companyName || "프로젝트"}의 수신 견적을
            기준으로 비교표와 추천 사유를 준비합니다.
          </p>

          <div className="matching-loading-progress" aria-label={`진행률 ${progress}%`}>
            <div style={{ width: `${progress}%` }} />
          </div>

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
            <button className="button action-primary" disabled={!isComplete} onClick={onComplete} type="button">
              견적 검토 화면 보기
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
