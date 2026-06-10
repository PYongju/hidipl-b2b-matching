import { useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectStepTabs from "../components/ProjectStepTabs";
import { uploadProjectQuotes } from "../api/apiClient";
const ACCEPTED_QUOTE_FILES = ".pdf,.xlsx,.xls,.doc,.docx,.png,.jpg,.jpeg,.webp";

export default function QuoteWaitingPage({
  projectData,
  onBack,
  onGoDashboard,
  onProjectDataChange,
}) {
  const [selectedFiles, setSelectedFiles] = useState(projectData.quoteFiles ?? []);
  const [uploadState, setUploadState] = useState("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const canCompare = selectedFiles.length > 0 && uploadState !== "uploading";
  const viewedCount = 0;
  const receivedCount = selectedFiles.length;

  const updateFiles = (files) => {
    setSelectedFiles(files);
    onProjectDataChange((current) => ({
      ...current,
      quoteFiles: files,
    }));
  };

  const handleFiles = (event) => {
    const nextFiles = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!nextFiles.length) return;
    updateFiles(mergeFiles(selectedFiles, nextFiles));
    setErrorMessage("");
  };

  const removeFile = (fileToRemove) => {
    updateFiles(
      selectedFiles.filter(
        (file) =>
          `${file.name}-${file.lastModified}-${file.size}` !==
          `${fileToRemove.name}-${fileToRemove.lastModified}-${fileToRemove.size}`,
      ),
    );
  };

  const uploadQuotes = async () => {
    if (!canCompare) return;
    setUploadState("uploading");
    setErrorMessage("");

    try {
      const projectApiId = projectData.projectApiId;
      if (!projectApiId) {
        throw new Error("프로젝트 API ID가 없어 견적서를 업로드할 수 없습니다.");
      }

      const uploadResult = await uploadProjectQuotes(projectApiId, selectedFiles);
      const quoteIds =
        uploadResult.quote_ids ??
        uploadResult.quotes?.map((quote) => quote.quote_id ?? quote.id) ??
        [];

      onProjectDataChange((current) => ({
        ...current,
        quoteFiles: selectedFiles,
        quoteIds,
        quoteUploadResult: uploadResult,
      }));
      setUploadState("done");
      onGoDashboard();
    } catch (error) {
      setUploadState("error");
      setErrorMessage(error.message || "견적서 업로드 중 오류가 발생했습니다.");
    }
  };

  return (
    <div className="flow-page quote-waiting-page">
      <FlowTopbar
        trail="프로젝트 상세 > 견적 수신"
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
            <span>견적 수신</span>
          </div>
        </section>

        <ProjectStepTabs
          activeStep={3}
          onGoPartnerMatching={onBack}
          onGoQuoteReview={uploadState === "done" ? onGoDashboard : undefined}
        />

        <section className="quote-status-bar">
          <article>
            <span>요청 상태</span>
            <strong>견적 요청 발송됨</strong>
          </article>
          <article>
            <span>견적서 업로드</span>
            <strong>{selectedFiles.length}개 선택됨</strong>
          </article>
          <article>
            <span>업로드 방식</span>
            <strong>프로젝트 단위</strong>
          </article>
          <article>
            <span>마지막 업데이트</span>
            <strong>업로드 후 자동 갱신</strong>
          </article>
        </section>

        <section className="quote-waiting-layout">
          <div className="quote-board-panel">
            <div className="quote-panel-title with-progress">
              <div>
                <h2>견적서 업로드</h2>
                <p>공급사별 견적서를 한 번에 첨부합니다. 선택한 파일은 프로젝트 단위로 업로드됩니다.</p>
              </div>
              <div className="quote-progress">
                <span>{selectedFiles.length}개 선택</span>
                <div><i style={{ width: selectedFiles.length ? "100%" : "0%" }} /></div>
              </div>
            </div>

            <label className="drop-zone upload-drop-zone quote-bulk-drop-zone">
              <input
                accept={ACCEPTED_QUOTE_FILES}
                multiple
                onChange={handleFiles}
                type="file"
              />
              <b>파일을 드래그하거나 클릭하여 업로드</b>
              <span>PDF, Excel, Word, 이미지 파일 지원 · 여러 개 선택 가능</span>
            </label>

            <div className="uploaded-list quote-uploaded-list">
              {selectedFiles.length === 0 ? (
                <div className="empty-file-row">
                  아직 업로드할 견적서가 없습니다.
                </div>
              ) : (
                selectedFiles.map((file) => (
                  <div className="file-row" key={`${file.name}-${file.lastModified}-${file.size}`}>
                    <div>
                      <span className="file-row-name">{file.name}</span>
                      <small>{formatFileSize(file.size)}</small>
                    </div>
                    <div className="file-row-actions">
                      <Badge tone="green">선택 완료</Badge>
                      <button
                        aria-label={`${file.name} 삭제`}
                        className="icon-button file-remove-button"
                        onClick={() => removeFile(file)}
                        type="button"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {errorMessage ? (
              <div className="quote-upload-error">{errorMessage}</div>
            ) : null}
          </div>

          <aside className="quote-ops-panel">
            <div className="quote-panel-title">
              <h2>운영 액션</h2>
              <p>수신 대기 단계에서 필요한 후속 조치를 수행합니다.</p>
            </div>

            <section>
              <h3>리마인드 발송</h3>
              <button className="quote-action-button" type="button">
                미열람 업체에 발송 <Badge tone="blue">{viewedCount}</Badge>
              </button>
              <button className="quote-action-button" type="button">
                전체 미수신 업체에 발송 <Badge tone="blue">-</Badge>
              </button>
            </section>

            <section>
              <h3>요청 대상 관리</h3>
              <button className="quote-action-button" type="button">요청 대상 추가</button>
              <button className="quote-action-button" type="button">수동 업로드 등록</button>
            </section>

            <label className="request-memo">
              <span>내부 메모</span>
              <textarea defaultValue="현재는 견적서를 프로젝트 단위로 업로드합니다. 업체명 매핑은 OCR/파싱 결과에서 확인 예정." />
            </label>
          </aside>
        </section>
      </main>

      <footer className="quote-waiting-bottom-actions">
        <span>
          {uploadState === "done"
            ? "견적서 업로드 완료"
            : selectedFiles.length
              ? `견적서 ${receivedCount}개 선택됨`
              : "견적서를 업로드하면 비교 검토를 시작할 수 있습니다."}
        </span>
        <div>
          <button className="button action-secondary" type="button">임시 저장</button>
          <button className="button button-blue" type="button">리마인드 발송</button>
          <button
            className="button action-primary"
            disabled={!canCompare}
            onClick={uploadQuotes}
            type="button"
          >
            {uploadState === "uploading" ? "업로드 중..." : "업로드 후 비교 분석"}
          </button>
        </div>
      </footer>
    </div>
  );
}

function mergeFiles(existingFiles, nextFiles) {
  const fileMap = new Map();
  [...existingFiles, ...nextFiles].forEach((file) => {
    fileMap.set(`${file.name}-${file.lastModified}-${file.size}`, file);
  });
  return Array.from(fileMap.values());
}

function formatFileSize(size) {
  if (!size) return "0 KB";
  if (size < 1024 * 1024) return `${Math.ceil(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
