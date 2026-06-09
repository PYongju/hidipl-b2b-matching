const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function request(endpoint, options = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...options.headers,
    },
    ...options,
  });

  const payload = await parseJson(response);

  if (!response.ok) {
    throw new Error(
      payload?.error?.message ?? payload?.message ?? "API request failed",
    );
  }

  if (payload && typeof payload === "object" && "ok" in payload) {
    if (!payload.ok) {
      throw new Error(payload.error?.message ?? "API request failed");
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
    throw new Error("API response is not valid JSON");
  }
}

function createProject(project) {
  return request("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(project),
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

function runProjectMatch(projectId, topN = 3, runExplanation = true, explanationProvider = null) {
  return request(`/api/v1/projects/${projectId}/matches`, {
    method: "POST",
    body: JSON.stringify({
      quote_top_n: topN,
      run_explanation: runExplanation,
      explanation_provider: explanationProvider,
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

export {
  createProject,
  fetchCompare,
  fetchExplanation,
  request,
  runProjectMatch,
  uploadProjectQuotes,
};
