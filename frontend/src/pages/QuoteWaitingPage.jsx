import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";

const partnerQuoteStatuses = [
  {
    id: "a",
    name: "A Display",
    specialty: "상업용 사이니지 전문",
    sentAt: "04.28 11:12",
    viewed: true,
    replied: true,
    uploaded: true,
    fileCount: 2,
    deadline: "05.03",
    status: "견적 수신 완료",
    tone: "green",
  },
  {
    id: "b",
    name: "BrightSign Korea",
    specialty: "프리미엄 디스플레이",
    sentAt: "04.28 11:12",
    viewed: true,
    replied: true,
    uploaded: true,
    fileCount: 1,
    deadline: "05.03",
    status: "견적 수신 완료",
    tone: "green",
  },
  {
    id: "c",
    name: "VisionTech",
    specialty: "로비 구축 경험 다수",
    sentAt: "04.28 11:12",
    viewed: true,
    replied: true,
    uploaded: false,
    fileCount: 0,
    deadline: "05.03",
    status: "문의 응답",
    tone: "blue",
  },
  {
    id: "d",
    name: "인포디스플레이",
    specialty: "대형 설치 프로젝트",
    sentAt: "04.28 11:12",
    viewed: true,
    replied: false,
    uploaded: false,
    fileCount: 0,
    deadline: "05.03",
    status: "열람 완료",
    tone: "orange",
  },
  {
    id: "e",
    name: "솔루션즈",
    specialty: "통합 구축 및 유지보수",
    sentAt: "04.28 11:12",
    viewed: false,
    replied: false,
    uploaded: false,
    fileCount: 0,
    deadline: "05.03",
    status: "미열람",
    tone: "gray",
  },
];

const timelineSteps = [
  { label: "요청 대상 확정", detail: "5개 업체 선택", done: true },
  { label: "요청 발송", detail: "04.28 11:12", done: true },
  { label: "열람", detail: "4개 업체 열람", done: true },
  { label: "문의 응답", detail: "3개 업체 응답", done: false, active: true },
  { label: "견적 업로드", detail: "2개 업체 완료", done: false },
];

