import { useEffect, useMemo, useState } from "react";
import { fetchCompare } from "../api/apiClient";
import { shouldUseMockApi } from "../api/apiMode";
import getMockCompareResponse from "../data/getMockCompareResponse";
import { createCompareViewModel } from "../utils/compareAdapter";

const EMPTY_COMPARE_VIEW_MODEL = {
  comparisonSections: [],
  suppliers: [],
  totalRows: [],
};

function buildCompareRequest(projectData) {
  return {
    project_id: projectData.projectApiId,
    quote_ids: projectData.quoteIds,
    match_id: projectData.matchId,
  };
}

function useCompareResult(projectData) {
  const forcedState = projectData.compareState;
  const [apiState, setApiState] = useState({
    error: null,
    rawResponse: null,
    state: "loading",
  });
  const mockResponse = useMemo(() => getMockCompareResponse(projectData), [projectData]);
  const apiParamError = useMemo(
    () =>
      !shouldUseMockApi && !forcedState && !projectData.projectApiId
        ? new Error("비교 검토에 필요한 projectApiId가 없습니다.")
        : null,
    [forcedState, projectData.projectApiId],
  );

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
      setApiState({ error: apiParamError, rawResponse: null, state: "error" });
      return () => {
        ignore = true;
      };
    }

    fetchCompare(buildCompareRequest(projectData))
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
  }, [apiParamError, forcedState, projectData.projectApiId, projectData.quoteIds, projectData.matchId]);

  const compareState = forcedState ?? (apiParamError ? "error" : shouldUseMockApi ? "ready" : apiState.state);
  const rawResponse = shouldUseMockApi ? mockResponse : apiState.rawResponse;
  const compareErrorMessage =
    projectData.compareErrorMessage ??
    apiParamError?.message ??
    apiState.error?.message ??
    "견적 비교 데이터를 불러오지 못했습니다.";

  const viewModel = useMemo(() => {
    if (compareState !== "ready" || !rawResponse) {
      return EMPTY_COMPARE_VIEW_MODEL;
    }

    return createCompareViewModel(rawResponse);
  }, [compareState, rawResponse]);

  return {
    ...viewModel,
    compareErrorMessage,
    compareState,
    isMockCompare: shouldUseMockApi,
  };
}

export default useCompareResult;
