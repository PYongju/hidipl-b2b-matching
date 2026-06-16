import FlowTopbar from "../components/FlowTopbar";

const historyItems = [
  {
    type: "생성",
    title: "프로젝트 생성",
    time: "2025-04-28 10:20",
    actor: "김담당자",
    detail: "기본 정보와 요구사항 초안 작성",
  },
  {
    type: "요청",
    title: "요청 대상 저장",
    time: "2025-04-28 11:05",
    actor: "김담당자",
    detail: "AI 추천 결과 검토 후 공급사 5개 확정",
  },
  {
    type: "요청",
    title: "견적 요청 발송",
    time: "2025-04-28 11:12",
    actor: "김담당자",
    detail: "A Display 외 4개 공급사에 요청 발송",
  },
  {
    type: "수신",
    title: "견적 수신",
    time: "2025-05-20 09:40",
    actor: "A Display",
    detail: "견적서 2개 파일 업로드",
  },
  {
    type: "수정",
    title: "값 수정",
    time: "2025-05-22 10:05",
    actor: "김담당자",
    detail: "VisionTech 납기 조건 검토 메모 수정",
  },
  {
    type: "선정",
    title: "최종 선정",
    time: "2025-05-23 10:15",
    actor: "김담당자",
    detail: "A Display 최종 선정 완료",
  },
];

export default function ReportHistoryPage({ projectData, onBack, onGoProjects }) {
  const projectName = projectData.projectName || "삼성전자 본사 로비 사이니지 구축";

  return (
    <div className="flow-page report-history-page">
      <FlowTopbar
        trail="프로젝트 상세 > 보고서/이력"
        action={
          <>
            <button className="button action-secondary" onClick={onBack} type="button">
              이전
            </button>
            <button className="button button-blue" onClick={onGoProjects} type="button">
              프로젝트 목록
            </button>
            <div className="avatar" />
            <div className="user-name">
              <b>김담당자</b>
              <small>구매검토팀</small>
            </div>
          </>
        }
      />

      <main className="report-history-main">
        <section className="report-result-bar">
          <article>
            <span>최종 선정 결과</span>
            <strong>A Display</strong>
          </article>
          <article>
            <span>내부 확정 시각</span>
            <strong>2025-05-23 10:15</strong>
          </article>
          <article>
            <span>담당자</span>
            <strong>김담당자 · 구매검토팀</strong>
          </article>
        </section>

        <section className="report-history-layout">
          <div className="report-preview-panel">
            <div className="report-panel-title">
              <div>
                <h2>고객 보고서 미리보기</h2>
                <p>고객에게 공유할 비교 결과와 최종 추천 사유를 확인해요.</p>
              </div>
              <button className="button button-small" type="button">보고서 문구 수정</button>
            </div>

            <article className="customer-report-paper">
              <header>
                <div>
                  <b>견적 비교 결과 보고서</b>
                  <span>PV-2025-0421 · 2025-05-23</span>
                </div>
                <h1>{projectName}</h1>
                <p>
                  상업용 디스플레이 구축 프로젝트의 수신 견적서를 비교하고,
                  가격·납기·유지보수·유사 사례를 기준으로 최종 추천 공급사를 선정했어요.
                </p>
              </header>

              <section className="report-summary-grid">
                <div>
                  <h3>비교 요약</h3>
                  <p>
                    견적 요청 공급사 5개 중 3개 공급사가 견적서를 제출했어요.
                    3개 공급사 모두 필수 디스플레이 사양을 충족했고, 가격과 납기 조건에서 차이가 있었어요.
                  </p>
                </div>
                <div>
                  <h3>최종 추천 요약</h3>
                  <p>
                    A Display는 최저가는 아니지만 6주 납기, 2년 무상 유지보수,
                    유사 구축 사례 12건을 바탕으로 가장 안정적인 수행 가능성을 보였어요.
                  </p>
                </div>
                <div>
                  <h3>선택 사유</h3>
                  <p>
                    로비 리모델링 일정과 연계된 프로젝트 특성상 단순 최저가보다
                    납기 안정성과 유지보수 대응력을 우선 고려했어요.
                  </p>
                </div>
                <div>
                  <h3>주의사항</h3>
                  <p>
                    현장 실사 이후 설치 방식과 세부 모델이 변경될 수 있어요.
                    최종 계약 전에 설치 일정과 CMS 포함 범위를 다시 확인해 주세요.
                  </p>
                </div>
              </section>

              <section className="final-vendor-callout">
                <b>최종 선정 공급사: A Display</b>
                <span>총 견적 금액 96,800,000원 · 납기 6주 · 무상 유지보수 2년 · 유사 구축 사례 12건</span>
              </section>

              <table className="report-compare-table">
                <thead>
                  <tr>
                    <th>비교 항목</th>
                    <th>A Display</th>
                    <th>BrightSign Korea</th>
                    <th>VisionTech</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>총 견적 금액</td>
                    <td className="report-selected">96,800,000원</td>
                    <td>108,500,000원</td>
                    <td>91,200,000원</td>
                  </tr>
                  <tr>
                    <td>납기</td>
                    <td className="report-selected">6주</td>
                    <td>7주</td>
                    <td>8주</td>
                  </tr>
                  <tr>
                    <td>유지보수</td>
                    <td className="report-selected">2년</td>
                    <td>1년</td>
                    <td>1년</td>
                  </tr>
                  <tr>
                    <td>유사 구축 사례</td>
                    <td className="report-selected">12건</td>
                    <td>9건</td>
                    <td>7건</td>
                  </tr>
                </tbody>
              </table>
            </article>
          </div>

          <aside className="history-timeline-panel">
            <div className="report-panel-title">
              <div>
                <h2>히스토리 타임라인</h2>
                <p>프로젝트 주요 이벤트와 수정 이력을 확인해요.</p>
              </div>
            </div>

            <div className="history-filter-row">
              <button className="active" type="button">전체</button>
              <button type="button">요청</button>
              <button type="button">수신</button>
              <button type="button">수정</button>
            </div>

            <div className="history-event-list">
              {historyItems.map((item) => (
                <article className={`history-event history-${item.type}`} key={`${item.title}-${item.time}`}>
                  <span>{getHistorySymbol(item.type)}</span>
                  <div>
                    <b>{item.title}</b>
                    <small>{item.time} · {item.actor}</small>
                    <p>{item.detail}</p>
                  </div>
                </article>
              ))}
            </div>
          </aside>
        </section>
      </main>

      <footer className="report-bottom-actions">
        <span>최종 선정 완료 · 고객 공유용 보고서 준비됨</span>
        <div>
          <button className="button button-blue" type="button">PDF 다운로드</button>
          <button className="button button-blue" type="button">Excel 다운로드</button>
          <button className="button action-primary" type="button">고객 공유용 복사</button>
          <button className="button action-secondary" onClick={onGoProjects} type="button">프로젝트 목록으로 돌아가기</button>
        </div>
      </footer>
    </div>
  );
}

function getHistorySymbol(type) {
  if (type === "선정") return "✓";
  if (type === "수정") return "✎";
  if (type === "수신") return "↑";
  if (type === "요청") return "↗";
  return "+";
}
