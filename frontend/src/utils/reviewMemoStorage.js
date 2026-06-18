const STORAGE_PREFIX = "hidipl_review_memo:";

function decodeEscapedString(value) {
  return String(value)
    .replace(/\\n/g, "\n")
    .replace(/\\r/g, "\r")
    .replace(/\\t/g, "\t")
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\\\/g, "\\");
}

function extractDashboardMemoFromObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }

  if (typeof value.dashboard === "string") {
    return value.dashboard;
  }

  if (
    value.notes &&
    typeof value.notes === "object" &&
    !Array.isArray(value.notes) &&
    typeof value.notes.dashboard === "string"
  ) {
    return value.notes.dashboard;
  }

  return undefined;
}

function extractDashboardMemoFromString(value) {
  if (typeof value !== "string") return undefined;

  try {
    const parsed = JSON.parse(value);
    const fromJson = extractDashboardMemoFromObject(parsed);
    if (fromJson !== undefined) return fromJson;
  } catch {
    // Fall through to regex parsing for Python-style dict strings.
  }

  const directPatterns = [
    /['"]dashboard['"]\s*:\s*"((?:\\.|[^"\\])*)"/s,
    /['"]dashboard['"]\s*:\s*'((?:\\.|[^'\\])*)'/s,
  ];

  for (const pattern of directPatterns) {
    const match = value.match(pattern);
    if (match) {
      return decodeEscapedString(match[1]);
    }
  }

  const nestedPatterns = [
    /['"]notes['"]\s*:\s*\{[\s\S]*?['"]dashboard['"]\s*:\s*"((?:\\.|[^"\\])*)"/s,
    /['"]notes['"]\s*:\s*\{[\s\S]*?['"]dashboard['"]\s*:\s*'((?:\\.|[^'\\])*)'/s,
  ];

  for (const pattern of nestedPatterns) {
    const match = value.match(pattern);
    if (match) {
      return decodeEscapedString(match[1]);
    }
  }

  return undefined;
}

export function extractDashboardReviewMemo(internalNotes) {
  const fromObject = extractDashboardMemoFromObject(internalNotes);
  if (fromObject !== undefined) return fromObject;
  return extractDashboardMemoFromString(internalNotes);
}

export function loadReviewMemoFromStorage(projectId) {
  if (!projectId) return null;

  try {
    return localStorage.getItem(`${STORAGE_PREFIX}${projectId}`);
  } catch {
    return null;
  }
}

export function saveReviewMemoToStorage(projectId, reviewMemo) {
  if (!projectId) return;

  try {
    localStorage.setItem(`${STORAGE_PREFIX}${projectId}`, reviewMemo ?? "");
  } catch {
    // Ignore storage failures and keep the server save as the source of truth.
  }
}

export function resolveReviewMemo(projectData = {}, internalNotes) {
  const fromInternalNotes = extractDashboardReviewMemo(internalNotes);
  if (fromInternalNotes !== undefined) return fromInternalNotes;

  if (projectData.reviewMemo !== undefined && projectData.reviewMemo !== null) {
    return String(projectData.reviewMemo);
  }

  const projectId = projectData.projectApiId ?? projectData.projectId;
  const fromStorage = loadReviewMemoFromStorage(projectId);
  return fromStorage ?? "";
}
