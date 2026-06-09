import { useMemo, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectStepTabs from "../components/ProjectStepTabs";

const candidatePartners = [
  {
    id: "partner-a",
    name: "A Display",
    score: 92,
    specialty: "상업용 사이니지 전문",
    cases: 8,
    premium: true,
    priceScore: 88,
    response: "2.1h",
    trust: 95,
    recommended: true,
    caution: false,
    reason: "유사 구축 사례와 납기 안정성이 높음",
  },
  {
    id: "partner-b",
    name: "BrightSign Korea",
    score: 89,
    specialty: "프리미엄 디스플레이",
    cases: 6,
    premium: true,
    priceScore: 82,
    response: "1.8h",
    trust: 93,
    recommended: true,
    caution: false,
    reason: "기술 적합도와 응답 속도가 우수함",
  },
  {
    id: "partner-c",
    name: "VisionTech",
    score: 86,
    specialty: "로비 구축 경험 다수",
    cases: 7,
    premium: false,
    priceScore: 91,
    response: "2.5h",
    trust: 88,
    recommended: true,
    caution: false,
    reason: "가격 경쟁력과 구축 사례가 양호함",
  },
  {
    id: "partner-d",
    name: "인포디스플레이",
    score: 84,
    specialty: "대형 설치 프로젝트",
    cases: 9,
    premium: true,
    priceScore: 78,
    response: "3.0h",
    trust: 86,
    recommended: true,
    caution: false,
    reason: "상업용 설치 경험이 충분함",
  },
  {
    id: "partner-e",
    name: "솔루션즈",
    score: 81,
    specialty: "통합 구축 및 유지보수",
    cases: 5,
    premium: false,
    priceScore: 85,
    response: "2.3h",
    trust: 84,
    recommended: true,
    caution: false,
    reason: "유지보수 조건이 프로젝트 요구와 맞음",
  },
  {
    id: "partner-f",
    name: "스마트뷰",
    score: 78,
    specialty: "중소형 사이니지",
    cases: 3,
    premium: false,
    priceScore: 93,
    response: "4.1h",
    trust: 79,
    recommended: false,
    caution: false,
    reason: "가격은 낮지만 대형 레퍼런스가 부족함",
  },
  {
    id: "partner-g",
    name: "오픈사이니지",
    score: 76,
    specialty: "콘텐츠 관리 솔루션",
    cases: 4,
    premium: true,
    priceScore: 80,
    response: "3.4h",
    trust: 80,
    recommended: false,
    caution: false,
    reason: "CMS 강점은 있으나 설치 사례 확인 필요",
  },
  {
    id: "partner-h",
    name: "넥스트디스플레이",
    score: 74,
    specialty: "저가형 디스플레이 공급",
    cases: 2,
    premium: false,
    priceScore: 96,
    response: "5.0h",
    trust: 74,
    recommended: false,
    caution: true,
    reason: "블랙리스트 이력이 있어 발송 전 재확인 필요",
  },
];

export default function PartnerMatchingPage({
  projectData,
  onBack,
  onGoDashboard,
}) {
  const [targetIds, setTargetIds] = useState([]);
  const [showAllPartners, setShowAllPartners] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [premiumFilter, setPremiumFilter] = useState("all");
  const [sortKey, setSortKey] = useState("ai");

  const recommendedCount = candidatePartners.filter((partner) => partner.recommended).length;
  const cautionCount = candidatePartners.filter((partner) => partner.caution).length;

  const visiblePartners = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    const base = showAllPartners
      ? candidatePartners
      : candidatePartners.filter((partner) => partner.recommended);

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
        if (sortKey === "price") return b.priceScore - a.priceScore;
        if (sortKey === "trust") return b.trust - a.trust;
        if (sortKey === "response") return parseFloat(a.response) - parseFloat(b.response);
        return b.score - a.score;
      });
  }, [premiumFilter, searchTerm, showAllPartners, sortKey]);

  const targetPartners = useMemo(
    () => candidatePartners.filter((partner) => targetIds.includes(partner.id)),
    [targetIds],
  );
  const cautionPartners = candidatePartners.filter((partner) => partner.caution);

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
        ...candidatePartners
          .filter((partner) => partner.recommended)
          .map((partner) => partner.id),
      ]),
    ]);
  };

  return (
    <div className="flow-page partner-page">
      <FlowTopbar
        trail="프로젝트 상세 > 파트너 매칭/견적 요청"
        action={
          <>
            <button className="button action-secondary" type="button">
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
          프로젝트 조건 기준으로 요청 우선 대상 {recommendedCount}개를 자동 제안했습니다.
          체크 표시는 사용자가 요청 발송 대상으로 추가한 업체에만 표시됩니다.
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
                <option value="ai">AI 적합도순</option>
                <option value="price">가격 점수순</option>
                <option value="trust">신뢰도순</option>
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
                  <Badge tone="blue">추천 {recommendedCount}</Badge>
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
                    <th>업체명</th>
                    <th>전문성</th>
                    <th>프리미엄</th>
                    <th>가격</th>
                    <th>사례5+</th>
                    <th>응답</th>
                    <th>신뢰도</th>
                    <th>구분</th>
                    <th>사유</th>
                    <th>요청</th>
                  </tr>
                </thead>
                <tbody>
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
                        <td>{partner.priceScore}</td>
                        <td>{partner.cases >= 5 ? "예" : "아니오"}</td>
                        <td>{partner.response}</td>
                        <td>{partner.trust}</td>
                        <td>
                          <Badge tone={partner.caution ? "orange" : partner.recommended ? "blue" : "gray"}>
                            {partner.caution ? "주의" : partner.recommended ? "AI 추천" : "후보"}
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
                        <small>전문성 {partner.score} · 신뢰도 {partner.trust} · 응답 {partner.response}</small>
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
          <button className="button action-secondary" type="button">
            임시 저장
          </button>
          <button className="button button-blue" disabled={targetPartners.length === 0} type="button">
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
