import {
  extendedCompareResponse,
  failureCompareResponse,
  normalCompareResponse,
} from "./mockCompareResponse";

function getMockCompareResponse(projectData) {
  if (projectData?.failureScenario) return failureCompareResponse;
  if (projectData?.manyQuotesScenario) return extendedCompareResponse;
  return normalCompareResponse;
}

export default getMockCompareResponse;
