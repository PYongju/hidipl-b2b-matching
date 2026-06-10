function createCandidatePartnerViewModel(response) {
  const candidates =
    response?.candidate_vendors ??
    response?.candidates ??
    response?.data?.candidate_vendors ??
    response?.data?.candidates ??
    [];

  return candidates.map((candidate, index) => {
    const cautionReasons = [
      ...(candidate.filter_reasons ?? []),
      ...(candidate.check_required ?? []),
    ].filter(Boolean);
    const score =
      candidate.semantic_similarity_score ?? candidate.cosine_similarity ?? candidate.score ?? 0;
    const vendorName =
      candidate.vendor_name ?? candidate.partner_name ?? candidate.name ?? "업체명 확인 필요";

    return {
      id:
        candidate.vendor_id ??
        candidate.vendor_name ??
        candidate.partner_id ??
        candidate.partner_name ??
        `partner-${index}`,
      name: vendorName,
      score: toPercent(score),
      specialty: formatSpecialty(candidate.specialty_tags),
      cases: candidate.metadata?.case_count ?? candidate.cases ?? 0,
      premium: Boolean(candidate.is_premium),
      response: candidate.response_speed ?? "미확인",
      recommended: candidate.business_rule_passed === true && !candidate.is_excluded,
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
