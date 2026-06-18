import { useEffect, useMemo, useRef, useState } from "react";
import AutoSaveStatus from "../components/AutoSaveStatus";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectDetailHeader from "../components/ProjectDetailHeader";
import ProjectStepTabs from "../components/ProjectStepTabs";
import { fetchProjectMatches } from "../api/apiClient";
import { buildHydratedProjectFields } from "../utils/projectMatchHydration";
import { buildProjectInfoSummary } from "../utils/projectRequestText";

const ACCEPTED_QUOTE_FILES = ".pdf,.xlsx,.xls,.png,.jpg,.jpeg,.webp";
const RANK_EXCLUSION_PATTERN = /^상위 \d+개 추천 후보 외$/;

function shouldRestoreMatchData(projectData) {
  if (!projectData?.projectApiId) return false;
  if (projectData.matchHydrationAttempted) return false;

  const serverStatus = projectData.serverStatus ?? projectData.status;
  if (serverStatus !== "matched") return false; // 추가

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
  const [selectedFiles, setSelectedFiles] = useState(
    projectData.quoteFiles ?? [],
  );
  const [errorMessage, setErrorMessage] = useState("");
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
      autoSaveStatusTimerRef.current = window.setTimeout(
        () => {
          setAutoSaveStatus("idle");
          autoSaveStatusTimerRef.current = null;
        },
        status === "saved" ? 1800 : 3000,
      );
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
    onProjectDataChange,
    projectData.cachedExplanation,
    projectData.matchHydrationAttempted,
    projectData.matchId,
    projectData.matchResult,
    projectData.projectApiId,
    projectData.quoteIds,
  ]);

  useEffect(
    () => () => {
      if (autoSaveStatusTimerRef.current) {
        window.clearTimeout(autoSaveStatusTimerRef.current);
      }
    },
    [],
  );

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

    if (sameFiles) return undefined;

    showAutoSaveStatus("saving");
    const timer = window.setTimeout(() => {
      onProjectDataChange((current) => ({
        ...current,
        quoteFiles: selectedFiles,
      }));
      showAutoSaveStatus("saved");
    }, 500);

    return () => window.clearTimeout(timer);
  }, [onProjectDataChange, projectData.quoteFiles, selectedFiles]);

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

  const projectInfoSummary = buildProjectInfoSummary(projectData, {
    includeLocation: true,
  });

  return (
    <div className="flow-page quote-waiting-page">
      <FlowTopbar
        onHome={onGoHome}
        trail="프로젝트 상세 > 견적 수신"
        action={
          <>
            <AutoSaveStatus status={autoSaveStatus} />
            <button
              className="button action-secondary"
              onClick={onGoHome}
              type="button"
            >
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
        <ProjectDetailHeader
          infoSummary={projectInfoSummary}
          onBack={onBack}
          projectName={projectData.projectName || "새 프로젝트"}
        />

        <ProjectStepTabs
          activeStep={3}
          onGoPartnerMatching={onBack}
          onGoQuoteReview={
            canCompare || hasUploadedQuotes ? goToQuoteReview : undefined
          }
        />

        <section className="quote-waiting-layout">
          <div className="quote-board-panel">
            <div className="quote-panel-title with-progress">
              <div>
                <h2>견적서 업로드</h2>
                <p>
                  공급사별 견적서를 한 번에 첨부해요. 선택한 파일은 프로젝트
                  단위로 업로드돼요.
                </p>
              </div>
              <div className="quote-progress">
                <span>{selectedFiles.length}개 선택</span>
                <div>
                  <i style={{ width: selectedFiles.length ? "100%" : "0%" }} />
                </div>
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
                  아직 업로드한 견적서가 없어요.
                </div>
              ) : (
                selectedFiles.map((file) => (
                  <div
                    className="file-row"
                    key={`${file.name}-${file.lastModified}-${file.size}`}
                  >
                    <div>
                      <span className="file-row-name">{file.name}</span>
                      <small>{formatFileSize(file.size)}</small>
                    </div>
                    <div className="file-row-actions">
                      <Badge tone="green">선택 완료</Badge>
                      <button
                        aria-label={`${file.name} 제거`}
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
                <h2>견적 요청 발송 대상</h2>
                <p>이전 단계에서 선택한 공급사를 다시 확인해요.</p>
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
                    <div
                      className="selected-partner-pill quote-request-target-pill"
                      key={partner.id}
                    >
                      <span>
                        <b>{partner.name}</b>
                        <small>
                          {partner.score != null
                            ? `AI 추천 점수 ${partner.score}`
                            : "점수 미확인"}
                          {partner.response
                            ? ` · 응답 ${partner.response}`
                            : ""}
                        </small>
                      </span>
                      {partner.caution ? (
                        <Badge tone="orange">주의</Badge>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </section>
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
          <button
            className="button action-secondary"
            onClick={onBack}
            type="button"
          >
            이전
          </button>
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
        name:
          raw.vendor_name ?? raw.partner_name ?? raw.name ?? String(targetId),
        score:
          typeof raw.semantic_similarity_score === "number"
            ? raw.semantic_similarity_score <= 1
              ? Math.round(raw.semantic_similarity_score * 100)
              : Math.round(raw.semantic_similarity_score)
            : null,
        response:
          typeof raw.response_speed === "number"
            ? `${raw.response_speed}시간`
            : (raw.response_speed ?? "미확인"),
        caution: (raw.filter_reasons ?? []).some(
          (reason) => !RANK_EXCLUSION_PATTERN.test(String(reason ?? "").trim()),
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
