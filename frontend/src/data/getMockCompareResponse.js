import { failureCompareResponse, normalCompareResponse } from "./mockCompareResponse";

function getMockCompareResponse(projectData) {
  return projectData?.failureScenario ? failureCompareResponse : normalCompareResponse;
}

export default getMockCompareResponse;
