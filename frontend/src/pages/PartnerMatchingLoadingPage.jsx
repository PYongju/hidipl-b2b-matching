import { useEffect, useMemo, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import { fetchCandidateVendors } from "../api/apiClient";
import { formatProjectSolutions } from "../utils/projectRequestText";

function normalizeReviewPresetLabel(value) {
  const normalized = String(value ?? "").replace(/ 우선$/, "").trim();

  if (normalized === "최저가" || normalized === "가격") return "가격";
  if (normalized === "보증/A/S" || normalized === "보증·A/S") return "보증·A/S";
  if (normalized === "스펙") return "스펙";
  if (normalized === "납기") return "납기";
  if (normalized === "균형 추천") return "균형 추천";

  return normalized;
}

const MATCHING_STEPS = [
  {
    title: "요구사항 분석",
    detail: "활용 목적, 스펙, 운영 조건을 읽고 있어요.",
  },
  {
    title: "예산/일정 기준 추출",
    detail: "예산 범위와 납기 조건을 후보 필터에 반영해요.",
  },
  {
    title: "공급사 후보군 검색",
    detail: "카테고리와 설치 경험이 맞는 공급사를 찾고 있어요.",
  },
  {
    title: "적합도 점수 계산",
    detail: "전문성, 응답 속도, 가격 경쟁력, 신뢰도를 비교해요.",
  },
  {
    title: "추천 사유 생성",
    detail: "담당자가 검토할 수 있도록 추천 근거를 정리해요.",
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
        setErrorMessage(error.message || "공급사 추천 후보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
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
              ? "준비 끝! AI 분석 결과를 확인해 보세요."
              : "우리 프로젝트와 딱 맞는 파트너를 찾고 있어요."}
          </h1>
          <p>
            {projectData.projectName || projectData.companyName || "새 프로젝트"}
            의 요구사항을 기준으로 후보 공급사를 좁히고 추천 근거를 정리해요.
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
                  <span>
                    {isDone ? (
                      <i className="fa-solid fa-check" />
                    ) : (
                      index + 1
                    )}
                  </span>
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
                <strong>{normalizeReviewPresetLabel(projectData.reviewPreset) || "균형 추천"}</strong>
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
              프로젝트를 저장하고 있어요. 저장이 끝나면 공급사 추천을 시작해요.
            </div>
          ) : null}

          {candidateState === "loading" ? (
            <div className="matching-loading-message">
              추천 후보를 불러오고 있어요.
            </div>
          ) : null}

          {candidateState === "empty" ? (
            <div className="matching-loading-message warning">
              추천 후보가 없어요. 요구사항을 보완해 주세요.
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
