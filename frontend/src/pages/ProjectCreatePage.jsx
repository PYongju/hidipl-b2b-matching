import { useRef, useState } from 'react';
import Badge from '../components/Badge';
import FlowTopbar from '../components/FlowTopbar';
import { formatNumberInput } from '../utils/formatters';

export default function ProjectCreatePage({
  projectData,
  onProjectDataChange,
  onBack,
  onAnalyze,
  onGoHome,
}) {
  const [step, setStep] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);
  const uploadedFiles = projectData.quoteFiles ?? [];
  const steps = [
    ["기본 정보", "회사명, 위치, 일정"],
    ["요구사항", "스펙, 예산, 우선순위"],
    ["견적서 업로드", "공급사별 파일 첨부"],
  ];

  const isSameFile = (left, right) =>
    left.name === right.name &&
    left.lastModified === right.lastModified &&
    left.size === right.size;

  const appendFiles = (fileList) => {
    const newFiles = Array.from(fileList || []);
    if (newFiles.length === 0) {
      return;
    }

    onProjectDataChange((current) => {
      const existingFiles = current.quoteFiles ?? [];
      const mergedFiles = [...existingFiles];

      for (const file of newFiles) {
        if (!mergedFiles.some((existingFile) => isSameFile(existingFile, file))) {
          mergedFiles.push(file);
        }
      }

      return {
        ...current,
        quoteFiles: mergedFiles,
      };
    });
  };

  const handleFiles = (event) => {
    appendFiles(event.target.files);
    event.target.value = "";
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  };

  const handleDragEnter = (event) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    const relatedTarget = event.relatedTarget;
    if (relatedTarget && event.currentTarget.contains(relatedTarget)) return;
    setIsDragging(false);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    appendFiles(event.dataTransfer.files);
  };

  const openFilePicker = () => {
    fileInputRef.current?.click();
  };

  const removeFile = (fileToRemove) => {
    onProjectDataChange((current) => ({
      ...current,
      quoteFiles: (current.quoteFiles ?? []).filter((file) => !isSameFile(file, fileToRemove)),
    }));
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
        onHome={onGoHome}
        trail="프로젝트 목록 > 새 프로젝트 생성"
        action={<button className="button" onClick={onBack} type="button">취소</button>}
      />
      <main className="wizard-layout">
        <aside className="wizard-nav">
          <h1>새 프로젝트 생성</h1>
          <p>3단계로 AI 견적 비교를 시작해요.</p>
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
              <p>발주사와 프로젝트 일정을 입력해요.</p>
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
                    <option>요구사항</option>
                    <option>파트너 매칭</option>
                    <option>견적 수신</option>
                    <option>견적 검토</option>
                  </select>
                </label>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="wizard-content">
              <h2>고객 요구사항</h2>
              <p>공급사 비교에 필요한 스펙, 예산, 우선순위를 정리해요.</p>
              <div className="form-grid">
                <label>
                  <span>디스플레이 크기</span>
                  <div className="budget-field">
                    <input
                      inputMode="decimal"
                      onChange={(event) => {
                        const value = event.target.value.replace(/인치/g, "").trim();
                        updateProject("displaySize", value ? `${value}인치` : "");
                      }}
                      placeholder="55"
                      value={(projectData.displaySize ?? "").replace(/인치$/, "")}
                    />
                    <span>인치</span>
                  </div>
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
              <p>공급사별 견적서를 한 번에 또는 하나씩 첨부할 수 있어요. 선택한 파일은 아래 목록에 쌓여요.</p>
              <div
                className={`drop-zone upload-drop-zone${isDragging ? " is-dragging" : ""}`}
                onClick={openFilePicker}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openFilePicker();
                  }
                }}
                role="button"
                tabIndex={0}
              >
                <input
                  accept=".pdf,.xlsx,.xls,.png,.jpg,.jpeg,.webp"
                  multiple
                  onChange={handleFiles}
                  ref={fileInputRef}
                  type="file"
                />
                <b>파일을 드래그하거나 클릭하여 업로드</b>
                <span>PDF, Excel, 이미지 파일 지원 · 여러 개 또는 하나씩 선택 가능</span>
              </div>
              <div className="uploaded-list">
                {uploadedFiles.length === 0 ? (
                  <div className="empty-file-row">아직 업로드된 견적서가 없어요.</div>
                ) : (
                  uploadedFiles.map((file) => (
                    <div className="file-row" key={`${file.name}-${file.lastModified}-${file.size}`}>
                      <span className="file-row-name">{file.name}</span>
                      <div className="file-row-actions">
                        <Badge tone="green">선택 완료</Badge>
                        <button
                          aria-label={`${file.name} 삭제`}
                          className="icon-button file-remove-button"
                          onClick={() => removeFile(file)}
                          type="button"
                        >
                          <i aria-hidden="true" className="fa-solid fa-xmark" />
                        </button>
                      </div>
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
