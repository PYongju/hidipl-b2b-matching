const STORAGE_PREFIX = "hidipl_compare_cell_overrides:";

export function getCompareCellOverrideKey(supplierId, rowLabel) {
  return `${supplierId}::${rowLabel}`;
}

function parseJsonRecord(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value;
}

function parseOverridesValue(value) {
  if (!value) return {};
  if (typeof value === "object" && !Array.isArray(value)) return value;
  if (typeof value !== "string") return {};

  try {
    const parsed = JSON.parse(value);
    return parseJsonRecord(parsed);
  } catch {
    return {};
  }
}

export function loadCompareCellOverridesFromStorage(projectApiId) {
  if (!projectApiId) return {};

  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${projectApiId}`);
    if (!raw) return {};
    return parseOverridesValue(raw);
  } catch {
    return {};
  }
}

export function saveCompareCellOverridesToStorage(projectApiId, overrides) {
  if (!projectApiId) return;
  localStorage.setItem(`${STORAGE_PREFIX}${projectApiId}`, JSON.stringify(overrides));
}

export function resolveCompareCellOverrides(projectData = {}) {
  const projectApiId = projectData.projectApiId ?? projectData.projectId;
  const fromStorage = loadCompareCellOverridesFromStorage(projectApiId);
  const fromProject = parseJsonRecord(projectData.compareCellOverrides);

  return {
    ...fromStorage,
    ...fromProject,
  };
}

export function applyCompareCellOverride(cell, supplierId, rowLabel, overrides = {}) {
  const overrideKey = getCompareCellOverrideKey(supplierId, rowLabel);
  const overriddenValue = overrides[overrideKey];
  if (overriddenValue === undefined) return cell;

  return {
    ...cell,
    value: overriddenValue,
    status: undefined,
    highlight: undefined,
  };
}
