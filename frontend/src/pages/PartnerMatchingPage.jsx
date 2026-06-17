import { useEffect, useMemo, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectStepTabs from "../components/ProjectStepTabs";
import {
  fetchProjectMatches,
  getCandidateVendors,
  updateProject,
} from "../api/apiClient";
import { buildHydratedProjectFields } from "../utils/projectMatchHydration";
import { formatProjectSolutions } from "../utils/projectRequestText";

function shouldRestoreMatchData(projectData) {
  if (!projectData?.projectApiId) return false;
  if (projectData.matchHydrationAttempted) return false;

  const serverStatus = projectData.serverStatus ?? projectData.status;
  if (serverStatus !== "matched") return false;

  const hasQuoteIds =
    Array.isArray(projectData.quoteIds) && projectData.quoteIds.length > 0;
  const hasExplanationSource = Boolean(
    projectData.matchId ||
    projectData.cachedExplanation ||
    projectData.matchResult,
  );

  return !hasQuoteIds || !hasExplanationSource;
}

function normalizeSimilarityScore(value) {
  if (typeof value !== "number") return 0;
  return value <= 1 ? Math.round(value * 100) : Math.round(value);
}

function normalizeResponseSpeed(value) {
  if (typeof value === "number") return `${value}시간`;
  return value ?? "미확인";
}

function parseResponseHours(value) {
  if (typeof value === "number") return value;
  const parsed = parseFloat(String(value ?? ""));
  return Number.isFinite(parsed) ? parsed : Number.POSITIVE_INFINITY;
}

const RANK_EXCLUSION_PATTERN = /^상위 \d+개 추천 후보 외$/;

function hasRealCaution(filterReasons) {
  return filterReasons.some(
    (reason) => !RANK_EXCLUSION_PATTERN.test(String(reason ?? "").trim()),
  );
}

function normalizeCandidateVendor(raw, index) {
  const filterReasons = raw.filter_reasons ?? [];
  const checkRequired = raw.check_required ?? [];
  const vendorName =
    raw.vendor_name ?? raw.partner_name ?? raw.name ?? `공급사 ${index + 1}`;
  const caseCount =
    raw.installation_count ??
    raw.case_count ??
    raw.cases ??
    raw.metadata?.installation_count ??
    raw.metadata?.case_count ??
    0;
  const rank = raw.rank ?? index + 1;
  const businessRulePassed =
    raw.business_rule_passed === true && raw.is_excluded !== true;
  const caution = Boolean(
    raw.caution ?? (hasRealCaution(filterReasons) || checkRequired.length > 0),
  );
  const defaultReason =
    checkRequired.join(", ") ||
    filterReasons.join(", ") ||
    (businessRulePassed
      ? "요구사항 기준 추천 가능 공급사"
      : "추천 기준 미충족");

  return {
    id:
      raw.vendor_id ??
      raw.vendor_name ??
      raw.partner_id ??
      raw.partner_name ??
      `partner-${index}`,
    name: vendorName,
    rank,
    score: normalizeSimilarityScore(raw.final_score),
    specialty: Array.isArray(raw.specialty_tags)
      ? raw.specialty_tags.join(", ")
      : "전문 분야 미확인",
    cases: caseCount,
    premium: Boolean(raw.is_premium),
    response: normalizeResponseSpeed(raw.response_speed),
    businessRulePassed,
    recommended: businessRulePassed && rank <= 10,
    caution,
    reason: caution ? "이전에 납기 지연이 있었던 공급사예요." : defaultReason,
  };
}

export default function PartnerMatchingPage({
  projectData,
  onBack,
  onGoDashboard,
  onProjectDataChange,
  onGoHome,
}) {
  const [targetIds, setTargetIds] = useState(
    projectData.requestTargetIds ?? [],
  );
  const [showAllPartners, setShowAllPartners] = useState(true);

  useEffect(() => {
    setTargetIds(projectData.requestTargetIds ?? []);
  }, [projectData.requestTargetIds]);

  useEffect(() => {
    let ignore = false;
    const apiProjectId = projectData.projectApiId;

    if (!apiProjectId || !shouldRestoreMatchData(projectData)) {
      return undefined;
    }

    fetchProjectMatches(apiProjectId)
      .then((matchesResponse) => {
        if (ignore) return;
        onProjectDataChange((current) => ({
          ...current,
          ...buildHydratedProjectFields(matchesResponse, current),
          matchHydrationAttempted: true,
        }));
      })
      .catch((error) => {
        console.error("매칭 결과 조회 실패:", error);
        if (ignore) return;
        onProjectDataChange((current) => ({
          ...current,
          matchHydrationAttempted: true,
        }));
      });

    return () => {
      ignore = true;
    };
  }, [
    projectData.projectApiId,
    projectData.matchId,
    projectData.quoteIds,
    projectData.cachedExplanation,
    projectData.matchResult,
    projectData.matchHydrationAttempted,
  ]);

  useEffect(() => {
    const apiProjectId = projectData.projectApiId;
    if (
      !apiProjectId ||
      (projectData.candidateVendors ?? []).length > 0 ||
      projectData.candidateVendorsHydrationAttempted
    )
      return;

    onProjectDataChange((current) => ({
      ...current,
      candidateVendorsHydrationAttempted: true,
    }));

    getCandidateVendors(apiProjectId)
      .then((response) => {
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
        console.log("candidate-vendors 응답:", response); // ← 여기
        console.log("vendors 배열:", vendors);
        onProjectDataChange((current) => {
          const next = { ...current };
          let changed = false;

          if (vendors.length > 0 && !(current.candidateVendors?.length > 0)) {
            next.candidateVendors = vendors;
            next.candidateVendorsLoaded = true;
            changed = true;
          }

          const currentTargetIds = current.requestTargetIds ?? [];
          if (requestedVendorIds.length > 0 && currentTargetIds.length === 0) {
            const vendorSource =
              vendors.length > 0 ? vendors : (current.candidateVendors ?? []);
            const partnerList = vendorSource.map(normalizeCandidateVendor);
            next.requestTargetIds = requestedVendorIds;
            next.requestTargets = partnerList.filter((partner) =>
              requestedVendorIds.includes(partner.id),
            );
            changed = true;
          }

          return changed ? next : current;
        });
      })
      .catch(() => {});
  }, [projectData.projectApiId]);

  const [searchTerm, setSearchTerm] = useState("");
  const [premiumFilter, setPremiumFilter] = useState("all");
  const [sortKey, setSortKey] = useState("ai");
  const candidates = projectData.candidateVendors ?? [];
  const partners = useMemo(
    () => candidates.map(normalizeCandidateVendor),
    [candidates],
  );
  const candidateStatus = projectData.projectApiId
    ? partners.length > 0
      ? "ready"
      : "empty"
    : "missing-project-api-id";

  const recommendedCount = partners.filter(
    (partner) => partner.recommended,
  ).length;
  const businessPassedCount = partners.filter(
    (partner) => partner.businessRulePassed,
  ).length;
  const cautionCount = partners.filter((partner) => partner.caution).length;

  const visiblePartners = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    const base = showAllPartners
      ? partners
      : partners.filter((partner) => partner.recommended);

    return base
      .filter((partner) => {
        const matchesSearch =
          !normalizedSearch ||
          partner.name.toLowerCase().includes(normalizedSearch) ||
          partner.specialty.toLowerCase().includes(normalizedSearch);
        const matchesPremium =
          premiumFilter === "all" ||
          (premiumFilter === "premium" && partner.premium) ||
          (premiumFilter === "standard" && !partner.premium);
        return matchesSearch && matchesPremium;
      })
      .sort((a, b) => {
        if (sortKey === "response") {
          const responseDiff =
            parseResponseHours(a.response) - parseResponseHours(b.response);
          if (responseDiff !== 0) return responseDiff;
          return b.score - a.score || a.rank - b.rank;
        }
        if (sortKey === "cases") {
          const casesDiff = (b.cases ?? 0) - (a.cases ?? 0);
          if (casesDiff !== 0) return casesDiff;
          return b.score - a.score || a.rank - b.rank;
        }
        const scoreDiff = b.score - a.score;
        if (scoreDiff !== 0) return scoreDiff;
        return a.rank - b.rank;
      });
  }, [partners, premiumFilter, searchTerm, showAllPartners, sortKey]);

  const targetPartners = useMemo(
    () => partners.filter((partner) => targetIds.includes(partner.id)),
    [partners, targetIds],
  );
  const cautionPartners = partners.filter((partner) => partner.caution);
  const candidateEmptyMessage = getCandidateEmptyMessage(candidateStatus);

  const persistRequestTargets = (nextTargetIds, partnersList = partners) => {
    onProjectDataChange?.((current) => ({
      ...current,
      requestTargetIds: nextTargetIds,
      requestTargets: partnersList.filter((partner) =>
        nextTargetIds.includes(partner.id),
      ),
    }));
    const apiProjectId = projectData.projectApiId;
    if (apiProjectId) {
      updateProject(apiProjectId, {
        requested_vendor_ids: nextTargetIds,
      }).catch(() => {});
    }
  };

  const updateRequestTargets = (updater) => {
    setTargetIds((current) => {
      const nextTargetIds =
        typeof updater === "function" ? updater(current) : updater;
      persistRequestTargets(nextTargetIds);
      return nextTargetIds;
    });
  };

  const addPartner = (partnerId) => {
    updateRequestTargets((current) =>
      current.includes(partnerId) ? current : [...current, partnerId],
    );
  };

  const removePartner = (partnerId) => {
    updateRequestTargets((current) => current.filter((id) => id !== partnerId));
  };

  const togglePartner = (partnerId) => {
    if (targetIds.includes(partnerId)) {
      removePartner(partnerId);
      return;
    }
    addPartner(partnerId);
  };

  const addRecommendedPartners = () => {
    updateRequestTargets((current) => [
      ...new Set([
        ...current,
        ...partners
          .filter((partner) => partner.recommended)
          .map((partner) => partner.id),
      ]),
    ]);
  };

  const savePartnerDraft = () => {
    onProjectDataChange?.((current) => ({
      ...current,
      lastScreen: "partnerMatching",
      requestTargetIds: targetIds,
      requestTargets: partners.filter((partner) =>
        targetIds.includes(partner.id),
      ),
      currentStage: "요청 대상 검토중",
      workflowStatus: "진행 중",
    }));
  };

  const handleGoQuoteWaiting = () => {
    persistRequestTargets(targetIds);
    onGoDashboard();
  };

  const handleGoBack = () => {
    persistRequestTargets(targetIds);
    onBack();
  };

  return (
    <div className="flow-page partner-page">
      <FlowTopbar
        onHome={onGoHome}
        trail="프로젝트 상세 > 파트너 매칭/견적 요청"
        action={
          <>
            <button
              className="button action-secondary"
              onClick={handleGoBack}
              type="button"
            >
              이전
            </button>
            <div className="avatar" />
            <div className="user-name">
              <b>김담당자</b>
              <small>구매검토팀</small>
            </div>
          </>
        }
      />

      <main className="partner-main">
        <section className="partner-head">
          <div>
            <button
              className="partner-back"
              onClick={handleGoBack}
              type="button"
            >
              ‹
            </button>
            <span>프로젝트 상세</span>
          </div>
        </section>

        <ProjectStepTabs
          activeStep={2}
          onGoRequirements={handleGoBack}
          onGoQuoteWaiting={handleGoQuoteWaiting}
        />

        <section className="partner-project-summary six">
          <SummaryItem
            label="회사명"
            value={projectData.companyName || "미입력"}
          />
          <SummaryItem label="위치" value={projectData.location || "미입력"} />
          <SummaryItem
            label="일정"
            value={projectData.projectDate || "일정 미정"}
          />
          <SummaryItem
            label="발주처 유형"
            value={projectData.clientType || "미입력"}
          />
          <SummaryItem
            label="솔루션"
            value={formatProjectSolutions(projectData, "미선택")}
          />
          <SummaryItem label="상태" value="요청 대상 검토중" />
        </section>

        <section className="partner-notice strong">
          {partners.length === 0
            ? "공급사 추천 결과를 불러오고 있거나, 아직 추천된 공급사가 없어요."
            : `공급사 ${partners.length}개를 순위대로 보여드려요. 상위 ${recommendedCount}개는 AI 추천으로 표시하고, 기준 미충족 공급사는 아래에 따로 보여드려요.`}
        </section>

        <section className="partner-layout">
          <div className="partner-table-panel">
            <div className="partner-tools-top">
              <input
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="공급사명, 전문 분야 검색"
                value={searchTerm}
              />
              <select
                onChange={(event) => setPremiumFilter(event.target.value)}
                value={premiumFilter}
              >
                <option value="all">전체 공급사</option>
                <option value="premium">프리미엄만</option>
                <option value="standard">일반만</option>
              </select>
              <select
                onChange={(event) => setSortKey(event.target.value)}
                value={sortKey}
              >
                <option value="ai">AI 추천 점수순</option>
                <option value="response">응답 빠른순</option>
                <option value="cases">사례 많은순</option>
              </select>
            </div>

            <div className="partner-section-title">
              <div>
                <h2>추천 공급사 목록</h2>
                <p>
                  AI 추천 공급사를 확인한 뒤, 실제로 보낼 공급사만 체크하거나
                  추가해요.
                </p>
              </div>
              <div className="partner-title-actions">
                <div className="partner-count-chips">
                  <Badge tone="blue">AI 추천 {recommendedCount}</Badge>
                  <Badge tone="gray">추천 가능 {businessPassedCount}</Badge>
                  <Badge tone="blue">선택 {targetIds.length}</Badge>
                  <Badge tone="orange">주의 {cautionCount}</Badge>
                  <Badge tone="gray">표시 {visiblePartners.length}</Badge>
                </div>
                <div className="partner-title-buttons">
                  <button
                    className="partner-expand-button partner-expand-button-inline"
                    onClick={() => setShowAllPartners((current) => !current)}
                    type="button"
                  >
                    {showAllPartners
                      ? "AI 추천 공급사만 보기"
                      : "전체 공급사 보기"}
                  </button>
                  <button
                    className="button button-small"
                    onClick={addRecommendedPartners}
                    type="button"
                  >
                    AI 추천 대상 모두 추가
                  </button>
                </div>
              </div>
            </div>

            <div className="partner-table-wrap">
              <table className="partner-table">
                <colgroup>
                  <col className="col-select" />
                  <col className="col-rank" />
                  <col className="col-name" />
                  <col className="col-score" />
                  <col className="col-premium" />
                  <col className="col-cases" />
                  <col className="col-response" />
                  <col className="col-type" />
                  <col className="col-reason" />
                  <col className="col-action" />
                </colgroup>
                <thead>
                  <tr>
                    <th>선택</th>
                    <th>순위</th>
                    <th>공급사명</th>
                    <th>AI 추천 점수</th>
                    <th>프리미엄</th>
                    <th>사례5+</th>
                    <th>응답</th>
                    <th>구분</th>
                    <th>사유</th>
                    <th>요청</th>
                  </tr>
                </thead>
                <tbody>
                  {visiblePartners.length === 0 ? (
                    <tr>
                      <td className="partner-empty-cell" colSpan={10}>
                        <b>{candidateEmptyMessage.title}</b>
                        <span>{candidateEmptyMessage.description}</span>
                      </td>
                    </tr>
                  ) : null}
                  {visiblePartners.map((partner) => {
                    const isTarget = targetIds.includes(partner.id);
                    return (
                      <tr
                        className={[
                          partner.recommended ? "ai-recommended-row" : "",
                          partner.caution ? "caution-row" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        key={partner.id}
                      >
                        <td>
                          <input
                            checked={isTarget}
                            onChange={() => togglePartner(partner.id)}
                            type="checkbox"
                          />
                        </td>
                        <td>{partner.rank}</td>
                        <td>
                          <b>{partner.name}</b>
                          <small>{partner.specialty}</small>
                        </td>
                        <td>{partner.score}/100</td>
                        <td>
                          <Badge tone={partner.premium ? "blue" : "gray"}>
                            {partner.premium ? "가능" : "일반"}
                          </Badge>
                        </td>
                        <td>
                          {partner.cases >= 5 ? "예" : "아니오"}
                          {partner.cases ? ` (${partner.cases}건)` : ""}
                        </td>
                        <td>{partner.response}</td>
                        <td>
                          <Badge
                            tone={
                              partner.caution
                                ? "orange"
                                : partner.recommended
                                  ? "blue"
                                  : "gray"
                            }
                          >
                            {partner.caution
                              ? "주의"
                              : partner.recommended
                                ? "AI 추천"
                                : partner.businessRulePassed
                                  ? "추천 가능"
                                  : "기준 미충족"}
                          </Badge>
                        </td>
                        <td>{partner.reason}</td>
                        <td>
                          <button
                            className="partner-row-action"
                            onClick={() => togglePartner(partner.id)}
                            type="button"
                          >
                            {isTarget ? "제거" : "추가"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <aside className="request-panel">
            <div className="request-card">
              <div className="request-card-head">
                <div>
                  <h2>요청 발송 대상</h2>
                  <p>선택한 공급사를 최종 확인해요.</p>
                </div>
                <div className="request-count-chips">
                  <Badge tone="blue">{targetPartners.length}개 대상</Badge>
                </div>
              </div>

              {targetPartners.length === 0 ? (
                <div className="request-empty">
                  아직 요청 발송 대상이 없어요.
                  <span>
                    AI 추천 대상을 한 번에 추가하거나, 목록에서 개별 공급사를
                    선택해 주세요.
                  </span>
                </div>
              ) : (
                <div className="selected-partner-list">
                  {targetPartners.map((partner) => (
                    <div className="selected-partner-pill" key={partner.id}>
                      <span>
                        <b>{partner.name}</b>
                        <small>
                          AI 추천 점수 {partner.score} · 응답 {partner.response}
                        </small>
                      </span>
                      {partner.caution && <Badge tone="orange">주의</Badge>}
                      <button
                        onClick={() => removePartner(partner.id)}
                        type="button"
                        aria-label={`${partner.name} 제거`}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="blacklist-card neutral">
              <h3>주의 공급사 요약</h3>
              <p>
                총 {cautionPartners.length}개 공급사는 주의 이력이 있어요. 견적
                요청 전에 사유를 확인하고 담당자가 최종 판단해 주세요.
              </p>
              {cautionPartners.map((partner) => (
                <span key={partner.id}>
                  {partner.name}: {partner.reason}
                </span>
              ))}
            </div>

            <label className="request-memo">
              <span>발송 전 메모</span>
              <textarea placeholder="공급사에 전달할 견적 요청 메모를 입력해 주세요." />
            </label>
          </aside>
        </section>
      </main>

      <footer className="partner-bottom-actions">
        <span>
          상태: 요청 대상 검토중 · 발송 대상 {targetPartners.length}개
        </span>
        <div>
          <button
            className="button action-secondary"
            onClick={savePartnerDraft}
            type="button"
          >
            임시 저장
          </button>
          <button
            className="button button-blue"
            disabled
            title="요청 대상 저장은 곧 사용할 수 있어요."
            type="button"
          >
            요청 대상 저장
          </button>
          <button
            className="button action-primary"
            disabled={targetPartners.length === 0}
            onClick={handleGoQuoteWaiting}
            type="button"
          >
            견적 요청 발송
          </button>
        </div>
      </footer>
    </div>
  );
}

function SummaryItem({ label, value }) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function getCandidateEmptyMessage(status) {
  if (status === "loading") {
    return {
      title: "추천 후보를 불러오고 있어요.",
      description: "프로젝트 조건을 기준으로 공급사 후보를 찾고 있어요.",
    };
  }
  if (status === "empty") {
    return {
      title: "추천 후보가 없어요.",
      description:
        "현재 조건으로 찾은 공급사가 없어요. 요구사항을 보완하거나 전체 공급사 조건을 다시 확인해 주세요.",
    };
  }
  if (status === "missing-project-api-id") {
    return {
      title: "프로젝트 정보가 없어요.",
      description:
        "프로젝트 정보가 없어 추천 후보를 불러오지 못했어요. 이전 단계에서 프로젝트를 먼저 저장해 주세요.",
    };
  }
  if (status === "error") {
    return {
      title: "추천 후보를 불러오지 못했어요.",
      description: "잠시 후 다시 시도해 주세요.",
    };
  }
  return {
    title: "표시할 공급사가 없어요.",
    description: "검색어 또는 필터 조건을 조정해 주세요.",
  };
}
