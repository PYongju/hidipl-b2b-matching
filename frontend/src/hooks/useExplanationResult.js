import { useEffect, useMemo, useState } from "react";
import { fetchExplanation } from "../api/apiClient";
import { createExplanationViewModel } from "../utils/explanationAdapter";
import { isAwaitingMatchHydration } from "../utils/projectMatchHydration";

const EMPTY_EXPLANATION_VIEW_MODEL = {
  isFallback: false,
  overallSummary: "AI 근거 요약을 준비 중입니다.",
  provider: "unknown",
  supplierExplanations: [],
  warnings: [],
};

function getProjectApiId(projectData) {
  return projectData.projectApiId;
}

function getMatchId(projectData) {
  return projectData.matchId;
}

function useExplanationResult(projectData, suppliers) {
  const forcedState = projectData.explanationState;
  const projectId = getProjectApiId(projectData);
  const matchId = getMatchId(projectData);
  const cachedExplanation = projectData.cachedExplanation ?? null;
  const awaitingHydration = isAwaitingMatchHydration(projectData);
  const apiParamError = useMemo(() => {
    if (forcedState || cachedExplanation || awaitingHydration) return null;
    if (!projectId || !matchId) {
      return new Error("AI 근거를 불러올 준비가 아직 안 됐어요. 이전 단계를 다시 확인해 주세요.");
    }
    return null;
  }, [awaitingHydration, cachedExplanation, forcedState, matchId, projectId]);
  const [apiState, setApiState] = useState({
    error: null,
    rawResponse: null,
    state: "loading",
  });

  useEffect(() => {
    let ignore = false;

    if (forcedState === "loading" || forcedState === "error") {
      return () => {
        ignore = true;
      };
    }

    if (cachedExplanation) {
      setApiState({
        error: null,
        rawResponse: cachedExplanation,
        state: "ready",
      });
      return () => {
        ignore = true;
      };
    }

    if (awaitingHydration || apiParamError) {
      return () => {
        ignore = true;
      };
    }

    fetchExplanation(projectId, matchId)
      .then((response) => {
        if (!ignore) {
          setApiState({ error: null, rawResponse: response, state: "ready" });
        }
      })
      .catch((error) => {
        if (!ignore) {
          setApiState({ error, rawResponse: null, state: "error" });
        }
      });

    return () => {
      ignore = true;
    };
  }, [
    apiParamError,
    awaitingHydration,
    cachedExplanation,
    forcedState,
    matchId,
    projectId,
  ]);

  const explanationState =
    forcedState
    ?? (cachedExplanation ? "ready" : null)
    ?? (awaitingHydration ? "loading" : null)
    ?? (apiParamError ? "error" : apiState.state);
  const rawResponse = cachedExplanation ?? apiState.rawResponse;
  const explanationErrorMessage =
    projectData.explanationErrorMessage ??
    apiParamError?.message ??
    apiState.error?.message ??
    "AI 근거 요약을 불러오지 못했어요.";

  const explanation = useMemo(() => {
    if (explanationState === "error") {
      return {
        ...EMPTY_EXPLANATION_VIEW_MODEL,
        isFallback: true,
        overallSummary: explanationErrorMessage,
        warnings: [explanationErrorMessage],
      };
    }

    if (explanationState !== "ready" || !rawResponse) {
      return EMPTY_EXPLANATION_VIEW_MODEL;
    }

    return createExplanationViewModel(rawResponse, suppliers);
  }, [explanationErrorMessage, explanationState, rawResponse, suppliers]);

  return {
    ...explanation,
    explanationErrorMessage,
    explanationState,
  };
}

export default useExplanationResult;
