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
            <div className="login-logo-row">
              <img
                alt=""
                aria-hidden="true"
                className="login-logo-icon"
                height={28}
                src="/quopilot-logo.png"
                width={28}
              />
              <span className="login-logo-text">QuoPilot</span>
            </div>
            <p className="login-logo-tagline">
              구매 검토팀의 견적 비교를 AI로 더 빠르게
            </p>
          </div>

          <p className="login-version">v1.3.2</p>

          <div className="login-copy-main">
            <h1 className="login-heading">
              모든 견적 검토를 한곳에서,
              <br />
              더 똑똑하게 시작해 보세요
            </h1>
            <p className="login-subtext">
              이전 프로젝트 확인부터 AI 분석 대시보드까지, 복잡한 견적 검토 과정이
              한눈에 정리돼요.
            </p>
          </div>

          <div aria-hidden="true" className="login-copy-spacer" />
        </div>

        <div className="login-auth-side">
          <div className="login-auth-content">
            <div className="login-auth-header">
              <h2 className="login-auth-title">로그인</h2>
              <p className="login-auth-sub">
                회사 Microsoft 계정으로 계속해 보세요
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
                  <strong>Microsoft Entra ID를 통해 인증해요</strong>
                  <p>
                    조직에서 발급한 회사 이메일로 로그인해 주세요. 안전하게 로그인할 수
                    있어요.
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
