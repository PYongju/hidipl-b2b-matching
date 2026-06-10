function createCandidatePartnerViewModel(response) {
  const candidates = response?.candidates ?? response?.data?.candidates ?? [];

  return candidates.map((candidate, index) => {
    const cautionReasons = [
      ...(candidate.filter_reasons ?? []),
      ...(candidate.check_required ?? []),
    ].filter(Boolean);
    const score = candidate.semantic_similarity_score ?? candidate.score ?? 0;
    const trust = candidate.success_rate ?? candidate.trust ?? 0;

    return {
      id: candidate.partner_id || candidate.partner_name || `partner-${index}`,
      name: candidate.partner_name || "업체명 확인 필요",
      score: toPercent(score),
      specialty: formatSpecialty(candidate.specialty_tags),
      cases: candidate.metadata?.case_count ?? 0,
      premium: Boolean(candidate.is_premium),
      priceScore: candidate.metadata?.price_score ?? null,
      response: candidate.response_speed || "미확인",
      trust: toPercent(trust),
      recommended: candidate.business_rule_passed !== false && !candidate.is_excluded,
      caution: Boolean(candidate.is_excluded || cautionReasons.length),
      reason: cautionReasons.join(", ") || "요구사항 기준 추천 가능 업체",
      businessStage: candidate.business_stage || "",
    };
  });
}

function toPercent(value) {
  if (typeof value !== "number") return 0;
  return value <= 1 ? Math.round(value * 100) : Math.round(value);
}

function formatSpecialty(tags) {
  if (Array.isArray(tags) && tags.length > 0) return tags.join(", ");
  return "전문 분야 미확인";
}

export { createCandidatePartnerViewModel };
