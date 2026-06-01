import FlowTopbar from '../components/FlowTopbar';

export default function AnalysisPage({ onDashboard }) {
  return (
    <div className="flow-page analysis-page">
      <FlowTopbar trail="새 프로젝트 생성 > AI 분석" />
      <main className="analysis-card">
        <div className="analysis-symbol">✦</div>
        <h1>AI가 견적서를 분석 중입니다</h1>
        <p>3개 공급사의 견적서를 요구사항과 비교하고 있습니다.</p>
        <div className="analysis-progress">
          <span />
        </div>
        <div className="analysis-steps">
          <div className="done"><b>파일 업로드 확인</b><small>완료 · 3개 파일</small></div>
          <div className="done"><b>금액 · 납기 · 보증 항목 추출</b><small>완료 · 24개 항목 인식</small></div>
          <div className="active"><b>비요청 옵션 분리</b><small>진행 중</small></div>
          <div><b>공급사별 장단점 생성</b><small>대기 중</small></div>
          <div><b>비교 대시보드 구성</b><small>대기 중</small></div>
        </div>
        <button className="button action-primary" onClick={onDashboard} type="button">
          분석 완료 화면 보기
        </button>
      </main>
    </div>
  );
}
