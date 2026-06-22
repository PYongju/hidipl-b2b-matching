import { useEffect, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import ProjectListSkeleton from "../components/ProjectListSkeleton";
import { EMPTY_PROJECTS, getUserDisplayName, USER } from "../constants/uiText";

const FILTER_ALL = "전체";
const STATUS_IN_PROGRESS = "진행 중";
const STATUS_IN_REVIEW = "검토 중";
const STATUS_APPROVAL_REQUEST = "결재 요청";
const STATUS_DONE = "확정 완료";
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
  const [isDeleteMode, setIsDeleteMode] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  useEffect(() => {
    setSelectedIds((current) =>
      current.filter((id) => projects.some((project) => project.id === id)),
    );
  }, [projects]);

  const completedCount = projects.filter(
    (project) => getProjectListFilterKey(project) === STATUS_DONE,
  ).length;
  const activeCount = projects.filter(
    (project) => normalizeStatus(project.status) === STATUS_IN_PROGRESS,
  ).length;
  const reviewCount = projects.filter(
    (project) => normalizeStatus(project.status) === STATUS_IN_REVIEW,
  ).length;
  const approvalRequestCount = projects.filter(isApprovalRequestProject).length;
  const filterCounts = {
    [FILTER_ALL]: projects.length,
    [STATUS_IN_PROGRESS]: activeCount,
    [STATUS_IN_REVIEW]: reviewCount,
    [STATUS_APPROVAL_REQUEST]: approvalRequestCount,
    [STATUS_DONE]: completedCount,
  };

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
    return getProjectListFilterKey(project) === activeFilter;
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

  const enterDeleteMode = () => {
    setIsDeleteMode(true);
    setOpenMenuId("");
  };

  const cancelDeleteMode = () => {
    setIsDeleteMode(false);
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
    setIsDeleteMode(false);
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
        <header className="project-list-header">
          <p>프로젝트 히스토리</p>
          <div className="project-list-header-title-row">
            <h1>프로젝트 목록</h1>
            <button
              className="button action-primary"
              onClick={onCreate}
              type="button"
            >
              {EMPTY_PROJECTS.cta}
            </button>
          </div>
          <span className="project-list-header-desc">
            진행 중인 견적 검토와 완료된 이력을 프로젝트 단위로 관리해요.
          </span>
        </header>

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

        <section className="filter-block">
          <div className="filter-block-row">
            <div className="filter-block-tabs" role="tablist">
              {filterOptions.map((filter) => (
                <button
                  aria-selected={activeFilter === filter}
                  className={`filter-tab ${getFilterTabToneClass(filter)} ${
                    activeFilter === filter ? "active" : ""
                  }`}
                  key={filter}
                  onClick={() => setActiveFilter(filter)}
                  role="tab"
                  type="button"
                >
                  <span className="filter-tab-label">{filter}</span>
                  <span className="filter-tab-count">{filterCounts[filter]}</span>
                </button>
              ))}
            </div>
            <div className="filter-block-tools">
              <div className="filter-block-search">
                <i
                  aria-hidden="true"
                  className="fa-solid fa-magnifying-glass filter-block-search-icon"
                />
                <input
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="프로젝트명 또는 ID 검색"
                  type="search"
                  value={searchTerm}
                />
              </div>
              {!isDeleteMode ? (
                <button
                  className="filter-btn-text filter-btn-text-delete"
                  disabled={projects.length === 0}
                  onClick={enterDeleteMode}
                  type="button"
                >
                  삭제
                </button>
              ) : (
                <>
                  <button
                    className={`filter-btn filter-btn-outline ${allVisibleSelected ? "active" : ""}`}
                    disabled={visibleProjectIds.length === 0}
                    onClick={toggleSelectAll}
                    type="button"
                  >
                    {allVisibleSelected ? "전체 해제" : "전체 선택"}
                  </button>
                  <button
                    className="filter-btn filter-btn-danger-fill"
                    disabled={selectedIds.length === 0}
                    onClick={requestDeleteSelected}
                    type="button"
                  >
                    {selectedIds.length}개 삭제
                  </button>
                  <button
                    className="filter-btn filter-btn-outline"
                    onClick={cancelDeleteMode}
                    type="button"
                  >
                    취소
                  </button>
                </>
              )}
            </div>
          </div>
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
                aria-pressed={isDeleteMode ? isSelected : undefined}
                className={`history-card ${isDeleteMode ? "manage-mode" : ""} ${
                  isSelected ? "selected" : ""
                }`}
                key={project.id}
                onClick={
                  isDeleteMode ? () => toggleSelected(project.id) : undefined
                }
                onKeyDown={
                  isDeleteMode
                    ? (event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          toggleSelected(project.id);
                        }
                      }
                    : undefined
                }
                role={isDeleteMode ? "button" : undefined}
                tabIndex={isDeleteMode ? 0 : undefined}
              >
                <div className="history-card-top">
                  {isDeleteMode && (
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
                  <Badge tone={statusTone}>{statusLabel}</Badge>
                  <div className="history-card-top-right">
                    <span className="history-card-id">{project.id}</span>
                    {!isDeleteMode && (
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
                          <i
                            aria-hidden="true"
                            className="fa-solid fa-ellipsis-vertical"
                          />
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
                    if (!isDeleteMode) {
                      onOpenDashboard(project.id);
                    }
                  }}
                  type="button"
                >
                  <h2>{readable(project.name, "이름 없는 프로젝트")}</h2>
                  <p>{readable(project.desc, "요구사항을 정리 중이에요.")}</p>
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
              <p>
                {projects.length === 0
                  ? EMPTY_PROJECTS.emptyMessage
                  : EMPTY_PROJECTS.filterEmptyMessage}
              </p>
              <span>
                {projects.length === 0
                  ? EMPTY_PROJECTS.emptyHint
                  : EMPTY_PROJECTS.filterEmptyHint}
              </span>
            </div>
          )}
        </section>
      </main>

      {deleteConfirmOpen && (
        <div className="confirm-layer" role="presentation">
          <div
            aria-describedby="delete-projects-description"
            aria-labelledby="delete-projects-title"
            aria-modal="true"
            className="confirm-dialog"
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
              삭제 후에는 되돌릴 수 없어요.
            </p>
            <div className="confirm-actions">
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

function getFilterTabToneClass(filter) {
  if (filter === STATUS_IN_PROGRESS) return "filter-tab-tone-blue";
  if (filter === STATUS_IN_REVIEW) return "filter-tab-tone-orange";
  if (filter === STATUS_APPROVAL_REQUEST) return "filter-tab-tone-rose";
  if (filter === STATUS_DONE) return "filter-tab-tone-green";
  return "filter-tab-tone-all";
}

function isDoneWorkflowStatus(workflowStatus) {
  return (
    workflowStatus === "확정 완료" ||
    workflowStatus === "승인 완료" ||
    workflowStatus === "완료" ||
    workflowStatus === "completed"
  );
}

function getProjectListFilterKey(project) {
  const workflowStatus = project.data?.workflowStatus ?? "";
  if (workflowStatus === WORKFLOW_APPROVAL_REQUEST) {
    return STATUS_APPROVAL_REQUEST;
  }
  if (isDoneWorkflowStatus(workflowStatus)) {
    return STATUS_DONE;
  }
  return normalizeStatus(project.status);
}

function getWorkflowStatusBadgeLabel(workflowStatus) {
  if (workflowStatus === "컨펌 요청") return "결재 요청";
  if (isDoneWorkflowStatus(workflowStatus)) return STATUS_DONE;
  return workflowStatus;
}

function isWorkflowStatusBadge(workflowStatus) {
  return (
    workflowStatus === "컨펌 요청" || isDoneWorkflowStatus(workflowStatus)
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
  if (workflowStatus === "컨펌 요청") return "rose";
  if (workflowStatus === "확정 완료") return "green";
  return project.statusTone;
}

function normalizeStatus(value) {
  const text = String(value ?? "").trim();
  if (isDoneWorkflowStatus(text) || text === STATUS_DONE) {
    return STATUS_DONE;
  }
  if (text.includes("검토")) {
    return STATUS_IN_REVIEW;
  }
  if (text.includes("진행")) {
    return STATUS_IN_PROGRESS;
  }
  return readable(value, STATUS_IN_PROGRESS);
}

function readable(value, fallback) {
  const text = String(value ?? "").trim();
  if (!text || /[�]/.test(text) || /[?]{2,}/.test(text)) return fallback;
  return text;
}
