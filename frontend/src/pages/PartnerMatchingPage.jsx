import { useEffect, useMemo, useRef, useState } from "react";
import AutoSaveStatus from "../components/AutoSaveStatus";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectDetailHeader from "../components/ProjectDetailHeader";
import ProjectStepTabs from "../components/ProjectStepTabs";
import {
  fetchProjectMatches,
  getCandidateVendors,
  updateProject,
} from "../api/apiClient";
import { buildHydratedProjectFields } from "../utils/projectMatchHydration";
import { formatProjectSolutions } from "../utils/projectRequestText";

const DEFAULT_VISIBLE_PARTNERS = 15;
const RANK_EXCLUSION_PATTERN = /^상위 \d+개 추천 후보 외$/;

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
      ? "요구사항 기준 추천 가능한 공급사예요."
      : "추천 기준을 아직 충족하지 않았어요.");

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
    reason: caution ? "검토가 필요한 이력이 있어요." : defaultReason,
  };
}

function buildRequestMessage(partner, projectData) {
  const partnerName = partner?.name || "[업체명]";
  const companyName = projectData.companyName || "고객사 미입력";
  const projectName = projectData.projectName || "프로젝트 미입력";
  const location = projectData.location || "미입력";
  const schedule = projectData.projectDate || "일정 미정";
  const solutionText = formatProjectSolutions(projectData, "미선택");
  const displaySize = projectData.displaySize || "미입력";
  const quantity = projectData.quantity || "미입력";
  const budget = projectData.budgetAmount || "미입력";
  const usage = projectData.usage || "상세 활용 용도는 요청사항 문서를 참고해 주세요.";
  const extra = projectData.otherConditions?.trim();

  return [
    `안녕하세요 ${partnerName} 담당자님`,
    "하이디플을 통해 견적 요청 드립니다.",
    "",
    "[프로젝트 개요]",
    `- 고객사: ${companyName}`,
    `- 프로젝트명: ${projectName}`,
    `- 설치 위치: ${location}`,
    `- 일정: ${schedule}`,
    `- 솔루션: ${solutionText}`,
    `- 디스플레이 크기: ${displaySize}`,
    `- 수량: ${quantity}`,
    `- 예산: ${budget}`,
    "",
    "[요청 내용]",
    usage,
    ...(extra ? ["", "[추가 요청사항]", extra] : []),
    "",
    "가능하신 경우 아래 항목 기준으로 회신 부탁드립니다.",
    "- 진행 가능 여부",
    "- 예상 금액",
    "- 납기 일정",
    "- 설치 가능 일정",
    "- A/S 및 대응 조건",
    "",
    "감사합니다.",
  ].join("\n");
}

function normalizeLegacyRequestMessage(message = "", partnerName = "") {
  const escapedName = String(partnerName).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  let text = String(message)
    .replace(/하이디플레이를/g, "하이디플을")
    .replace(/하이디플레이/g, "하이디플");

  if (escapedName) {
    text = text.replace(
      new RegExp(`안녕하세요 ${escapedName}님`, "g"),
      `안녕하세요 ${partnerName} 담당자님`,
    );
  }

  return text.replace(
    /안녕하세요 (.+?)님(?!(\s*담당자님|\n))/g,
    "안녕하세요 $1 담당자님",
  );
}

function resolveRequestMessage(partner, projectData, override) {
  const defaultMessage = buildRequestMessage(partner, projectData);
  if (!override) return defaultMessage;
  return normalizeLegacyRequestMessage(override, partner?.name ?? "");
}

