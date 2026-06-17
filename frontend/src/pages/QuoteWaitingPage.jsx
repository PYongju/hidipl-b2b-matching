import { useEffect, useMemo, useRef, useState } from "react";
import AutoSaveStatus from "../components/AutoSaveStatus";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectStepTabs from "../components/ProjectStepTabs";
import { fetchProjectMatches } from "../api/apiClient";
import { buildHydratedProjectFields } from "../utils/projectMatchHydration";

const ACCEPTED_QUOTE_FILES = ".pdf,.xlsx,.xls,.png,.jpg,.jpeg,.webp";

function shouldRestoreMatchData(projectData) {
  if (!projectData?.projectApiId) return false;
  if (projectData.matchHydrationAttempted) return false;

  const hasQuoteIds =
    Array.isArray(projectData.quoteIds) && projectData.quoteIds.length > 0;
  const hasExplanationSource = Boolean(
    projectData.matchId ||
    projectData.cachedExplanation ||
    projectData.matchResult,
  );

  return !hasQuoteIds || !hasExplanationSource;
}

export default function QuoteWaitingPage({
  projectData,
  onBack,
  onGoDashboard,
  onProjectDataChange,
  onGoHome,
}) {
  const [selectedFiles, setSelectedFiles] = useState(projectData.quoteFiles ?? []);
  const [errorMessage, setErrorMessage] = useState("");
  const [note, setNote] = useState(projectData.quoteNote ?? "");
  const [autoSaveStatus, setAutoSaveStatus] = useState("idle");
  const autoSaveStatusTimerRef = useRef(null);
  const hasUploadedQuotes = (projectData.quoteIds?.length ?? 0) > 0;
  const canCompare = selectedFiles.length > 0;
  const receivedCount = selectedFiles.length;
  const requestTargets = useMemo(
    () => resolveRequestTargets(projectData),
    [projectData],
  );

  const showAutoSaveStatus = (status) => {
    if (autoSaveStatusTimerRef.current) {
      window.clearTimeout(autoSaveStatusTimerRef.current);
      autoSaveStatusTimerRef.current = null;
    }

    setAutoSaveStatus(status);

    if (status === "saved" || status === "error") {
      autoSaveStatusTimerRef.current = window.setTimeout(() => {
        setAutoSaveStatus("idle");
        autoSaveStatusTimerRef.current = null;
      }, status === "saved" ? 1800 : 3000);
    }
  };

  useEffect(() => {
    let ignore = false;
    const apiProjectId = projectData.projectApiId;

    if (!apiProjectId || !shouldRestoreMatchData(projectData)) {
      return undefined;
    }

    fetchProjectMatches(apiProjectId)
      .then((matchesResponse) => {
        if (ignore) return;
        onProjectDataChange((current) => ({
          ...current,
          ...buildHydratedProjectFields(matchesResponse, current),
          matchHydrationAttempted: true,
        }));
      })
      .catch((error) => {
        console.error("매칭 결과 조회 실패:", error);
        if (ignore) return;
        onProjectDataChange((current) => ({
          ...current,
          matchHydrationAttempted: true,
        }));
      });

    return () => {
      ignore = true;
    };
  }, [
    projectData.projectApiId,
    projectData.matchId,
    projectData.quoteIds,
    projectData.cachedExplanation,
    projectData.matchResult,
    projectData.matchHydrationAttempted,
  ]);

  useEffect(() => {
    setNote(projectData.quoteNote ?? "");
  }, [projectData.quoteNote]);

  useEffect(() => () => {
    if (autoSaveStatusTimerRef.current) {
      window.clearTimeout(autoSaveStatusTimerRef.current);
    }
  }, []);

  useEffect(() => {
    const sameFiles =
      (projectData.quoteFiles ?? []).length === selectedFiles.length &&
      (projectData.quoteFiles ?? []).every((file, index) => {
        const target = selectedFiles[index];
        return (
          target &&
          target.name === file.name &&
          target.lastModified === file.lastModified &&
          target.size === file.size
        );
      });
    const sameNote = (projectData.quoteNote ?? "") === note;

    if (sameFiles && sameNote) return undefined;

    showAutoSaveStatus("saving");
    const timer = window.setTimeout(() => {
      onProjectDataChange((current) => ({
        ...current,
        quoteFiles: selectedFiles,
        quoteNote: note,
      }));
      showAutoSaveStatus("saved");
    }, 500);

    return () => window.clearTimeout(timer);
  }, [note, onProjectDataChange, projectData.quoteFiles, projectData.quoteNote, selectedFiles]);

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

  const goToQuoteReview = () => {
    if (!canCompare && !hasUploadedQuotes) return;

    onProjectDataChange((current) => ({
      ...current,
      ...(selectedFiles.length ? { quoteFiles: selectedFiles } : {}),
    }));
    onGoDashboard();
  };

  return (
    <div className="flow-page quote-waiting-page">
      <FlowTopbar
        onHome={onGoHome}
        trail="프로젝트 상세 > 견적 수신"
        action={
          <>
            <AutoSaveStatus status={autoSaveStatus} />
            <button className="button action-secondary" onClick={onGoHome} type="button">
              목록
            </button>
            <div className="avatar" />
            <div className="user-name">
              <b>김담당자</b>
              <small>구매검토팀</small>
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
          onGoQuoteReview={canCompare || hasUploadedQuotes ? goToQuoteReview : undefined}
        />

        <section className="quote-status-bar">
          <article>
            <span>현재 상태</span>
            <strong>{hasUploadedQuotes ? "견적서 업로드 완료" : "견적서 업로드 대기"}</strong>
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
            <strong>{hasUploadedQuotes ? "업로드 완료" : "업로드 전"}</strong>
          </article>
        </section>

        <section className="quote-waiting-layout">
          <div className="quote-board-panel">
            <div className="quote-panel-title with-progress">
              <div>
                <h2>견적서 업로드</h2>
                <p>공급사별 견적서를 한 번에 첨부해요. 선택한 파일은 프로젝트 단위로 업로드돼요.</p>
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
              <span>PDF, Excel, 이미지 파일 지원 · 여러 개 선택 가능</span>
            </label>

            <div className="uploaded-list quote-uploaded-list">
              {selectedFiles.length === 0 ? (
                <div className="empty-file-row">
                  아직 업로드할 견적서가 없어요.
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

          <aside className="quote-ops-panel panel-sticky">
            <div className="quote-panel-title quote-ops-panel-title">
              <div>
                <h2>추가 작업</h2>
                <p>견적 수신 단계에서 필요한 후속 작업을 해요.</p>
              </div>
            </div>

            <section>
              <h3>
                견적 요청 발송 대상
                {requestTargets.length > 0 ? (
                  <Badge tone="blue">{requestTargets.length}</Badge>
                ) : null}
              </h3>
              {requestTargets.length === 0 ? (
                <div className="quote-request-empty">
                  파트너 매칭 단계에서 선택한 견적 요청 대상이 없어요.
                  <span>이전 단계에서 발송 대상 공급사를 선택해 주세요.</span>
                </div>
              ) : (
                <div className="selected-partner-list quote-request-target-list">
                  {requestTargets.map((partner) => (
                    <div className="selected-partner-pill quote-request-target-pill" key={partner.id}>
                      <span>
                        <b>{partner.name}</b>
                        <small>
                          {partner.score != null ? `AI 추천 점수 ${partner.score}` : "점수 미확인"}
                          {partner.response ? ` · 응답 ${partner.response}` : ""}
                        </small>
                      </span>
                      {partner.caution ? <Badge tone="orange">주의</Badge> : null}
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h3>업로드 안내</h3>
              <button
                className="quote-action-button"
                disabled
                title="현재 버전에서는 프로젝트 단위 업로드만 사용해요."
                type="button"
              >
                프로젝트 단위 일괄 업로드 <Badge tone="blue">{selectedFiles.length}</Badge>
              </button>
              <button
                className="quote-action-button"
                disabled
                title="공급사명 연결은 견적서 내용 추출 후 확인할 수 있어요."
                type="button"
              >
                공급사명은 견적서 내용 추출 후 확인
              </button>
            </section>

            <section>
              <h3>후속 작업</h3>
              <button
                className="quote-action-button"
                disabled
                title="아래 ‘업로드 후 비교 분석’ 버튼을 사용해 주세요."
                type="button"
              >
                업로드 완료 후 비교 분석
              </button>
            </section>

            <label className="request-memo">
              <span>내부 메모</span>
              <textarea
                onChange={(event) => setNote(event.target.value)}
                value={note}
              />
            </label>
          </aside>
        </section>
      </main>

      <footer className="quote-waiting-bottom-actions">
        <span>
          {hasUploadedQuotes
            ? "견적서 업로드 완료"
            : selectedFiles.length
              ? `견적서 ${receivedCount}개 선택됨`
              : "견적서를 업로드하면 비교 검토를 시작할 수 있어요."}
        </span>
        <div>
          <button className="button action-secondary" onClick={onBack} type="button">이전</button>
          <button
            className="button action-primary"
            disabled={!canCompare}
            onClick={goToQuoteReview}
            type="button"
          >
            다음: 견적 검토
          </button>
        </div>
      </footer>
    </div>
  );
}

function resolveRequestTargets(projectData) {
  if (projectData.requestTargets?.length) {
    return projectData.requestTargets;
  }

  const targetIds = projectData.requestTargetIds ?? [];
  if (!targetIds.length) return [];

  const candidates = projectData.candidateVendors ?? [];
  return targetIds
    .map((targetId) => {
      const raw = candidates.find(
        (candidate) =>
          (candidate.vendor_id ??
            candidate.vendor_name ??
            candidate.partner_id ??
            candidate.partner_name) === targetId,
      );
      if (!raw) {
        return { id: targetId, name: String(targetId) };
      }
      return {
        id: targetId,
        name: raw.vendor_name ?? raw.partner_name ?? raw.name ?? String(targetId),
        score:
          typeof raw.semantic_similarity_score === "number"
            ? raw.semantic_similarity_score <= 1
              ? Math.round(raw.semantic_similarity_score * 100)
              : Math.round(raw.semantic_similarity_score)
            : null,
        response:
          typeof raw.response_speed === "number" ? `${raw.response_speed}시간` : raw.response_speed ?? "미확인",
        caution: (raw.filter_reasons ?? []).some(
          (reason) => !/^상위 \d+개 추천 후보 외$/.test(String(reason ?? "").trim()),
        ),
      };
    })
    .filter(Boolean);
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
