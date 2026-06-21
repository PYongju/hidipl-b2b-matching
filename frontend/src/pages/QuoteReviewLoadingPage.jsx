import { useEffect, useRef, useState } from "react";
import FlowTopbar from "../components/FlowTopbar";
import { uploadProjectQuotes, runProjectMatch } from "../api/apiClient";
import { createMatchViewModel } from "../utils/matchAdapter";
import { saveQuoteIdsToStorage } from "../utils/projectQuoteIds";
import { getUserDisplayName, USER } from "../constants/uiText";

const SLOT_STEPS = [
  {
    title: "견적서 업로드",
    desc: "선택한 견적서를 서버에 안전하게 업로드하고 있어요.",
    descs: [
      "견적서 잘 받았어요, 서버로 보내는 중이에요...",
      "파일이 잘 도착했는지 확인할게요...",
    ],
  },
  {
    title: "파일 무결성 검증",
    desc: "PDF·Excel 형식과 파일 손상 여부를 꼼꼼히 확인해요.",
    descs: [
      "파일이 멀쩡한지 한번 살펴볼게요...",
      "내용이 잘 담겨있는지 꼼꼼히 확인하고 있어요...",
    ],
  },
  {
    title: "항목 구조 파악",
    desc: "견적 항목, 수량, 단가 구조를 AI가 읽어들이고 있어요.",
    descs: [
      "어떤 항목들이 있는지 읽어보고 있어요...",
      "수량이랑 단가 구조 파악 중이에요...",
    ],
  },
  {
    title: "공급사별 데이터 정리",
    desc: "공급사마다 다른 항목 표기 방식을 통일된 형식으로 정리해요.",
    descs: [
      "공급사마다 표기 방식이 달라서 맞춰보는 중이에요...",
      "다 같은 형식으로 정리해드릴게요...",
    ],
  },
  {
    title: "견적 비교 분석",
    desc: "AI 추천 점수와 비교 데이터를 최종 생성하고 있어요.",
    descs: [
      "거의 다 됐어요, AI가 점수 매기는 중이에요...",
      "최적의 공급사 추려내고 있어요...",
    ],
  },
];

const SLOT_STEP_INTERVAL_MS = 3800;
const SLOT_LAST_INDEX = SLOT_STEPS.length - 1;
const SLOT_STEP5_WAIT_MS = 8000;
const SLOT_CARD_HEIGHT = 78;
const SLOT_CARD_STRIDE = SLOT_CARD_HEIGHT + 8;
const SLOT_FOCUS_TOP = SLOT_CARD_STRIDE;

