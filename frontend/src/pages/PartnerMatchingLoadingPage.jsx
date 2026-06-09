import { useEffect, useMemo, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";

const MATCHING_STEPS = [
  {
    title: "요구사항 분석",
    detail: "활용 목적, 스펙, 운영 조건을 읽고 있습니다.",
  },
  {
    title: "예산/일정 기준 추출",
    detail: "예산 범위와 납기 조건을 후보 필터에 반영합니다.",
  },
  {
    title: "파트너 후보군 검색",
    detail: "카테고리와 설치 경험이 맞는 공급사를 찾고 있습니다.",
  },
  {
    title: "적합도 점수 계산",
    detail: "전문성, 응답 속도, 가격 경쟁력, 신뢰도를 비교합니다.",
  },
  {
    title: "추천 사유 생성",
    detail: "담당자가 검토할 수 있도록 추천 근거를 정리합니다.",
  },
];

export default function PartnerMatchingLoadingPage({
  projectData,
  onBack,
  onComplete,
}) {
  const [activeStep, setActiveStep] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  const progress = useMemo(() => {
    if (isComplete) return 100;
    return Math.min(
      96,
      Math.round(((activeStep + 1) / MATCHING_STEPS.length) * 92),
    );
  }, [activeStep, isComplete]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveStep((current) => {
        if (current >= MATCHING_STEPS.length - 1) {
          window.clearInterval(timer);
          window.setTimeout(() => setIsComplete(true), 350);
          return current;
        }
        return current + 1;
      });
    }, 850);

    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="flow-page matching-loading-page">
      <FlowTopbar
        trail="프로젝트 상세 > AI 파트너 매칭"
        action={
          <button className="button action-secondary" onClick={onBack} type="button">
            요구사항으로 돌아가기
          </button>
        }
      />

      <main className="matching-loading-main">
        <section className="matching-loading-card">
          <div className="matching-loading-symbol" aria-hidden="true">
            <span />
          </div>
          <Badge tone={isComplete ? "green" : "blue"}>
            {isComplete ? "추천 준비 완료" : "AI 파트너 매칭중"}
          </Badge>
          <h1>
            {isComplete
              ? "추천 파트너 검토 준비가 완료되었습니다"
              : "프로젝트 조건에 맞는 파트너를 찾고 있습니다"}
          </h1>
          <p>
            {projectData.projectName || projectData.companyName || "신규 검토 건"}
            의 요구사항을 기준으로 후보 업체를 좁히고 추천 근거를 정리합니다.
          </p>

          <div className="matching-loading-progress" aria-label={`진행률 ${progress}%`}>
            <div style={{ width: `${progress}%` }} />
          </div>

          <div className="matching-loading-steps">
            {MATCHING_STEPS.map((step, index) => {
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

          <div className="matching-loading-summary">
            <article>
              <span>우선 기준</span>
              <strong>{projectData.reviewPreset || "균형 추천"}</strong>
            </article>
            <article>
              <span>카테고리</span>
              <strong>{projectData.category || "디스플레이"}</strong>
            </article>
            <article>
              <span>예산</span>
              <strong>{projectData.budgetAmount ? `${projectData.budgetAmount}원` : "미입력"}</strong>
            </article>
          </div>

          <div className="matching-loading-actions">
            <button className="button" onClick={onBack} type="button">
              요구사항 수정
            </button>
            <button className="button action-primary" disabled={!isComplete} onClick={onComplete} type="button">
              추천 결과 보기
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
