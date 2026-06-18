const STORAGE_PREFIX = "hidipl_project_quote_ids:";

export function loadQuoteIdsFromStorage(projectApiId) {
  if (!projectApiId) return [];
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${projectApiId}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveQuoteIdsToStorage(projectApiId, quoteIds) {
  if (!projectApiId || !Array.isArray(quoteIds) || !quoteIds.length) return;
  localStorage.setItem(
    `${STORAGE_PREFIX}${projectApiId}`,
    JSON.stringify(quoteIds),
  );
}
