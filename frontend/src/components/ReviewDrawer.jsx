import { useState } from 'react';
import Badge from './Badge';

export default function ReviewDrawer({ open, onClose }) {
  const [step, setStep] = useState(1);
  const stepLabels = ["요구사항", "견적 업로드", "AI 비교"];

  if (!open) return null;

  return (
    <div className="drawer-layer">
      <button
        aria-label="새 프로젝트 생성 닫기"
        className="drawer-backdrop"
        onClick={onClose}
        type="button"
      />
      <aside className="review-drawer" aria-label="새 프로젝트 생성">
        <div className="drawer-header">
          <div className="drawer-title-row">
            <div>
              <p>새 프로젝트 생성</p>
              <h2>요구사항 입력부터 AI 비교까지</h2>
            </div>
            <button className="drawer-close" onClick={onClose} type="button" aria-label="닫기">
              ×
            </button>
          </div>

          <div className="drawer-steps">
            {stepLabels.map((label, index) => {
              const current = index + 1;
              return (
                <div className={`drawer-step ${step >= current ? "active" : ""}`} key={label}>
                  <span>{current}</span>
                  <b>{label}</b>
                </div>
              );
            })}
          </div>
        </div>

        <div className="drawer-body">
          {step === 1 && (
            <div className="drawer-form">
              <label>
                <span>요청 품목</span>
                <input defaultValue="회의실 LED 디스플레이 설치" />
              </label>

              <div className="drawer-two-col">
                <label>
                  <span>예산 상한</span>
                  <input defaultValue="25,000,000원" />
                </label>
                <label>
                  <span>희망 납기</span>
                  <input defaultValue="21일 이내" />
                </label>
              </div>

              <div>
                <div className="drawer-label">고객 우선순위</div>
                <div className="priority-grid">
                  {["최저가 우선", "납기 우선", "보증/A/S 우선", "스펙 우선", "균형 추천"].map(
                    (item) => (
                      <button
                        className={`priority-button ${item === "균형 추천" ? "selected" : ""}`}
                        key={item}
                        type="button"
                      >
                        {item}
                      </button>
                    ),
                  )}
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="drawer-form">
              <div className="upload-box">
                <div className="upload-icon">⇧</div>
                <h3>견적서 PDF 업로드</h3>
                <p>여러 공급사의 견적서를 한 번에 업로드할 수 있어요.</p>
                <button type="button">파일 선택</button>
              </div>

              {["A_Display_quote.pdf", "BrightSign_quote.pdf", "VisionTech_quote.pdf"].map((file) => (
                <div className="upload-file" key={file}>
                  <span>▤ {file}</span>
                  <Badge tone="green">업로드 완료</Badge>
                </div>
              ))}
            </div>
          )}

          {step === 3 && (
            <div className="drawer-form">
              <div className="ai-ready">
                <div className="ai-ready-icon">✦</div>
                <div>
                  <h3>AI 비교 준비 완료</h3>
                  <p>요구사항과 견적서 기준으로 적합도, 리스크, 추천 사유를 만들어요.</p>
                </div>
              </div>

              <button className="start-analysis" onClick={onClose} type="button">
                AI 비교 시작 후 대시보드 반영
              </button>
            </div>
          )}
        </div>

        <div className="drawer-footer">
          <button
            className="button"
            disabled={step === 1}
            onClick={() => setStep(Math.max(1, step - 1))}
            type="button"
          >
            이전
          </button>
          {step < 3 && (
            <button
              className="button drawer-next"
              onClick={() => setStep(step + 1)}
              type="button"
            >
              다음 ›
            </button>
          )}
        </div>
      </aside>
    </div>
  );
}
