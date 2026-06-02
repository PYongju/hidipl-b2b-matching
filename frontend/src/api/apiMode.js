const hasApiBaseUrl = Boolean(import.meta.env.VITE_API_BASE_URL);

const shouldUseMockApi = import.meta.env.VITE_USE_MOCK_API !== "false" || !hasApiBaseUrl;

export { hasApiBaseUrl, shouldUseMockApi };
