import { createMatchViewModel } from "./matchAdapter";

function extractQuoteIds(matchesPayload) {
  const recommendation = matchesPayload?.recommendation ?? {};
  const items = recommendation.all_items ?? recommendation.items ?? [];

  return [
    ...new Set(
      items.map((item) => item.quote_id ?? item.quoteId).filter(Boolean),
    ),
  ];
}

function buildHydratedProjectFields(matchesResponse, currentData = {}) {
  const payload = matchesResponse ?? {};
  const matchId =
    payload.match_id ?? payload.matchId ?? currentData.matchId ?? null;
  const quoteIds = extractQuoteIds(payload);
  const cachedExplanation = payload.explanation ?? null;

  return {
    matchId,
    quoteIds:
      currentData.quoteIds?.length > 0
        ? currentData.quoteIds
        : quoteIds.length > 0
          ? quoteIds
          : [],
    matchResult: createMatchViewModel(matchesResponse),
    cachedExplanation,
  };
}

function shouldHydrateMatchData(projectData) {
  if (!projectData?.projectApiId) return false;

  const status = projectData.serverStatus ?? projectData.status;
  const isMatchedProject =
    status === "matched" || projectData.lastScreen === "dashboard";

  if (!isMatchedProject) return false;

  const hasQuoteIds =
    Array.isArray(projectData.quoteIds) && projectData.quoteIds.length > 0;
  const hasExplanationSource = Boolean(
    projectData.matchId || projectData.cachedExplanation,
  );

  return !hasQuoteIds || !hasExplanationSource;
}

function isAwaitingMatchHydration(projectData) {
  if (!projectData?.projectApiId) return false;
  if (projectData.matchHydrationAttempted) return false;
  if (projectData.matchId || projectData.cachedExplanation) return false;

  const status = projectData.serverStatus ?? projectData.status;
  return status === "matched" || projectData.lastScreen === "dashboard";
}

export {
  buildHydratedProjectFields,
  extractQuoteIds,
  isAwaitingMatchHydration,
  shouldHydrateMatchData,
};
