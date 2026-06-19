import { useMsal } from "@azure/msal-react";
import { loginRequest } from "../auth/msalConfig";

export default function LoginPage({ onLogin }) {
  const { instance } = useMsal();

  async function handleLogin() {
    try {
      await instance.loginRedirect(loginRequest);
    } catch (e) {
      console.error("로그인 실패:", e);
    }
  }

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
            <b>QuoPilot</b>
            <span>구매 검토팀을 위한 AI 견적 비교 워크스페이스</span>
          </div>
        </div>
        <div className="login-copy">
          <p>v1.3.2</p>
          <h1>프로젝트별 견적 검토를 한 곳에서 시작하세요</h1>
          <span>
            이전 프로젝트를 확인하고, 새 견적서를 업로드한 뒤 AI 분석 결과를
            대시보드로 검토해요.
          </span>
        </div>
        <div className="login-form">
          <button
            className="button action-primary"
            onClick={handleLogin}
            type="button"
          >
            Microsoft 계정으로 로그인
          </button>
        </div>
      </div>
    </div>
  );
}
