import { msalInstance } from "../auth/msalInstance";
import { loginRequest } from "../auth/msalConfig";

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const API_BASE_URL = configuredApiBaseUrl
  ? configuredApiBaseUrl.replace(/\/$/, "")
  : import.meta.env.DEV
    ? "http://localhost:8000"
    : "";

async function getAccessToken() {
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length === 0) return null;

  try {
    const response = await msalInstance.acquireTokenSilent({
      ...loginRequest,
      account: accounts[0],
    });
    return response.accessToken;
  } catch {
    await msalInstance.acquireTokenRedirect(loginRequest);
    return null;
  }
}

async function request(endpoint, options = {}) {
  const token = await getAccessToken();

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...options,
  });

  const payload = await parseJson(response);

  if (!response.ok) {
    throw new Error(
      getApiErrorMessage(
        payload,
        "요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.",
      ),
    );
  }

  if (payload && typeof payload === "object" && "ok" in payload) {
    if (!payload.ok) {
      throw new Error(
        getApiErrorMessage(
          payload,
          "요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.",
        ),
      );
    }
    return payload.data;
  }

  return payload;
}

async function parseJson(response) {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    throw new Error("응답을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.");
  }
}

function getApiErrorMessage(payload, fallback) {
  if (!payload || typeof payload !== "object") return fallback;

  const detail = payload.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return (
      detail
        .map((item) => item?.msg ?? item?.message ?? JSON.stringify(item))
        .filter(Boolean)
        .join("\n") || fallback
    );
  }
  if (detail && typeof detail === "object") {
    return detail.message ?? detail.msg ?? JSON.stringify(detail);
  }

  if (typeof payload.error === "string") return payload.error;
  return payload.error?.message ?? payload.message ?? fallback;
}

function createProject(project) {
  return request("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(project),
  });
}

function fetchProject(projectId) {
  return request(`/api/v1/projects/${projectId}`, {
    method: "GET",
  });
}

function uploadProjectQuotes(projectId, files) {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file);
  });

  return request(`/api/v1/projects/${projectId}/quotes`, {
    method: "POST",
    body: formData,
  });
}

function runProjectMatch(
  projectId,
  topN = 3,
  runExplanation = true,
  explanationProvider = null,
) {
  return request(`/api/v1/projects/${projectId}/matches`, {
    method: "POST",
    body: JSON.stringify({
      quote_top_n: topN,
      run_explanation: runExplanation,
      explanation_provider: explanationProvider,
    }),
  });
}

function fetchProjectMatches(projectId) {
  return request(`/api/v1/projects/${projectId}/matches`, {
    method: "GET",
  });
}

function fetchCandidateVendors(projectId, quoteTopN = 10) {
  return request(`/api/v1/projects/${projectId}/candidate-vendors`, {
    method: "POST",
    body: JSON.stringify({
      quote_top_n: quoteTopN,
    }),
  });
}

function fetchCompare(compareRequest) {
  const projectId = compareRequest.project_id;
  return request(`/api/v1/projects/${projectId}/compare`, {
    method: "POST",
    body: JSON.stringify({
      quote_ids: compareRequest.quote_ids,
      top_n: compareRequest.top_n ?? null,
    }),
  });
}

function fetchExplanation(projectId, matchId) {
  return request(
    `/api/v1/projects/${projectId}/matches/${matchId}/explanation`,
    {
      method: "GET",
    },
  );
}

function updateProject(projectId, data) {
  return request(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

function saveInternalNotes(projectId, body) {
  return request(`/api/v1/projects/${projectId}/internal-notes`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

function fetchProjects() {
  return request("/api/v1/projects", {
    method: "GET",
  });
}

function deleteProjects(projectIds) {
  return request("/api/v1/projects", {
    method: "DELETE",
    body: JSON.stringify({ project_ids: projectIds }),
  });
}

function getCandidateVendors(projectId) {
  return request(`/api/v1/projects/${projectId}/candidate-vendors`, {
    method: "GET",
  });
}

function updateCandidateVendorField(projectId, vendorName, fields) {
  return request(
    `/api/v1/projects/${projectId}/candidate-vendors/${encodeURIComponent(vendorName)}`,
    {
      method: "PATCH",
      body: JSON.stringify(fields),
    },
  );
}

export {
  createProject,
  deleteProjects, // 6/12 백엔드 작업에서 추가
  fetchCandidateVendors,
  getCandidateVendors,
  fetchCompare,
  fetchExplanation,
  fetchProject,
  fetchProjectMatches, // 6/12 백엔드 작업에서 추가
  fetchProjects, // 6/12 백엔드 작업에서 추가
  request,
  runProjectMatch,
  saveInternalNotes,
  updateCandidateVendorField,
  updateProject,
  uploadProjectQuotes,
};
