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
  const apiParamError = useMemo(
    () =>
      !forcedState && !projectData.projectApiId
        ? new Error("비교할 프로젝트 정보가 없어요. 견적서를 업로드한 뒤 다시 시도해 주세요.")
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
          // 기술 상세(에러 원문)는 콘솔로만 남기고, 화면에는 행동 중심 문구를 노출
          console.error("견적 비교 데이터 조회 실패:", error);
          setApiState({ error, rawResponse: null, state: "error" });
        }
      });

    return () => {
      ignore = true;
    };
  }, [apiParamError, forcedState, projectData.projectApiId, projectData.quoteIds, projectData.matchId]);

  const compareState = forcedState ?? (apiParamError ? "error" : apiState.state);
  const rawResponse = apiState.rawResponse;
  const compareErrorMessage =
    projectData.compareErrorMessage ??
    apiParamError?.message ??
    "일시적인 문제로 비교 데이터를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.";

  const viewModel = useMemo(() => {
    if (compareState !== "ready" || !rawResponse) {
      return EMPTY_COMPARE_VIEW_MODEL;
    }

    return createCompareViewModel(rawResponse, {
      quoteFileCount: projectData.quoteFiles?.length,
      quoteIds: projectData.quoteIds,
    });
  }, [compareState, rawResponse, projectData.quoteFiles?.length, projectData.quoteIds]);

  return {
    ...viewModel,
    compareErrorMessage,
    compareState,
  };
}

export default useCompareResult;
