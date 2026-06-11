import { useMemo, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectStepTabs from "../components/ProjectStepTabs";

function normalizeSimilarityScore(value) {
  if (typeof value !== "number") return 0;
  return value <= 1 ? Math.round(value * 100) : Math.round(value);
}

function normalizeResponseSpeed(value) {
  if (typeof value === "number") return `${value}h`;
  return value ?? "미확인";
}

function normalizeCandidateVendor(raw, index) {
  const filterReasons = raw.filter_reasons ?? [];
  const checkRequired = raw.check_required ?? [];
  const vendorName = raw.vendor_name ?? raw.partner_name ?? raw.name ?? `업체 ${index + 1}`;
  const caseCount =
    raw.installation_count ??
    raw.case_count ??
    raw.cases ??
    raw.metadata?.installation_count ??
    raw.metadata?.case_count ??
    0;
  const rank = raw.rank ?? index + 1;
  const businessRulePassed = raw.business_rule_passed === true && raw.is_excluded !== true;

  return {
    id: raw.vendor_id ?? raw.vendor_name ?? raw.partner_id ?? raw.partner_name ?? `partner-${index}`,
    name: vendorName,
    rank,
    score: normalizeSimilarityScore(
      raw.semantic_similarity_score ?? raw.cosine_similarity,
    ),
    specialty: Array.isArray(raw.specialty_tags)
      ? raw.specialty_tags.join(", ")
      : "전문 분야 미확인",
    cases: caseCount,
    premium: Boolean(raw.is_premium),
    response: normalizeResponseSpeed(raw.response_speed),
    businessRulePassed,
    recommended: businessRulePassed && rank <= 10,
    caution: filterReasons.length > 0 || checkRequired.length > 0,
    reason:
      checkRequired.join(", ") ||
      filterReasons.join(", ") ||
      (businessRulePassed ? "요구사항 기준 추천 가능 업체" : "추천 기준 미충족"),
  };
}

export default function PartnerMatchingPage({
  projectData,
  onBack,
  onGoDashboard,
  onProjectDataChange,
}) {
  const [targetIds, setTargetIds] = useState(projectData.requestTargetIds ?? []);
  const [showAllPartners, setShowAllPartners] = useState(true);
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

  const recommendedCount = partners.filter((partner) => partner.recommended).length;
  const businessPassedCount = partners.filter((partner) => partner.businessRulePassed).length;
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
        if (a.businessRulePassed !== b.businessRulePassed) {
          return a.businessRulePassed ? -1 : 1;
        }
        if (sortKey === "response") {
          return parseFloat(a.response) - parseFloat(b.response);
        }
        return a.rank - b.rank || b.score - a.score;
      });
  }, [partners, premiumFilter, searchTerm, showAllPartners, sortKey]);

  const targetPartners = useMemo(
    () => partners.filter((partner) => targetIds.includes(partner.id)),
    [partners, targetIds],
  );
  const cautionPartners = partners.filter((partner) => partner.caution);
  const candidateEmptyMessage = getCandidateEmptyMessage(candidateStatus);

  const addPartner = (partnerId) => {
    setTargetIds((current) =>
      current.includes(partnerId) ? current : [...current, partnerId],
    );
  };

  const removePartner = (partnerId) => {
    setTargetIds((current) => current.filter((id) => id !== partnerId));
  };

  const togglePartner = (partnerId) => {
    if (targetIds.includes(partnerId)) {
      removePartner(partnerId);
      return;
    }
    addPartner(partnerId);
  };

  const addRecommendedPartners = () => {
    setTargetIds((current) => [
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
      requestTargets: partners.filter((partner) => targetIds.includes(partner.id)),
      currentStage: "요청 대상 검토중",
      workflowStatus: "진행 중",
    }));
  };

  return (
    <div className="flow-page partner-page">
      <FlowTopbar
        trail="프로젝트 상세 > 파트너 매칭/견적 요청"
        action={
          <>
            <button className="button action-secondary" onClick={savePartnerDraft} type="button">
              임시 저장
            </button>
            <div className="avatar" />
            <div className="user-name">
              <b>김담당자</b>
              <small>구매팀</small>
            </div>
          </>
        }
      />

      <main className="partner-main">
        <section className="partner-head">
          <div>
            <button className="partner-back" onClick={onBack} type="button">
              ‹
            </button>
            <span>프로젝트 상세</span>
          </div>
        </section>

        <ProjectStepTabs
          activeStep={2}
          onGoRequirements={onBack}
          onGoQuoteWaiting={onGoDashboard}
        />

        <section className="partner-project-summary six">
          <SummaryItem label="회사명" value={projectData.companyName || "미입력"} />
          <SummaryItem label="위치" value={projectData.location || "미입력"} />
          <SummaryItem label="일정" value={projectData.projectDate || "일정 미정"} />
          <SummaryItem label="발주처 유형" value={projectData.clientType || "미입력"} />
          <SummaryItem label="카테고리" value={projectData.category || "디스플레이"} />
          <SummaryItem label="상태" value="요청 대상 검토중" />
        </section>

        <section className="partner-notice strong">
          {partners.length === 0
            ? "파트너 추천 결과를 불러오는 중이거나 아직 추천된 업체가 없습니다."
            : `파트너 ${partners.length}개를 순위대로 표시합니다. 상위 ${recommendedCount}개는 AI 추천으로 표시하고, 기준 미충족 업체는 아래에 분리됩니다.`}
        </section>

        <section className="partner-layout">
          <div className="partner-table-panel">
            <div className="partner-tools-top">
              <input
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="업체명, 전문 분야 검색"
                value={searchTerm}
              />
              <select
                onChange={(event) => setPremiumFilter(event.target.value)}
                value={premiumFilter}
              >
                <option value="all">전체 파트너</option>
                <option value="premium">프리미엄만</option>
                <option value="standard">일반만</option>
              </select>
              <select onChange={(event) => setSortKey(event.target.value)} value={sortKey}>
                <option value="ai">AI 추천 점수순</option>
                <option value="response">응답 빠른순</option>
              </select>
            </div>

            <div className="partner-section-title">
              <div>
                <h2>추천 파트너 테이블</h2>
                <p>AI 추천 업체를 확인한 뒤, 실제 발송할 업체만 체크하거나 추가합니다.</p>
              </div>
              <div className="partner-title-actions">
                <div className="partner-count-chips">
                  <Badge tone="blue">AI 추천 {recommendedCount}</Badge>
                  <Badge tone="gray">추천 가능 {businessPassedCount}</Badge>
                  <Badge tone="blue">선택 {targetIds.length}</Badge>
                  <Badge tone="orange">주의 {cautionCount}</Badge>
                  <Badge tone="gray">표시 {visiblePartners.length}</Badge>
                </div>
                <button className="button button-small" onClick={addRecommendedPartners} type="button">
                  AI 추천 대상 모두 추가
                </button>
              </div>
            </div>

            <div className="partner-table-wrap">
              <table className="partner-table">
                <thead>
                  <tr>
                    <th>선택</th>
                    <th>순위</th>
                    <th>업체명</th>
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
                          <Badge tone={partner.caution ? "orange" : partner.recommended ? "blue" : "gray"}>
                            {partner.caution ? "주의" : partner.recommended ? "AI 추천" : partner.businessRulePassed ? "추천 가능" : "기준 미충족"}
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

            <button
              className="partner-expand-button"
              onClick={() => setShowAllPartners((current) => !current)}
              type="button"
            >
              {showAllPartners ? "AI 추천 파트너만 보기" : "전체 파트너 보기"}
            </button>
          </div>

          <aside className="request-panel">
            <div className="request-card">
              <div className="request-card-head">
                <div>
                  <h2>요청 발송 대상</h2>
                  <p>선택된 업체를 최종 확인합니다.</p>
                </div>
                <div className="request-count-chips">
                  <Badge tone="blue">{targetPartners.length}개 대상</Badge>
                </div>
              </div>

              {targetPartners.length === 0 ? (
                <div className="request-empty">
                  아직 요청 발송 대상이 없습니다.
                  <span>AI 추천 대상을 한 번에 추가하거나, 테이블에서 개별 업체를 선택하세요.</span>
                </div>
              ) : (
                <div className="selected-partner-list">
                  {targetPartners.map((partner) => (
                    <div className="selected-partner-pill" key={partner.id}>
                      <span>
                        <b>{partner.name}</b>
                        <small>AI 추천 점수 {partner.score} · 응답 {partner.response}</small>
                      </span>
                      {partner.caution && <Badge tone="orange">주의</Badge>}
                      <button onClick={() => removePartner(partner.id)} type="button" aria-label={`${partner.name} 제거`}>
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="blacklist-card neutral">
              <h3>주의 업체 요약</h3>
              <p>
                총 {cautionPartners.length}개 업체는 블랙리스트 또는 리스크 이력이 있습니다.
                견적 요청 전 사유를 확인하고 담당자가 최종 판단하세요.
              </p>
              {cautionPartners.map((partner) => (
                <span key={partner.id}>{partner.name}: {partner.reason}</span>
              ))}
            </div>

            <label className="request-memo">
              <span>발송 전 메모</span>
              <textarea placeholder="파트너에게 전달할 견적 요청 메모를 입력하세요." />
            </label>
          </aside>
        </section>
      </main>

      <footer className="partner-bottom-actions">
        <span>상태: 요청 대상 검토중 · 발송 대상 {targetPartners.length}개</span>
        <div>
          <button className="button action-secondary" onClick={savePartnerDraft} type="button">
            임시 저장
          </button>
          <button
            className="button button-blue"
            disabled
            title="요청 대상 저장 API 연결 후 사용할 수 있습니다."
            type="button"
          >
            요청 대상 저장
          </button>
          <button
            className="button action-primary"
            disabled={targetPartners.length === 0}
            onClick={onGoDashboard}
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
      title: "추천 후보를 불러오는 중입니다.",
      description: "프로젝트 조건을 기준으로 파트너 후보를 조회하고 있습니다.",
    };
  }
  if (status === "empty") {
    return {
      title: "추천 후보가 없습니다.",
      description: "현재 조건으로 조회된 파트너가 없습니다. 요구사항을 보완하거나 전체 파트너 조건을 다시 확인해 주세요.",
    };
  }
  if (status === "missing-project-api-id") {
    return {
      title: "프로젝트 생성 정보가 없습니다.",
      description: "서버에 생성된 프로젝트 ID가 없어 추천 후보를 조회하지 못했습니다.",
    };
  }
  if (status === "error") {
    return {
      title: "추천 후보를 불러오지 못했습니다.",
      description: "candidate-vendors API 연결 상태를 확인해야 합니다. 실제 데이터를 mock으로 대체하지 않습니다.",
    };
  }
  return {
    title: "표시할 파트너가 없습니다.",
    description: "검색어 또는 필터 조건을 조정해 주세요.",
  };
}
