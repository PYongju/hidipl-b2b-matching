import { useEffect, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectListSkeleton from "../components/ProjectListSkeleton";
import { EMPTY_PROJECTS, getUserDisplayName, USER } from "../constants/uiText";

const FILTER_ALL = "전체";
const STATUS_IN_PROGRESS = "진행 중";
const STATUS_IN_REVIEW = "검토 중";
const STATUS_APPROVAL_REQUEST = "결재 요청";
const STATUS_DONE = "완료";
const WORKFLOW_APPROVAL_REQUEST = "컨펌 요청";

const filterOptions = [
  FILTER_ALL,
  STATUS_IN_PROGRESS,
  STATUS_IN_REVIEW,
  STATUS_APPROVAL_REQUEST,
  STATUS_DONE,
];

export default function ProjectListPage({
  projects,
  isLoading = false,
  loadError = "",
  onCreate,
  onOpenDashboard,
  onEditProject,
  onDeleteProjects,
  onReloadProjects,
  onGoHome,
}) {
  const [selectedIds, setSelectedIds] = useState([]);
  const [openMenuId, setOpenMenuId] = useState("");
  const [activeFilter, setActiveFilter] = useState(FILTER_ALL);
  const [searchTerm, setSearchTerm] = useState("");
  const [manageMode, setManageMode] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  useEffect(() => {
    setSelectedIds((current) =>
      current.filter((id) => projects.some((project) => project.id === id)),
    );
  }, [projects]);

  const completedCount = projects.filter(
    (project) => normalizeStatus(project.status) === STATUS_DONE,
  ).length;
  const activeCount = projects.filter(
    (project) => normalizeStatus(project.status) === STATUS_IN_PROGRESS,
  ).length;
  const reviewCount = projects.filter(
    (project) => normalizeStatus(project.status) === STATUS_IN_REVIEW,
  ).length;
  const approvalRequestCount = projects.filter(isApprovalRequestProject).length;

  const filteredProjects = projects.filter((project) => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    const projectId = String(project.id ?? "");
    const projectName = String(project.name ?? "");
    const matchesSearch =
      !normalizedSearch ||
      projectId.toLowerCase().includes(normalizedSearch) ||
      projectName.toLowerCase().includes(normalizedSearch);

    if (!matchesSearch) return false;
    if (activeFilter === FILTER_ALL) return true;
    if (activeFilter === STATUS_APPROVAL_REQUEST) {
      return isApprovalRequestProject(project);
    }
    return normalizeStatus(project.status) === activeFilter;
  });

  const visibleProjectIds = filteredProjects.map((project) => project.id);
  const allVisibleSelected =
    visibleProjectIds.length > 0 &&
    visibleProjectIds.every((id) => selectedIds.includes(id));

  const toggleSelected = (projectId) => {
    setSelectedIds((current) =>
      current.includes(projectId)
        ? current.filter((id) => id !== projectId)
        : [...current, projectId],
    );
  };

  const toggleSelectAll = () => {
    if (allVisibleSelected) {
      setSelectedIds((current) =>
        current.filter((id) => !visibleProjectIds.includes(id)),
      );
      return;
    }

    setSelectedIds((current) => [
      ...new Set([...current, ...visibleProjectIds]),
    ]);
  };

  const enterManageMode = () => {
    setManageMode(true);
    setOpenMenuId("");
  };

  const cancelManageMode = () => {
    setManageMode(false);
    setDeleteConfirmOpen(false);
    setOpenMenuId("");
    setSelectedIds([]);
  };

  const requestDeleteSelected = () => {
    if (selectedIds.length === 0) return;
    setDeleteConfirmOpen(true);
  };

  const confirmDeleteSelected = async () => {
    if (selectedIds.length === 0) return;
    await onDeleteProjects(selectedIds);
    setDeleteConfirmOpen(false);
    setManageMode(false);
    setSelectedIds([]);
  };

  return (
    <div className="flow-page">
      <FlowTopbar
        onHome={onGoHome}
        action={
          <>
            <div className="avatar" />
            <div className="user-name">
              <b>{getUserDisplayName("member")}</b>
              <small>{USER.team}</small>
            </div>
          </>
        }
      />
      <main className="flow-main">
        <section className="flow-hero">
          <div>
            <p>프로젝트 히스토리</p>
            <h1>프로젝트 목록</h1>
            <span>
              진행 중인 견적 검토와 완료된 이력을 프로젝트 단위로 관리해요.
            </span>
          </div>
          <button
            className="button action-primary"
            onClick={onCreate}
            type="button"
          >
            {EMPTY_PROJECTS.cta}
          </button>
        </section>

        <section className="flow-stats project-summary-stats">
          <article className="project-summary-stat project-summary-stat-total">
            <span>전체 프로젝트</span>
            <b>{projects.length}</b>
          </article>
          <article className="project-summary-stat">
            <span>{STATUS_IN_PROGRESS}</span>
            <b className="blue-text">{activeCount}</b>
          </article>
          <article className="project-summary-stat">
            <span>{STATUS_IN_REVIEW}</span>
            <b className="orange-text">{reviewCount}</b>
          </article>
          <article className="project-summary-stat">
            <span>{STATUS_APPROVAL_REQUEST}</span>
            <b className="approval-text">{approvalRequestCount}</b>
          </article>
          <article className="project-summary-stat">
            <span>{STATUS_DONE}</span>
            <b className="green-text">{completedCount}</b>
          </article>
        </section>

        {loadError && (
          <div className="empty-project-result" role="alert">
            <p>{loadError}</p>
            {onReloadProjects && (
              <button
                className="button action-secondary"
                onClick={() => onReloadProjects()}
                type="button"
              >
                다시 불러오기
              </button>
            )}
          </div>
        )}

        <section className="project-tools-wrap">
          <section className="project-tools">
            <input
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="프로젝트명 또는 ID 검색"
              value={searchTerm}
            />
            {filterOptions.map((filter) => (
              <button
                className={`chip ${activeFilter === filter ? "active" : ""}`}
                key={filter}
                onClick={() => setActiveFilter(filter)}
                type="button"
              >
                {filter}
              </button>
            ))}
            {!manageMode && (
              <button
                className="chip destructive-manage-chip"
                disabled={projects.length === 0}
                onClick={enterManageMode}
                type="button"
              >
                삭제
              </button>
            )}
            {manageMode && (
              <>
                <button
                  className={`chip ${allVisibleSelected ? "active" : ""}`}
                  disabled={visibleProjectIds.length === 0}
                  onClick={toggleSelectAll}
                  type="button"
                >
                  {allVisibleSelected ? "전체 해제" : "전체 선택"}
                </button>
                <button
                  className="chip danger-chip"
                  disabled={selectedIds.length === 0}
                  onClick={requestDeleteSelected}
                  type="button"
                >
                  {selectedIds.length}개 삭제
                </button>
                <button
                  className="chip neutral-chip"
                  onClick={cancelManageMode}
                  type="button"
                >
                  취소
                </button>
              </>
            )}
          </section>
          {manageMode && (
            <p className="project-manage-hint">삭제할 항목을 선택하세요.</p>
          )}
        </section>

        <section
          aria-busy={isLoading}
          aria-live="polite"
          className="project-card-grid"
        >
          {isLoading ? (
            <ProjectListSkeleton />
          ) : (
            filteredProjects.map((project) => {
              const isSelected = selectedIds.includes(project.id);
              const statusLabel = getProjectCardStatusLabel(project);
              const statusTone = getProjectCardStatusTone(project);

              return (
              <article
                aria-pressed={manageMode ? isSelected : undefined}
                className={`history-card ${manageMode ? "manage-mode" : ""} ${
                  isSelected ? "selected" : ""
                }`}
                key={project.id}
                onClick={
                  manageMode ? () => toggleSelected(project.id) : undefined
                }
                onKeyDown={
                  manageMode
                    ? (event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          toggleSelected(project.id);
                        }
                      }
                    : undefined
                }
                role={manageMode ? "button" : undefined}
                tabIndex={manageMode ? 0 : undefined}
              >
                <div className="history-card-top">
                  <div className="history-card-title-row">
                    {manageMode && (
                      <label
                        className="project-select-check"
                        onClick={(event) => event.stopPropagation()}
                      >
                        <input
                          checked={isSelected}
                          onChange={() => toggleSelected(project.id)}
                          type="checkbox"
                        />
                        <span className="sr-only">{project.name} 선택</span>
                      </label>
                    )}
                    <span className="history-card-id">{project.id}</span>
                  </div>
                  <div className="history-card-actions">
                    <Badge tone={statusTone}>{statusLabel}</Badge>
                    {!manageMode && (
                      <div className="project-menu-wrap">
                        <button
                          aria-label={`${project.name} 메뉴`}
                          className="project-more-button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setOpenMenuId(
                              openMenuId === project.id ? "" : project.id,
                            );
                          }}
                          type="button"
                        >
                          ...
                        </button>
                        {openMenuId === project.id && (
                          <div
                            className="project-menu"
                            onClick={(event) => event.stopPropagation()}
                          >
                            <button
                              onClick={() => {
                                setOpenMenuId("");
                                onEditProject(project);
                              }}
                              type="button"
                            >
                              수정
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <button
                  className="history-card-main"
                  onClick={() => {
                    if (!manageMode) {
                      onOpenDashboard(project.id);
                    }
                  }}
                  type="button"
                >
                  <h2>{readable(project.name, "이름 없는 프로젝트")}</h2>
                  <p>{readable(project.desc, "요구사항을 정리 중입니다.")}</p>
                </button>
                <div className="history-meta">
                  {project.meta.map((item) => (
                    <Badge tone="gray" key={item}>
                      {readable(item, "미정")}
                    </Badge>
                  ))}
                </div>
              </article>
              );
            })
          )}
          {!isLoading && filteredProjects.length === 0 && !loadError && (
            <div className="empty-project-result">
              <p>{EMPTY_PROJECTS.message}</p>
              <span>{EMPTY_PROJECTS.hint}</span>
              <button
                className="button action-primary"
                onClick={onCreate}
                type="button"
              >
                {EMPTY_PROJECTS.cta}
              </button>
            </div>
          )}
        </section>
      </main>

      {deleteConfirmOpen && (
        <div className="confirm-modal-layer" role="presentation">
          <button
            aria-label="삭제 확인 닫기"
            className="confirm-modal-backdrop"
            onClick={() => setDeleteConfirmOpen(false)}
            type="button"
          />
          <div
            aria-describedby="delete-projects-description"
            aria-labelledby="delete-projects-title"
            aria-modal="true"
            className="confirm-modal"
            role="dialog"
          >
            <div className="confirm-modal-header">
              <p>삭제 확인</p>
              <h2 id="delete-projects-title">
                선택한 {selectedIds.length}개 프로젝트를 삭제할까요?
              </h2>
            </div>
            <p
              className="confirm-modal-description"
              id="delete-projects-description"
            >
              삭제 후에는 되돌릴 수 없습니다.
            </p>
            <div className="confirm-modal-actions">
              <button
                className="button"
                onClick={() => setDeleteConfirmOpen(false)}
                type="button"
              >
                취소
              </button>
              <button
                className="button action-danger"
                onClick={confirmDeleteSelected}
                type="button"
              >
                삭제
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function isApprovalRequestProject(project) {
  return (project.data?.workflowStatus ?? "") === WORKFLOW_APPROVAL_REQUEST;
}

function getWorkflowStatusBadgeLabel(workflowStatus) {
  if (workflowStatus === "컨펌 요청") return "결재 요청";
  if (workflowStatus === "확정 완료") return "승인 완료";
  if (workflowStatus === "completed" || workflowStatus === "완료") return "완료";
  return workflowStatus;
}

function isWorkflowStatusBadge(workflowStatus) {
  return (
    workflowStatus === "컨펌 요청" ||
    workflowStatus === "확정 완료" ||
    workflowStatus === "completed" ||
    workflowStatus === "완료"
  );
}

function getProjectCardStatusLabel(project) {
  const workflowStatus = project.data?.workflowStatus ?? "";
  if (isWorkflowStatusBadge(workflowStatus)) {
    return getWorkflowStatusBadgeLabel(workflowStatus);
  }
  return normalizeStatus(project.status);
}

function getProjectCardStatusTone(project) {
  const workflowStatus = project.data?.workflowStatus ?? "";
  if (workflowStatus === "컨펌 요청") return "purple";
  if (workflowStatus === "확정 완료") return "green";
  return project.statusTone;
}

function normalizeStatus(value) {
  if (value === STATUS_DONE || String(value).includes("완료")) {
    return STATUS_DONE;
  }
  if (String(value).includes("검토")) {
    return STATUS_IN_REVIEW;
  }
  if (String(value).includes("진행")) {
    return STATUS_IN_PROGRESS;
  }
  return readable(value, STATUS_IN_PROGRESS);
}

function readable(value, fallback) {
  const text = String(value ?? "").trim();
  if (!text || /[�]/.test(text) || /[?]{2,}/.test(text)) return fallback;
  return text;
}
