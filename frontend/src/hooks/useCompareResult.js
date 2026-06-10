import { useEffect, useMemo, useState } from "react";
import { fetchCompare } from "../api/apiClient";
import { createCompareViewModel } from "../utils/compareAdapter";

const EMPTY_COMPARE_VIEW_MODEL = {
  comparisonSections: [],
  suppliers: [],
  totalRows: [],
};

function buildCompareRequest(projectData) {
  return {
    project_id: projectData.projectApiId ?? projectData.projectId,
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

  useEffect(() => {
    let ignore = false;

    if (forcedState === "loading" || forcedState === "error") {
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
  }, [forcedState, projectData]);

  const compareState = forcedState ?? apiState.state;
  const rawResponse = apiState.rawResponse;
  const compareErrorMessage =
    projectData.compareErrorMessage ??
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
  };
}

export default useCompareResult;
