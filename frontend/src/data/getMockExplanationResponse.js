import {
  extendedExplanationResponse,
  failureExplanationResponse,
  normalExplanationResponse,
} from "./mockExplanationResponse";

function getMockExplanationResponse(projectData) {
  if (projectData?.failureScenario) return failureExplanationResponse;
  if (projectData?.manyQuotesScenario) return extendedExplanationResponse;
  return normalExplanationResponse;
}

export default getMockExplanationResponse;
