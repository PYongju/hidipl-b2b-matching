import { useMemo, useState } from "react";
import Badge from "../components/Badge";
import { fetchProjectMatches } from "../api/apiClient";
import FlowBottomBar from "../components/FlowBottomBar";
import FlowTopbar from "../components/FlowTopbar";
import ProjectStepTabs from "../components/ProjectStepTabs";
import useAutoSaveStatus from "../hooks/useAutoSaveStatus";
import { buildHydratedProjectFields } from "../utils/projectMatchHydration";
import { formatProjectSolutions } from "../utils/projectRequestText";

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
  const { statusMessage, notifyAutoSave } = useAutoSaveStatus();
  const [selectedFiles, setSelectedFiles] = useState(
    projectData.quoteFiles ?? [],
  );
  const [errorMessage, setErrorMessage] = useState("");
  const hasUploadedQuotes = (projectData.quoteIds?.length ?? 0) > 0;
  const canCompare = selectedFiles.length > 0;
  const requestTargets = useMemo(
    () => resolveRequestTargets(projectData),
    [projectData],
  );

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
      .catch(() => {
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
    projectData.projectApiId,
    projectData.matchId,
    projectData.quoteIds,
    projectData.cachedExplanation,
    projectData.matchResult,
    projectData.matchHydrationAttempted,
  ]);

  const updateFiles = (files) => {
    setSelectedFiles(files);
    onProjectDataChange((current) => ({
      ...current,
      quoteFiles: files,
      lastScreen: "quoteWaiting",
    }));
    notifyAutoSave();
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
        <section className="partner-head">
          <div>
            <button className="partner-back" onClick={onBack} type="button">
              &lt;
            </button>
            <span>견적 수신</span>
          </div>
        </section>

        <ProjectStepTabs
          activeStep={3}
          onGoPartnerMatching={onBack}
          onGoQuoteReview={
            canCompare || hasUploadedQuotes ? goToQuoteReview : undefined
          }
        />

        <section className="partner-project-summary six">
          <SummaryItem label="회사명" value={projectData.companyName || "미입력"} />
          <SummaryItem label="위치" value={projectData.location || "미입력"} />
          <SummaryItem
            label="일정"
            value={projectData.projectDate || "일정 미정"}
          />
          <SummaryItem
            label="발주처 유형"
            value={projectData.clientType || "미입력"}
          />
          <SummaryItem
            label="솔루션"
            value={formatProjectSolutions(projectData, "미선택")}
          />
          <SummaryItem label="상태" value="견적 수신" />
        </section>

        <section className="quote-waiting-layout">
          <div className="quote-board-panel">
            <div className="quote-panel-title with-progress">
              <div>
                <h2>견적서 업로드</h2>
                <p>
                  공급사로부터 견적서를 받은 뒤에 업로드해 주세요. 업로드한 파일은 프로젝트
                  비교에 사용됩니다.
                </p>
              </div>
              <div className="quote-progress">
                <span>{selectedFiles.length}개 업로드</span>
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
              <b>파일을 드래그하거나 클릭해서 업로드</b>
              <span>PDF, Excel, 이미지 파일 지원 · 여러 개 동시 선택 가능</span>
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
                      <Badge tone="green">업로드 완료</Badge>
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

          <aside className="quote-ops-panel sticky-column">
            <div className="quote-panel-title quote-ops-panel-title">
              <div>
                <h2>확인 정보</h2>
                <p>견적 수신 화면에서 필요한 정보를 간단히 확인해요.</p>
              </div>
            </div>

            <section>
              <h3>
                견적 요청 발송 대상{" "}
                {requestTargets.length > 0 ? (
                  <Badge tone="blue">{requestTargets.length}</Badge>
                ) : null}
              </h3>
              {requestTargets.length === 0 ? (
                <div className="quote-request-empty">
                  파트너 매칭 화면에서 업로드된 견적 요청 대상이 없어요.
                  <span>이전 화면에서 발송 대상 공급사를 선택해 주세요.</span>
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
                          {partner.response ? ` · 응답 ${partner.response}` : ""}
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

      <FlowBottomBar
        backLabel="이전 단계"
        nextDisabled={!canCompare && !hasUploadedQuotes}
        nextLabel="다음: 견적 비교 검토"
        onBack={onBack}
        onNext={goToQuoteReview}
        statusMessage={statusMessage}
      />
    </div>
  );
}

function SummaryItem({ label, value }) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
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
            : raw.response_speed ?? "미확인",
        caution: (raw.filter_reasons ?? []).some(
          (reason) => !/^상위 \d+개 추천 후보/.test(String(reason ?? "").trim()),
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
