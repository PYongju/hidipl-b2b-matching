export default function LoginPage({ onLogin }) {
  return (
    <div className="flow-page login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
          </div>
          <div>
            <b>견적 비교 메이트 - QuoPilot</b>
            <span>구매 검토팀을 위한 AI 견적 비교 워크스페이스</span>
          </div>
        </div>
        <div className="login-copy">
          <p>v1.3.2</p>
          <h1>프로젝트별 견적 검토를 한 곳에서 시작하세요</h1>
          <span>이전 프로젝트를 확인하고, 새 견적서를 업로드한 뒤 AI 분석 결과를 대시보드로 검토합니다.</span>
        </div>
        <div className="login-form">
          <label>
            <span>이메일</span>
            <input defaultValue="buyer@company.co.kr" />
          </label>
          <label>
            <span>비밀번호</span>
            <input defaultValue="password" type="password" />
          </label>
          <button className="button action-primary" onClick={onLogin} type="button">
            로그인
          </button>
        </div>
      </div>
    </div>
  );
}