function getSlotTrackTranslateY(slotIndex) {
  if (slotIndex <= 0) {
    return 0;
  }

  return SLOT_FOCUS_TOP - slotIndex * SLOT_CARD_STRIDE;
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
  const [slotIndex, setSlotIndex] = useState(0);
  const [descIndex, setDescIndex] = useState(0);
  const [descVisible, setDescVisible] = useState(true);
  const [showStep5WaitMessage, setShowStep5WaitMessage] = useState(false);
  const slotWrapRef = useRef(null);
  const slotTrackRef = useRef(null);
  const slotIndexRef = useRef(slotIndex);
  const step5WaitStartedAtRef = useRef(null);
  slotIndexRef.current = slotIndex;
  const isComplete = analysisState === "ready";
  const isSlotFinished = slotIndex >= SLOT_STEPS.length - 1;
  const showCompletion = isComplete && isSlotFinished;
  const runQuoteReviewAnalysis = async () => {
    setActiveStep(0);
    setUploadSkipped(false);
    setRedirectCountdown(null);
    setSlotIndex(0);
    step5WaitStartedAtRef.current = null;
    setShowStep5WaitMessage(false);
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
    if (!showCompletion) {
      return undefined;
    }

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
  }, [showCompletion, onComplete]);

  useEffect(() => {
    if (analysisState === "loading") {
      setSlotIndex(0);
    }
  }, [analysisState]);

  useEffect(() => {
    if (analysisState === "error" || isSlotFinished) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      setSlotIndex((current) => current + 1);
    }, SLOT_STEP_INTERVAL_MS);

    return () => window.clearTimeout(timer);
  }, [slotIndex, analysisState, isSlotFinished]);

  useEffect(() => {
    const wrap = slotWrapRef.current;
    const track = slotTrackRef.current;
    if (!wrap || !track) {
      return;
    }

    const translateY = getSlotTrackTranslateY(slotIndex);
    track.style.transform = `translateY(${translateY}px)`;

    if (slotIndex >= SLOT_STEPS.length - 1) {
      wrap.style.maskImage = "none";
      wrap.style.webkitMaskImage = "none";
    } else if (slotIndex <= 0) {
      const mask =
        "linear-gradient(to bottom, black 0%, black 58%, transparent 100%)";
      wrap.style.maskImage = mask;
      wrap.style.webkitMaskImage = mask;
    } else {
      const mask =
        "linear-gradient(to bottom, black 0%, black 62%, transparent 100%)";
      wrap.style.maskImage = mask;
      wrap.style.webkitMaskImage = mask;
    }
  }, [slotIndex]);

  useEffect(() => {
    setDescIndex(0);
    setDescVisible(true);
  }, [slotIndex]);

  useEffect(() => {
    let fadeTimer;

    const t = window.setInterval(() => {
      setDescVisible(false);
      fadeTimer = window.setTimeout(() => {
        setDescIndex((i) => (i + 1) % 2);
        setDescVisible(true);
      }, 300);
    }, 2000);

    return () => {
      window.clearInterval(t);
      if (fadeTimer) {
        window.clearTimeout(fadeTimer);
      }
    };
  }, [slotIndex]);

  useEffect(() => {
    if (analysisState !== "loading") {
      step5WaitStartedAtRef.current = null;
      setShowStep5WaitMessage(false);
      return undefined;
    }

    const interval = window.setInterval(() => {
      const currentSlotIndex = slotIndexRef.current;

      if (currentSlotIndex >= SLOT_LAST_INDEX) {
        if (step5WaitStartedAtRef.current === null) {
          step5WaitStartedAtRef.current = Date.now();
        }

        if (Date.now() - step5WaitStartedAtRef.current >= SLOT_STEP5_WAIT_MS) {
          setShowStep5WaitMessage(true);
        }
        return;
      }

      step5WaitStartedAtRef.current = null;
      setShowStep5WaitMessage(false);
    }, 500);

    return () => window.clearInterval(interval);
  }, [analysisState]);

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

      <main className="matching-loading-main quote-review-loading-main">
        <section className="matching-loading-card">
          <div className="header-group">
            {analysisState !== "error" ? (
              <div className="quote-review-loader-wrap">
                {showCompletion ? (
                  <div
                    aria-hidden="true"
                    className="quote-review-complete-icon quote-review-complete-icon-inline"
                  >
                    <i className="fa-solid fa-check" />
                  </div>
                ) : (
                  <div aria-hidden="true" className="loader">
                    <div className="loader-dot" />
                    <div className="loader-dot" />
                    <div className="loader-dot" />
                    <div className="loader-dot" />
                    <div className="loader-dot" />
                  </div>
                )}
              </div>
            ) : null}

            <h1>
              {analysisState === "error"
                ? "견적 비교 분석을 완료하지 못했어요"
                : showCompletion
                  ? "분석이 완료됐어요"
                  : showStep5WaitMessage
                    ? "잠시만 기다려 주세요..."
                    : "수신한 견적서를 비교 분석하고 있어요"}
            </h1>

            <p aria-live="polite">
              {showCompletion ? (
                <>
                  {redirectCountdown ?? 3}초 뒤에 자동으로 견적 검토 페이지로
                  이동해요.
                </>
              ) : analysisState === "error" ? null : (
                <>
                  {projectData.projectName || projectData.companyName || "프로젝트"}
                  의 견적서를 업로드한 뒤 비교·추천 데이터를 준비해요.
                </>
              )}
            </p>

            {analysisState !== "error" && !showCompletion ? (
              <p
                className="ai-whisper"
                style={{ opacity: descVisible ? 1 : 0 }}
              >
                {SLOT_STEPS[slotIndex].descs[descIndex]}
              </p>
            ) : null}
          </div>

          {analysisState === "error" ? (
            <div className="matching-loading-message warning">
              <b>분석 실패</b>
              <span>{errorMessage}</span>
            </div>
          ) : null}

          {analysisState !== "error" ? (
            <div className="slot-wrap" ref={slotWrapRef}>
              <div className="slot-track" ref={slotTrackRef}>
                {SLOT_STEPS.map((step, index) => {
                  const isDone = showCompletion || index < slotIndex;
                  const isCurrent = !showCompletion && index === slotIndex;

                  return (
                    <div
                      className={`slot-step-card${isCurrent ? " current" : ""}${isDone ? " done" : ""}`}
                      key={step.title}
                    >
                      <div className="slot-step-num">
                        {isDone ? (
                          <i className="fa-solid fa-check" />
                        ) : (
                          index + 1
                        )}
                      </div>
                      <div className="slot-step-body">
                        <div className="slot-step-title">{step.title}</div>
                        <div className="slot-step-desc">{step.desc}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
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
              disabled={!showCompletion}
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
