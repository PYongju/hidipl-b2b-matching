import { useState } from 'react';
import Badge from '../components/Badge';
import FlowTopbar from '../components/FlowTopbar';
import { formatNumberInput } from '../utils/formatters';

export default function ProjectCreatePage({ projectData, onProjectDataChange, onBack, onAnalyze }) {
  const [step, setStep] = useState(1);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const steps = [
    ["기본 정보", "회사명, 위치, 일정"],
    ["요구사항", "스펙, 예산, 우선순위"],
    ["견적서 업로드", "공급사별 파일 첨부"],
  ];

  const handleFiles = (event) => {
    const files = Array.from(event.target.files || []);
    setUploadedFiles(files.map((file) => file.name));
  };

  const updateProject = (field, value) => {
    onProjectDataChange((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const next = () => {
    if (step === steps.length) {
      onAnalyze();
      return;
    }
    setStep((current) => current + 1);
  };

  return (
    <div className="flow-page">
      <FlowTopbar
        trail="프로젝트 목록 > 새 프로젝트 생성"
        action={<button className="button" onClick={onBack} type="button">취소</button>}
      />
      <main className="wizard-layout">
        <aside className="wizard-nav">
          <h1>새 프로젝트 생성</h1>
          <p>3단계로 AI 견적 비교를 시작합니다.</p>
          {steps.map(([title, desc], index) => {
            const current = index + 1;
            return (
              <button
                className={`wizard-step ${step === current ? "active" : ""} ${step > current ? "done" : ""}`}
                key={title}
                onClick={() => setStep(current)}
                type="button"
              >
                <span>{step > current ? "✓" : current}</span>
                <b>{title}</b>
                <small>{desc}</small>
              </button>
            );
          })}
        </aside>

        <section className="wizard-panel">
          {step === 1 && (
            <div className="wizard-content">
              <h2>프로젝트 기본 정보</h2>
              <p>발주사와 프로젝트 일정을 입력합니다.</p>
              <div className="form-grid">
                <label>
                  <span>회사명 *</span>
                  <input
                    onChange={(event) => updateProject("companyName", event.target.value)}
                    value={projectData.companyName}
                  />
                </label>
                <label>
                  <span>설치 위치 *</span>
                  <input
                    onChange={(event) => updateProject("location", event.target.value)}
                    value={projectData.location}
                  />
                </label>
                <label>
                  <span>프로젝트명</span>
                  <input
                    onChange={(event) => updateProject("projectName", event.target.value)}
                    value={projectData.projectName}
                  />
                </label>
                <label>
                  <span>활용 용도 및 디스플레이 요구사항</span>
                  <input
                    onChange={(event) => updateProject("usage", event.target.value)}
                    value={projectData.usage}
                  />
                </label>
                <label>
                  <span>프로젝트 일정</span>
                  <input
                    onChange={(event) => updateProject("projectDate", event.target.value)}
                    type="date"
                    value={projectData.projectDate}
                  />
                </label>
                <label>
                  <span>현재 단계</span>
                  <select
                    onChange={(event) => updateProject("currentStage", event.target.value)}
                    value={projectData.currentStage}
                  >
                    <option>정보 탐색</option>
                    <option>견적 수집 중</option>
                    <option>비교 검토 중</option>
                    <option>발주 직전</option>
                  </select>
                </label>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="wizard-content">
              <h2>고객 요구사항</h2>
              <p>공급사 비교에 필요한 스펙, 예산, 우선순위를 정리합니다.</p>
              <div className="form-grid">
                <label>
                  <span>디스플레이 크기</span>
                  <select
                    onChange={(event) => updateProject("displaySize", event.target.value)}
                    value={projectData.displaySize}
                  >
                    <option>55인치</option>
                    <option>65인치</option>
                    <option>75인치</option>
                    <option>85인치</option>
                  </select>
                </label>
                <label>
                  <span>수량</span>
                  <input
                    onChange={(event) => updateProject("quantity", event.target.value)}
                    value={projectData.quantity}
                  />
                </label>
                <label>
                  <span>예산 상한</span>
                  <div className="budget-field">
                    <input
                      inputMode="numeric"
                      onChange={(event) =>
                        updateProject("budgetAmount", formatNumberInput(event.target.value))
                      }
                      placeholder="0"
                      value={projectData.budgetAmount}
                    />
                    <span>원</span>
                  </div>
                </label>
                <label>
                  <span>운용 시간</span>
                  <select
                    onChange={(event) => updateProject("operationTime", event.target.value)}
                    value={projectData.operationTime}
                  >
                    <option>24/7</option>
                    <option>업무시간</option>
                  </select>
                </label>
              </div>
              <div className="priority-row" aria-label="고객 우선순위">
                {["최저가 우선", "납기 우선", "보증/A/S 우선", "스펙 우선", "균형 추천"].map((item) => (
                  <button
                    className={item === projectData.reviewPreset ? "chip active" : "chip"}
                    key={item}
                    onClick={() => updateProject("reviewPreset", item)}
                    type="button"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="wizard-content">
              <h2>견적서 업로드</h2>
              <p>공급사별 견적서를 첨부합니다. 선택한 파일명은 아래 목록에 표시됩니다.</p>
              <label className="drop-zone upload-drop-zone">
                <input
                  accept=".pdf,.xlsx,.xls,.doc,.docx"
                  multiple
                  onChange={handleFiles}
                  type="file"
                />
                <b>파일을 드래그하거나 클릭하여 업로드</b>
                <span>PDF, Excel, Word 파일 지원 · 여러 개 선택 가능</span>
              </label>
              <div className="uploaded-list">
                {uploadedFiles.length === 0 ? (
                  <div className="empty-file-row">아직 업로드된 견적서가 없습니다.</div>
                ) : (
                  uploadedFiles.map((file) => (
                    <div className="file-row" key={file}>
                      <span>{file}</span>
                      <Badge tone="green">선택 완료</Badge>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </section>
      </main>
      <footer className="wizard-footer">
        <span>{step} / {steps.length} 단계</span>
        <div>
          <button className="button" disabled={step === 1} onClick={() => setStep(step - 1)} type="button">
            이전
          </button>
          <button className="button action-primary" onClick={next} type="button">
            {step === steps.length ? "AI 분석 시작" : "다음"}
          </button>
        </div>
      </footer>
    </div>
  );
}
