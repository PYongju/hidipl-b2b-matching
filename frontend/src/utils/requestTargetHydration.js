import { getCandidateVendors } from "../api/apiClient";

const RANK_EXCLUSION_PATTERN = /^상위 \d+개 추천 후보 외$/;

function parseCandidateVendorResponse(response) {
  const payload = response?.data?.data ?? response?.data ?? response;
  const vendors =
    payload?.candidate_vendors ??
    response?.data?.data?.candidate_vendors ??
    response?.data?.candidate_vendors ??
    response?.candidate_vendors ??
    [];
  const requestedVendorIds =
    payload?.requested_vendor_ids ??
    response?.data?.data?.requested_vendor_ids ??
    response?.data?.requested_vendor_ids ??
    response?.requested_vendor_ids ??
    [];

  return { vendors, requestedVendorIds };
}

function buildRequestTargetFromVendor(raw, targetId) {
  if (!raw) {
    return { id: targetId, name: String(targetId) };
  }

  return {
    id: targetId,
    name: raw.vendor_name ?? raw.partner_name ?? raw.name ?? String(targetId),
    score:
      typeof raw.semantic_similarity_score === "number"
        ? raw.semantic_similarity_score <= 1
          ? Math.round(raw.semantic_similarity_score * 100)
          : Math.round(raw.semantic_similarity_score)
        : null,
    caution: (raw.filter_reasons ?? []).some(
      (reason) => !RANK_EXCLUSION_PATTERN.test(String(reason ?? "").trim()),
    ),
  };
}

function buildRequestTargetsFromVendors(targetIds, vendorList) {
  return targetIds.map((targetId) => {
    const raw = vendorList.find(
      (candidate) =>
        (candidate.vendor_id ??
          candidate.vendor_name ??
          candidate.partner_id ??
          candidate.partner_name) === targetId,
    );

    return buildRequestTargetFromVendor(raw, targetId);
  });
}

export function shouldHydrateRequestTargets(projectData) {
  if (!projectData?.projectApiId) return false;

  const hasTargetIds = (projectData.requestTargetIds?.length ?? 0) > 0;
  const hasVendors = (projectData.candidateVendors?.length ?? 0) > 0;
  const hasRequestTargets = (projectData.requestTargets?.length ?? 0) > 0;

  if (hasTargetIds && hasVendors && hasRequestTargets) return false;
  if (hasTargetIds && hasRequestTargets) return false;

  return !hasTargetIds || !hasVendors || !hasRequestTargets;
}

export function applyRequestTargetHydration(current, response) {
  const { vendors, requestedVendorIds } = parseCandidateVendorResponse(response);
  const next = { ...current };
  let changed = false;

  if (vendors.length > 0 && !(current.candidateVendors?.length > 0)) {
    next.candidateVendors = vendors;
    next.candidateVendorsLoaded = true;
    changed = true;
  }

  const vendorList =
    vendors.length > 0 ? vendors : (current.candidateVendors ?? []);
  const nextTargetIds =
    requestedVendorIds.length > 0
      ? requestedVendorIds
      : (current.requestTargetIds ?? []);

  if (requestedVendorIds.length > 0) {
    next.requestTargetIds = requestedVendorIds;
    changed = true;
  }

  if (
    nextTargetIds.length > 0 &&
    (!(current.requestTargets?.length > 0) || requestedVendorIds.length > 0)
  ) {
    next.requestTargets = buildRequestTargetsFromVendors(
      nextTargetIds,
      vendorList,
    );
    changed = true;
  }

  return changed ? next : current;
}

export async function hydrateRequestTargets(projectApiId, onProjectDataChange) {
  try {
    const response = await getCandidateVendors(projectApiId);
    onProjectDataChange((current) => ({
      ...applyRequestTargetHydration(current, response),
      candidateVendorsHydrationAttempted: true,
    }));
  } catch (error) {
    console.error("후보 공급사 조회 실패:", error);
    onProjectDataChange((current) => ({
      ...current,
      candidateVendorsHydrationAttempted: true,
    }));
  }
}
