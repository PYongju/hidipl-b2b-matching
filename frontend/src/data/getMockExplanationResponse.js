import {
  failureExplanationResponse,
  normalExplanationResponse,
} from "./mockExplanationResponse";

function getMockExplanationResponse(projectData) {
  return projectData?.failureScenario ? failureExplanationResponse : normalExplanationResponse;
}

export default getMockExplanationResponse;
