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
        <div aria-hidden="true" className="login-card-stripe" />

        <div className="login-copy-side">
          <div className="login-logo">
            <div aria-hidden="true" className="login-logo-icon">
              <span />
              <span />
              <span />
              <span />
            </div>
            <div className="login-logo-text-wrap">
              <span className="login-logo-text">QuoPilot</span>
              <span className="login-logo-tagline">
                구매 검토팀을 위한 AI 견적 비교 워크스페이스
              </span>
            </div>
          </div>

          <p className="login-version">v1.3.2</p>

          <div className="login-copy-main">
            <h1 className="login-heading">
              프로젝트별 견적 비교,
              <br />
              이제 한 화면에서 시작하세요
            </h1>
            <p className="login-subtext">
              이전 프로젝트를 확인하고, 새 견적서를 업로드한 뒤 AI 분석
              결과를 대시보드로 검토해요.
            </p>
          </div>

          <div aria-hidden="true" className="login-copy-spacer" />
        </div>

        <div className="login-auth-side">
          <div className="login-auth-content">
            <div className="login-auth-header">
              <h2 className="login-auth-title">로그인</h2>
              <p className="login-auth-sub">
                회사 Microsoft 계정으로 계속하세요
              </p>
            </div>

            <div className="login-auth-action">
              <button
                className="login-ms-button"
                onClick={handleLogin}
                type="button"
              >
                <img
                  alt=""
                  className="login-ms-button-logo"
                  height={20}
                  src="/ms-logo.png"
                  width={20}
                />
                Sign in with Microsoft
              </button>

              <hr aria-hidden="true" className="login-auth-divider" />
            </div>

            <div className="login-auth-main">
              <div className="login-auth-note">
                <div className="login-auth-note-copy">
                  <strong>Microsoft Entra ID를 통해 인증됩니다.</strong>
                  <p>
                    조직에서 발급한 회사 이메일로 로그인하세요. 안전한 SSO
                    환경을 지원합니다.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
