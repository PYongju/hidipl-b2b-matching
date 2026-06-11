function createMatchViewModel(response) {
  const source = response?.data ?? response ?? {};
  const match = source.match ?? source.latest_match ?? source.result ?? source;

  return {
    matchId: getFirstValue(
      match.match_id,
      match.id,
      source.match_id,
      source.id,
    ),
    project: source.project ?? match.project ?? null,
    requirement: source.requirement ?? match.requirement ?? null,
    quotePool: source.quote_pool ?? source.quotePool ?? match.quote_pool ?? match.quotePool ?? [],
    matches: normalizeMatchRows(match.matches ?? match.rows ?? source.matches ?? source.rows),
    raw: source,
  };
}

function normalizeMatchRows(rows) {
  if (!Array.isArray(rows)) return [];
  return rows;
}

function getFirstValue(...values) {
  return values.find((value) => value !== undefined && value !== null && value !== "");
}

export { createMatchViewModel };
