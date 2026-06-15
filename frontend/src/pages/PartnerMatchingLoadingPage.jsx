import { useEffect, useMemo, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import { fetchCandidateVendors } from "../api/apiClient";
import { formatProjectSolutions } from "../utils/projectRequestText";

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
  onProjectDataChange,
}) {
  const [activeStep, setActiveStep] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  const [candidateState, setCandidateState] = useState(
    projectData.candidateVendors?.length ? "ready" : "waiting-project",
  );
  const [errorMessage, setErrorMessage] = useState("");
  const [retryCount, setRetryCount] = useState(0);
  const isProjectCreated = Boolean(projectData.projectApiId);
  const isReady =
    isComplete &&
    isProjectCreated &&
    candidateState === "ready" &&
    (projectData.candidateVendors?.length ?? 0) > 0;
  const progress = useMemo(() => {
    if (isReady) return 100;
    return Math.min(
      candidateState === "loading" ? 96 : 90,
      Math.round(((activeStep + 1) / MATCHING_STEPS.length) * 92),
    );
  }, [activeStep, candidateState, isReady]);

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

  useEffect(() => {
    if (!projectData.projectApiId) {
      setCandidateState("waiting-project");
      return;
    }

    if (projectData.candidateVendors?.length) {
      setCandidateState("ready");
      return;
    }

    if (projectData.candidateVendorsLoaded) {
      setCandidateState("empty");
      return;
    }

    let isMounted = true;
    setCandidateState("loading");
    setErrorMessage("");

    fetchCandidateVendors(projectData.projectApiId, 51)
      .then((response) => {
        if (!isMounted) return;
        const candidates = response?.candidate_vendors ?? [];

        onProjectDataChange((current) => ({
          ...current,
          candidateVendors: candidates,
          candidateVendorsLoaded: true,
          candidateVendorsResponse: response,
        }));
        setCandidateState(candidates.length ? "ready" : "empty");
      })
      .catch((error) => {
        if (!isMounted) return;
        setCandidateState("error");
        setErrorMessage(error.message || "파트너 추천 후보 조회 중 오류가 발생했습니다.");
      });

    return () => {
      isMounted = false;
    };
  }, [
    onProjectDataChange,
    projectData.candidateVendors?.length,
    projectData.candidateVendorsLoaded,
    projectData.projectApiId,
    retryCount,
  ]);

  const retryCandidateFetch = () => {
    onProjectDataChange((current) => ({
      ...current,
      candidateVendors: [],
      candidateVendorsLoaded: false,
      candidateVendorsResponse: null,
    }));
    setRetryCount((current) => current + 1);
  };

  const statusText = getCandidateStatusText(candidateState, isProjectCreated, isReady);

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
          <Badge tone={isReady ? "green" : candidateState === "error" ? "orange" : "blue"}>
            {statusText.badge}
          </Badge>
          <h1>
            {isReady
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
              <strong>{formatProjectSolutions(projectData, "미선택")}</strong>
            </article>
            <article>
              <span>예산</span>
              <strong>{projectData.budgetAmount ? `${projectData.budgetAmount}원` : "미입력"}</strong>
            </article>
          </div>

          {candidateState === "waiting-project" ? (
            <div className="matching-loading-message">
              프로젝트를 저장하는 중입니다. 저장이 완료되면 파트너 추천을 시작합니다.
            </div>
          ) : null}

          {candidateState === "loading" ? (
            <div className="matching-loading-message">
              candidate-vendors API에서 추천 후보를 조회하고 있습니다.
            </div>
          ) : null}

          {candidateState === "empty" ? (
            <div className="matching-loading-message warning">
              추천 후보가 없습니다. 요구사항을 보완하거나 백엔드 후보 조회 결과를 확인해야 합니다.
            </div>
          ) : null}

          {candidateState === "error" ? (
            <div className="matching-loading-message warning">
              <b>추천 후보 조회 실패</b>
              <span>{errorMessage}</span>
              <button className="button button-small" onClick={retryCandidateFetch} type="button">
                다시 조회
              </button>
            </div>
          ) : null}

          <div className="matching-loading-actions">
            <button className="button" onClick={onBack} type="button">
              요구사항 수정
            </button>
            <button className="button action-primary" disabled={!isReady} onClick={onComplete} type="button">
              {statusText.action}
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

function getCandidateStatusText(candidateState, isProjectCreated, isReady) {
  if (isReady) {
    return { badge: "추천 준비 완료", action: "추천 결과 보기" };
  }
  if (!isProjectCreated || candidateState === "waiting-project") {
    return { badge: "프로젝트 저장중", action: "프로젝트 저장 대기" };
  }
  if (candidateState === "loading") {
    return { badge: "추천 후보 조회중", action: "추천 후보 조회중" };
  }
  if (candidateState === "empty") {
    return { badge: "추천 후보 없음", action: "추천 결과 없음" };
  }
  if (candidateState === "error") {
    return { badge: "추천 조회 오류", action: "추천 조회 필요" };
  }
  return { badge: "AI 파트너 매칭중", action: "추천 결과 보기" };
}