export default function QuoteWaitingPage({ projectData, onBack, onGoDashboard }) {
  const receivedCount = partnerQuoteStatuses.filter((partner) => partner.uploaded).length;
  const viewedCount = partnerQuoteStatuses.filter((partner) => partner.viewed).length;
  const repliedCount = partnerQuoteStatuses.filter((partner) => partner.replied).length;
  const canCompare = receivedCount >= 2;

  return (
    <div className="flow-page quote-waiting-page">
      <FlowTopbar
        trail="프로젝트 상세 > 견적 수신 대기"
        action={
          <>
            <button className="button action-secondary" onClick={onBack} type="button">
              이전
            </button>
            <div className="avatar" />
            <div className="user-name">
              <b>김담당자</b>
              <small>구매팀</small>
            </div>
          </>
        }
      />

      <main className="quote-waiting-main">
        <section className="partner-head">
          <div>
            <button className="partner-back" onClick={onBack} type="button">
              ‹
            </button>
            <span>견적 수신 대기</span>
          </div>
        </section>

        <nav className="partner-stepper" aria-label="프로젝트 단계">
          <button onClick={onBack} type="button">1 요구사항</button>
          <button onClick={onBack} type="button">2 파트너 매칭/견적 요청</button>
          <button className="active" type="button">3 견적 수신 대기</button>
          <button onClick={onGoDashboard} type="button">4 견적 검토</button>
          <button type="button">5 보고서/이력</button>
        </nav>

        <section className="quote-status-bar">
          <article>
            <span>요청 상태</span>
            <strong>견적 요청 발송됨</strong>
          </article>
          <article>
            <span>견적 수신 현황</span>
            <strong>{receivedCount} / {partnerQuoteStatuses.length}개 수신</strong>
          </article>
          <article>
            <span>미응답 파트너</span>
            <strong>{partnerQuoteStatuses.length - repliedCount}개</strong>
          </article>
          <article>
            <span>마지막 업데이트</span>
            <strong>2025-04-30 14:20 · 자동 갱신됨</strong>
          </article>
        </section>

        <section className="quote-timeline-panel">
          <div className="quote-panel-title">
            <h2>요청 타임라인</h2>
            <p>발송 이후 파트너별 진행 상태를 추적합니다.</p>
          </div>
          <div className="quote-timeline">
            {timelineSteps.map((step, index) => (
              <article className={step.active ? "active" : step.done ? "done" : ""} key={step.label}>
                <span>{step.done ? "✓" : index + 1}</span>
                <b>{step.label}</b>
                <small>{step.detail}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="quote-waiting-layout">
          <div className="quote-board-panel">
            <div className="quote-panel-title with-progress">
              <div>
                <h2>파트너별 수신 현황 보드</h2>
                <p>발송, 열람, 문의 응답, 견적 업로드 상태를 업체별로 확인합니다.</p>
              </div>
              <div className="quote-progress">
                <span>수신률 {Math.round((receivedCount / partnerQuoteStatuses.length) * 100)}%</span>
                <div><i style={{ width: `${(receivedCount / partnerQuoteStatuses.length) * 100}%` }} /></div>
              </div>
            </div>

            <div className="quote-board-table-wrap">
              <table className="quote-board-table">
                <thead>
                  <tr>
                    <th>업체명</th>
                    <th>발송 시각</th>
                    <th>열람 여부</th>
                    <th>응답 여부</th>
                    <th>견적 업로드</th>
                    <th>파일 수</th>
                    <th>마감일</th>
                    <th>상태</th>
                    <th>액션</th>
                  </tr>
                </thead>
                <tbody>
                  {partnerQuoteStatuses.map((partner) => (
                    <tr key={partner.id}>
                      <td>
                        <b>{partner.name}</b>
                        <small>{partner.specialty}</small>
                      </td>
                      <td>{partner.sentAt}</td>
                      <td className={partner.viewed ? "quote-ok" : "quote-muted"}>
                        {partner.viewed ? "열람" : "미열람"}
                      </td>
                      <td className={partner.replied ? "quote-ok" : "quote-muted"}>
                        {partner.replied ? "응답" : "미응답"}
                      </td>
                      <td className={partner.uploaded ? "quote-uploaded" : "quote-muted"}>
                        {partner.uploaded ? "업로드 완료" : "미업로드"}
                      </td>
                      <td>{partner.fileCount}개</td>
                      <td>{partner.deadline}</td>
                      <td><Badge tone={partner.tone}>{partner.status}</Badge></td>
                      <td>
                        <button className="partner-row-action" type="button">
                          {partner.uploaded ? "파일 보기" : "리마인드"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <aside className="quote-ops-panel">
            <div className="quote-panel-title">
              <h2>운영 액션</h2>
              <p>수신 대기 단계에서 필요한 후속 조치를 수행합니다.</p>
            </div>

            <section>
              <h3>리마인드 발송</h3>
              <button className="quote-action-button" type="button">
                미열람 업체에 발송 <Badge tone="blue">{partnerQuoteStatuses.length - viewedCount}</Badge>
              </button>
              <button className="quote-action-button" type="button">
                전체 미수신 업체에 발송 <Badge tone="blue">{partnerQuoteStatuses.length - receivedCount}</Badge>
              </button>
            </section>

            <section>
              <h3>요청 대상 관리</h3>
              <button className="quote-action-button" type="button">요청 대상 추가</button>
              <button className="quote-action-button" type="button">수동 업로드 등록</button>
            </section>

            <label className="request-memo">
              <span>내부 메모</span>
              <textarea defaultValue="VisionTech와 인포디스플레이는 아직 견적 미수신. 5월 2일 오전까지 미응답이면 리마인드 발송 예정." />
            </label>
          </aside>
        </section>
      </main>

      <footer className="quote-waiting-bottom-actions">
        <span>마지막 저장: 2025-04-30 14:20 · 견적 {receivedCount}개 수신</span>
        <div>
          <button className="button action-secondary" type="button">임시 저장</button>
          <button className="button button-blue" type="button">리마인드 발송</button>
          <button
            className="button action-primary"
            disabled={!canCompare}
            onClick={onGoDashboard}
            type="button"
          >
            비교 검토로 이동
          </button>
        </div>
      </footer>
    </div>
  );
}
