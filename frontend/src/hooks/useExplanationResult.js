import { useEffect, useMemo, useState } from "react";
import { fetchExplanation } from "../api/apiClient";
import { shouldUseMockApi } from "../api/apiMode";
import getMockExplanationResponse from "../data/getMockExplanationResponse";
import { createExplanationViewModel } from "../utils/explanationAdapter";

const EMPTY_EXPLANATION_VIEW_MODEL = {
  isFallback: false,
  overallSummary: "AI 근거 요약을 준비 중입니다.",
  provider: "unknown",
  supplierExplanations: [],
  warnings: [],
};

function getProjectApiId(projectData) {
  return projectData.projectApiId ?? projectData.projectId;
}

function getMatchId(projectData) {
  return projectData.matchId;
}

function useExplanationResult(projectData, suppliers) {
  const forcedState = projectData.explanationState;
  const projectId = getProjectApiId(projectData);
  const matchId = getMatchId(projectData);
  const apiParamError = useMemo(
    () =>
      !shouldUseMockApi && !forcedState && (!projectId || !matchId)
        ? new Error("AI 근거 조회에 필요한 project_id 또는 match_id가 없습니다.")
        : null,
    [forcedState, matchId, projectId]
  );
  const [apiState, setApiState] = useState({
    error: null,
    rawResponse: null,
    state: "loading",
  });
  const mockResponse = useMemo(() => getMockExplanationResponse(projectData), [projectData]);

  useEffect(() => {
    let ignore = false;

    if (forcedState === "loading" || forcedState === "error") {
      return () => {
        ignore = true;
      };
    }

    if (shouldUseMockApi) {
      return () => {
        ignore = true;
      };
    }

    if (apiParamError) {
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
  }, [apiParamError, forcedState, matchId, projectData, projectId]);

  const explanationState = forcedState ?? (apiParamError ? "error" : shouldUseMockApi ? "ready" : apiState.state);
  const rawResponse = shouldUseMockApi ? mockResponse : apiState.rawResponse;
  const explanationErrorMessage =
    projectData.explanationErrorMessage ??
    apiParamError?.message ??
    apiState.error?.message ??
    "AI 근거 요약을 불러오지 못했습니다.";

  const explanation = useMemo(() => {
    if (explanationState === "error") {
      return {
        ...createExplanationViewModel(mockResponse, suppliers),
        isFallback: true,
        warnings: [explanationErrorMessage],
      };
    }

    if (explanationState !== "ready" || !rawResponse) {
      return EMPTY_EXPLANATION_VIEW_MODEL;
    }

    return createExplanationViewModel(rawResponse, suppliers);
  }, [explanationErrorMessage, explanationState, mockResponse, rawResponse, suppliers]);

  return {
    ...explanation,
    explanationErrorMessage,
    explanationState,
    isMockExplanation: shouldUseMockApi,
  };
}

export default useExplanationResult;