function SummaryItem({ label, value }) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function PartnerSearchIcon() {
  return (
    <svg
      aria-hidden="true"
      className="partner-search-icon"
      fill="none"
      height="16"
      viewBox="0 0 24 24"
      width="16"
    >
      <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M16 16l4.5 4.5"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function PartnerRemoveIcon() {
  return (
    <svg
      aria-hidden="true"
      className="selected-partner-remove-icon"
      fill="none"
      height="12"
      viewBox="0 0 24 24"
      width="12"
    >
      <path
        d="M6 6l12 12M18 6 6 18"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="2"
      />
    </svg>
  );
}

function getCandidateEmptyMessage(status) {
  if (status === "missing-project-api-id") {
    return {
      title: "프로젝트 저장 후 추천 공급사를 불러올 수 있어요.",
      description: "요구사항을 먼저 저장하면 추천 공급사 목록이 준비돼요.",
    };
  }

  return {
    title: "추천 가능한 공급사가 아직 없어요.",
    description:
      "검색 조건을 조금 완화하거나 요구사항을 보완한 뒤 다시 확인해 주세요.",
  };
}

export default function PartnerMatchingPage({
  projectData,
  onBack,
  onGoDashboard,
  onProjectDataChange,
  onGoHome,
}) {
  const [targetIds, setTargetIds] = useState(projectData.requestTargetIds ?? []);
  const [showRecommendedOnly, setShowRecommendedOnly] = useState(false);
  const [expandedPartnerList, setExpandedPartnerList] = useState(false);
  const [autoSaveStatus, setAutoSaveStatus] = useState("idle");
  const [copyModalOpen, setCopyModalOpen] = useState(false);
  const [activePartnerId, setActivePartnerId] = useState("");
  const [copyFeedback, setCopyFeedback] = useState("");
  const [messageOverrides, setMessageOverrides] = useState({});
  const [isMessageEditing, setIsMessageEditing] = useState(false);
  const [draftMessage, setDraftMessage] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [premiumFilter, setPremiumFilter] = useState("all");
  const [sortKey, setSortKey] = useState("ai");
  const autoSaveStatusTimerRef = useRef(null);
  const copyFeedbackTimerRef = useRef(null);

  const showAutoSaveStatus = (status) => {
    if (autoSaveStatusTimerRef.current) {
      window.clearTimeout(autoSaveStatusTimerRef.current);
      autoSaveStatusTimerRef.current = null;
    }

    setAutoSaveStatus(status);

    if (status === "saved" || status === "error") {
      autoSaveStatusTimerRef.current = window.setTimeout(() => {
        setAutoSaveStatus("idle");
        autoSaveStatusTimerRef.current = null;
      }, status === "saved" ? 1800 : 3000);
    }
  };

  useEffect(() => {
    setTargetIds(projectData.requestTargetIds ?? []);
  }, [projectData.requestTargetIds]);

  useEffect(
    () => () => {
      if (autoSaveStatusTimerRef.current) {
        window.clearTimeout(autoSaveStatusTimerRef.current);
      }
      if (copyFeedbackTimerRef.current) {
        window.clearTimeout(copyFeedbackTimerRef.current);
      }
    },
    [],
  );

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
    onProjectDataChange,
    projectData.cachedExplanation,
    projectData.matchHydrationAttempted,
    projectData.matchId,
    projectData.matchResult,
    projectData.projectApiId,
    projectData.quoteIds,
  ]);

  useEffect(() => {
    const apiProjectId = projectData.projectApiId;
    if (
      !apiProjectId ||
      (projectData.candidateVendors ?? []).length > 0 ||
      projectData.candidateVendorsHydrationAttempted
    ) {
      return;
    }

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
            const partnerList = (vendors.length > 0
              ? vendors
              : current.candidateVendors ?? []
            ).map(normalizeCandidateVendor);
            next.requestTargetIds = requestedVendorIds;
            next.requestTargets = partnerList.filter((partner) =>
              requestedVendorIds.includes(partner.id),
            );
            changed = true;
          }

          return changed ? next : current;
        });
      })
      .catch((error) => {
        console.error("후보 공급사 조회 실패:", error);
      });
  }, [
    onProjectDataChange,
    projectData.candidateVendors,
    projectData.candidateVendorsHydrationAttempted,
    projectData.projectApiId,
  ]);

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

  const recommendedCount = partners.filter((partner) => partner.recommended).length;
  const cautionCount = partners.filter((partner) => partner.caution).length;

  const filteredPartners = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    const base = showRecommendedOnly
      ? partners.filter((partner) => partner.recommended)
      : partners;

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
          const caseDiff = (b.cases ?? 0) - (a.cases ?? 0);
          if (caseDiff !== 0) return caseDiff;
          return b.score - a.score || a.rank - b.rank;
        }
        const scoreDiff = b.score - a.score;
        if (scoreDiff !== 0) return scoreDiff;
        return a.rank - b.rank;
      });
  }, [partners, premiumFilter, searchTerm, showRecommendedOnly, sortKey]);

  const displayPartners = useMemo(() => {
    if (expandedPartnerList) return filteredPartners;
    return filteredPartners.slice(0, DEFAULT_VISIBLE_PARTNERS);
  }, [expandedPartnerList, filteredPartners]);

  const hasHiddenPartners =
    filteredPartners.length > DEFAULT_VISIBLE_PARTNERS && !expandedPartnerList;

  const targetPartners = useMemo(
    () => partners.filter((partner) => targetIds.includes(partner.id)),
    [partners, targetIds],
  );
  const activeMessagePartner =
    targetPartners.find((partner) => partner.id === activePartnerId) ??
    targetPartners[0] ??
    null;
  const defaultRequestMessage = useMemo(
    () => buildRequestMessage(activeMessagePartner, projectData),
    [activeMessagePartner, projectData],
  );
  const requestMessage = activeMessagePartner
    ? resolveRequestMessage(
        activeMessagePartner,
        projectData,
        messageOverrides[activeMessagePartner.id],
      )
    : defaultRequestMessage;
  const displayMessage = isMessageEditing ? draftMessage : requestMessage;

  useEffect(() => {
    setIsMessageEditing(false);
  }, [activePartnerId]);
  const cautionPartners = useMemo(
    () => partners.filter((partner) => partner.caution),
    [partners],
  );
  const candidateEmptyMessage = getCandidateEmptyMessage(candidateStatus);

  const persistRequestTargets = (nextTargetIds, partnersList = partners) => {
    showAutoSaveStatus("saving");
    onProjectDataChange?.((current) => ({
      ...current,
      requestTargetIds: nextTargetIds,
      requestTargets: partnersList.filter((partner) =>
        nextTargetIds.includes(partner.id),
      ),
    }));

    const apiProjectId = projectData.projectApiId;
    if (apiProjectId) {
      updateProject(apiProjectId, { requested_vendor_ids: nextTargetIds })
        .then(() => {
          showAutoSaveStatus("saved");
        })
        .catch((error) => {
          console.error("요청 대상 저장 실패:", error);
          showAutoSaveStatus("error");
        });
      return;
    }

    showAutoSaveStatus("saved");
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
    if (activePartnerId === partnerId) {
      setActivePartnerId("");
    }
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

  const openCopyModal = (partnerId = "") => {
    if (!targetPartners.length) return;
    setActivePartnerId(partnerId || targetPartners[0].id);
    setCopyFeedback("");
    setIsMessageEditing(false);
    setMessageOverrides((current) => {
      const entries = Object.entries(current);
      if (!entries.length) return current;

      const next = {};
      let changed = false;
      for (const [id, text] of entries) {
        const partner = targetPartners.find((item) => item.id === id);
        const normalized = normalizeLegacyRequestMessage(text, partner?.name ?? "");
        next[id] = normalized;
        if (normalized !== text) changed = true;
      }
      return changed ? next : current;
    });
    setCopyModalOpen(true);
  };

  const closeCopyModal = () => {
    setCopyModalOpen(false);
    setCopyFeedback("");
    setIsMessageEditing(false);
  };

  const startMessageEdit = () => {
    setDraftMessage(requestMessage);
    setIsMessageEditing(true);
  };

  const saveMessageEdit = () => {
    if (!activeMessagePartner) return;
    const normalizedMessage = normalizeLegacyRequestMessage(
      draftMessage,
      activeMessagePartner.name,
    );
    setMessageOverrides((current) => ({
      ...current,
      [activeMessagePartner.id]: normalizedMessage,
    }));
    setIsMessageEditing(false);
    setCopyFeedback("문구를 저장했어요.");
    if (copyFeedbackTimerRef.current) {
      window.clearTimeout(copyFeedbackTimerRef.current);
    }
    copyFeedbackTimerRef.current = window.setTimeout(() => {
      setCopyFeedback("");
      copyFeedbackTimerRef.current = null;
    }, 1800);
  };

  const handleCopyMessage = async () => {
    try {
      await navigator.clipboard.writeText(displayMessage);
      setCopyFeedback("문구를 복사했어요.");
      if (copyFeedbackTimerRef.current) {
        window.clearTimeout(copyFeedbackTimerRef.current);
      }
      copyFeedbackTimerRef.current = window.setTimeout(() => {
        setCopyFeedback("");
        copyFeedbackTimerRef.current = null;
      }, 1800);
    } catch (error) {
      console.error("요청 문구 복사 실패:", error);
      setCopyFeedback("복사에 실패했어요.");
    }
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
            <AutoSaveStatus status={autoSaveStatus} />
            <button className="button action-secondary" onClick={onGoHome} type="button">
              목록
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
        <ProjectDetailHeader
          onBack={handleGoBack}
          projectName={projectData.projectName || "새 프로젝트"}
        />

        <ProjectStepTabs
          activeStep={2}
          onGoRequirements={handleGoBack}
          onGoQuoteWaiting={handleGoQuoteWaiting}
        />

        <section className="partner-project-summary six">
          <SummaryItem label="회사명" value={projectData.companyName || "미입력"} />
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
            ? "공급사 추천 결과를 불러오고 있어요. 아직 추천된 공급사가 없을 수 있어요."
            : `공급사 ${partners.length}개를 순위대로 보여드려요. 상위 10개는 AI 추천으로 표시되고, 기본 미충족 공급사는 아래에 구분되어 보여요.`}
        </section>

        <section className="partner-layout">
          <div className="partner-table-panel">
            <div className="partner-section-title compact">
              <div>
                <h2>추천 공급사 목록</h2>
                <p>AI 추천 공급사를 확인한 뒤, 실제로 보낼 공급사만 체크하거나 추가해 주세요.</p>
              </div>
            </div>

            <div className="partner-tools-top compact partner-tools-inline">
              <label className="partner-search-field">
                <PartnerSearchIcon />
                <input
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="공급사명, 전문 분야 검색"
                  type="search"
                  value={searchTerm}
                />
              </label>
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
                <option value="response">응답 속도순</option>
                <option value="cases">사례 많은 순</option>
              </select>
              <button
                className="partner-expand-button partner-expand-button-inline"
                onClick={() => setShowRecommendedOnly((current) => !current)}
                type="button"
              >
                {showRecommendedOnly ? "전체 보기" : "AI 추천만 보기"}
              </button>
              <button
                className="button button-small"
                onClick={addRecommendedPartners}
                type="button"
              >
                AI 추천 대상 모두 추가
              </button>
            </div>

            <div className="partner-toolbar-meta">
              <div className="partner-count-chips compact">
                <Badge tone="blue">AI 추천 {recommendedCount}</Badge>
                <Badge tone="blue">선택 {targetPartners.length}</Badge>
                <Badge tone="orange">주의 {cautionCount}</Badge>
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
                    <th>요청</th>
                  </tr>
                </thead>
                <tbody>
                  {displayPartners.length === 0 ? (
                    <tr>
                      <td className="partner-empty-cell" colSpan={9}>
                        <b>{candidateEmptyMessage.title}</b>
                        <span>{candidateEmptyMessage.description}</span>
                      </td>
                    </tr>
                  ) : null}
                  {displayPartners.map((partner) => {
                    const isTarget = targetIds.includes(partner.id);
                    return (
                      <tr
                        className={[
                          "partner-table-row",
                          partner.recommended ? "ai-recommended-row" : "",
                          partner.caution ? "caution-row" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        key={partner.id}
                        onClick={() => togglePartner(partner.id)}
                      >
                        <td>
                          <input
                            checked={isTarget}
                            onClick={(event) => event.stopPropagation()}
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
                        <td>
                          <button
                            className="partner-row-action"
                            onClick={(event) => {
                              event.stopPropagation();
                              togglePartner(partner.id);
                            }}
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

            {(hasHiddenPartners || expandedPartnerList) && (
              <div className="partner-more-wrap">
                <button
                  className="partner-expand-button partner-expand-button-centered"
                  onClick={() => setExpandedPartnerList((current) => !current)}
                  type="button"
                >
                  <span>
                    {expandedPartnerList
                      ? "15개만 보기"
                      : `${filteredPartners.length - DEFAULT_VISIBLE_PARTNERS}개 더 보기`}
                  </span>
                  <span>{expandedPartnerList ? "접기" : "열기"}</span>
                </button>
              </div>
            )}
          </div>

          <aside className="request-panel panel-sticky">
            <div className="request-card">
              <div className="request-card-head">
                <div>
                  <h2>요청 발송 대상</h2>
                  <p>선택한 공급사를 최종 확인해요.</p>
                </div>
                <div className="request-card-head-actions">
                  <Badge tone="blue">{targetPartners.length}개 대상</Badge>
                  <button
                    className="button button-small"
                    disabled={targetPartners.length === 0}
                    onClick={() => openCopyModal()}
                    type="button"
                  >
                    견적 요청 문구 복사
                  </button>
                </div>
              </div>

              {targetPartners.length === 0 ? (
                <div className="request-empty">
                  아직 요청 발송 대상이 없어요.
                  <span>
                    AI 추천 대상을 한 번에 추가하거나, 목록에서 개별 공급사를 선택해 주세요.
                  </span>
                </div>
              ) : (
                <div className="selected-partner-list">
                  {targetPartners.map((partner) => (
                    <button
                      className={`selected-partner-pill request-target-card${
                        activeMessagePartner?.id === partner.id ? " is-active" : ""
                      }`}
                      key={partner.id}
                      onClick={() => setActivePartnerId(partner.id)}
                      type="button"
                    >
                      <span>
                        <b>{partner.name}</b>
                        <small>
                          AI 추천 점수 {partner.score} · 응답 {partner.response}
                        </small>
                      </span>
                      <button
                        aria-label={`${partner.name} 제거`}
                        className="selected-partner-remove"
                        onClick={(event) => {
                          event.stopPropagation();
                          removePartner(partner.id);
                        }}
                        type="button"
                      >
                        <PartnerRemoveIcon />
                      </button>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="blacklist-card neutral">
              <h3>주의 공급사 요약</h3>
              <p>
                총 {cautionPartners.length}개 공급사는 검토가 필요한 이력이 있어요. 견적 요청 전에
                사유를 확인하고 담당자가 최종 판단해 주세요.
              </p>
              {cautionPartners.length === 0 ? (
                <span>현재 주의 공급사는 없어요.</span>
              ) : (
                cautionPartners.map((partner) => (
                  <span key={partner.id}>
                    {partner.name}: {partner.reason}
                  </span>
                ))
              )}
            </div>
          </aside>
        </section>
      </main>

      <footer className="partner-bottom-actions">
        <span>상태: 요청 대상 검토중 · 발송 대상 {targetPartners.length}개</span>
        <div>
          <button
            className="button action-secondary"
            onClick={handleGoBack}
            type="button"
          >
            이전
          </button>
          <button
            className="button action-primary"
            disabled={targetPartners.length === 0}
            onClick={handleGoQuoteWaiting}
            type="button"
          >
            다음: 견적 수신
          </button>
        </div>
      </footer>

      {copyModalOpen && activeMessagePartner ? (
        <div className="request-copy-modal-layer" role="presentation">
          <button
            aria-label="견적 요청 문구 닫기"
            className="request-copy-backdrop"
            onClick={closeCopyModal}
            type="button"
          />
          <div
            aria-labelledby="request-copy-title"
            aria-modal="true"
            className="request-copy-modal"
            role="dialog"
          >
            <div className="request-copy-header">
              <div>
                <p>카톡 견적 요청</p>
                <h2 id="request-copy-title">복사해서 업체에 보내세요</h2>
              </div>
              <button
                aria-label="복사 모달 닫기"
                className="request-copy-close"
                onClick={closeCopyModal}
                type="button"
              >
                ×
              </button>
            </div>

            <div className="request-copy-summary">
              <div className="request-copy-summary-title">발송 요청 대상을 선택하세요</div>
              <div className="request-copy-summary-tags">
                {targetPartners.map((partner) => (
                  <button
                    className={`request-copy-target-chip${
                      activeMessagePartner.id === partner.id ? " is-active" : ""
                    }`}
                    key={partner.id}
                    onClick={() => setActivePartnerId(partner.id)}
                    type="button"
                  >
                    {partner.name}
                  </button>
                ))}
              </div>
            </div>

            <textarea
              className="request-copy-textarea"
              onChange={(event) => setDraftMessage(event.target.value)}
              readOnly={!isMessageEditing}
              value={displayMessage}
            />

            <p className="request-copy-help">
              {isMessageEditing
                ? "문구를 직접 수정한 뒤 저장해 주세요. 업체를 바꾸면 각 업체별 문구가 따로 유지돼요."
                : "업체명은 선택한 공급사 이름으로 자동 반영됩니다. 복사 후 카카오톡이나 메일에 바로 붙여 넣어 사용해 주세요."}
            </p>

            <div className="request-copy-actions">
              {copyFeedback ? <span>{copyFeedback}</span> : <span />}
              <div>
                {isMessageEditing ? (
                  <button
                    className="button"
                    onClick={() => setIsMessageEditing(false)}
                    type="button"
                  >
                    취소
                  </button>
                ) : null}
                <button
                  className="button"
                  onClick={isMessageEditing ? saveMessageEdit : startMessageEdit}
                  type="button"
                >
                  {isMessageEditing ? "저장" : "수정"}
                </button>
                <button
                  className="button action-primary"
                  disabled={isMessageEditing}
                  onClick={handleCopyMessage}
                  type="button"
                >
                  복사
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
