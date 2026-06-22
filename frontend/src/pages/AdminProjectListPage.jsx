import { useEffect, useMemo, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import { ApiError, confirmAdminProject } from "../api/apiClient";
import { getUserDisplayName, USER } from "../constants/uiText";

const FILTER_ALL = "전체";
const FILTER_APPROVAL_REQUEST = "결재 요청";
const WORKFLOW_APPROVAL_REQUEST = "컨펌 요청";
const ROWS_PER_PAGE = 10;

const filterOptions = [FILTER_ALL, FILTER_APPROVAL_REQUEST];

export default function AdminProjectListPage({
  projects,
  isLoading = false,
  loadError = "",
  onGoHome,
  onOpenProject,
  onReloadProjects,
}) {
  const [activeFilter, setActiveFilter] = useState(FILTER_ALL);
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(1);
  const [confirmingProjectId, setConfirmingProjectId] = useState("");

  useEffect(() => {
    setPage(1);
  }, [activeFilter, searchTerm, projects.length]);

  const filteredProjects = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    return projects.filter((project) => {
      const projectId = String(project.id ?? "");
      const companyName = String(project.companyName ?? project.name ?? "");
      const matchesSearch =
        !normalizedSearch ||
        projectId.toLowerCase().includes(normalizedSearch) ||
        companyName.toLowerCase().includes(normalizedSearch);

      if (!matchesSearch) return false;
      if (activeFilter === FILTER_ALL) return true;
      return (project.workflowStatus ?? "") === WORKFLOW_APPROVAL_REQUEST;
    });
  }, [projects, searchTerm, activeFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredProjects.length / ROWS_PER_PAGE));
  const currentPage = Math.min(page, totalPages);
  const pageStart = (currentPage - 1) * ROWS_PER_PAGE;
  const pageEnd = Math.min(pageStart + ROWS_PER_PAGE, filteredProjects.length);
  const visibleProjects = filteredProjects.slice(pageStart, pageEnd);

  const handleFilterChange = async (filter) => {
    setActiveFilter(filter);
    if (!onReloadProjects) return;
    await onReloadProjects({
      statusFilter: filter === FILTER_APPROVAL_REQUEST ? WORKFLOW_APPROVAL_REQUEST : null,
    });
  };

  const handleAdminConfirm = async (projectId) => {
    setConfirmingProjectId(projectId);
    try {
      await confirmAdminProject(projectId);
      if (onReloadProjects) {
        await onReloadProjects({
          statusFilter:
            activeFilter === FILTER_APPROVAL_REQUEST
              ? WORKFLOW_APPROVAL_REQUEST
              : null,
        });
      }
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 400) {
          window.alert("이미 처리된 요청이에요. 목록을 새로고침해 주세요.");
          if (onReloadProjects) {
            await onReloadProjects({
              statusFilter:
                activeFilter === FILTER_APPROVAL_REQUEST
                  ? WORKFLOW_APPROVAL_REQUEST
                  : null,
            });
          }
        } else if (error.status === 404) {
          window.alert("프로젝트를 찾을 수 없어요.");
          if (onReloadProjects) {
            await onReloadProjects({
              statusFilter:
                activeFilter === FILTER_APPROVAL_REQUEST
                  ? WORKFLOW_APPROVAL_REQUEST
                  : null,
            });
          }
        }
      } else {
        console.error("프로젝트 승인 실패:", error);
      }
    } finally {
      setConfirmingProjectId("");
    }
  };

  return (
    <div className="flow-page admin-project-page">
      <FlowTopbar
        onHome={onGoHome}
        action={
          <>
            <div className="avatar" />
            <div className="user-name">
              <b>{getUserDisplayName("admin")}</b>
              <small>{USER.team}</small>
            </div>
          </>
        }
      />
      <main className="flow-main">
        <section className="flow-hero admin-project-hero">
          <div>
            <p>관리자</p>
            <h1>프로젝트 승인</h1>
            <span>결재 요청된 프로젝트를 검토하고 승인해요.</span>
          </div>
        </section>

        {loadError && (
          <div className="empty-project-result" role="alert">
            <p>{loadError}</p>
            {onReloadProjects && (
              <button
                className="button action-secondary"
                onClick={() => onReloadProjects({ statusFilter: null })}
                type="button"
              >
                다시 불러오기
              </button>
            )}
          </div>
        )}

        <section className="admin-table-panel">
          <div className="admin-table-toolbar">
            <div className="admin-table-search">
              <i
                aria-hidden="true"
                className="fa-solid fa-magnifying-glass admin-table-search-icon"
              />
              <input
                aria-label="프로젝트 검색"
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="프로젝트 ID 또는 고객사 검색"
                type="search"
                value={searchTerm}
              />
            </div>
            <div className="admin-table-filters">
              {filterOptions.map((filter) => (
                <button
                  className={`chip ${activeFilter === filter ? "active" : ""}`}
                  key={filter}
                  onClick={() => {
                    void handleFilterChange(filter);
                  }}
                  type="button"
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>프로젝트 ID</th>
                  <th>고객사</th>
                  <th>진행 상태</th>
                  <th>승인 상태</th>
                  <th>위치</th>
                  <th>마감일</th>
                  <th>승인</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td className="admin-table-empty" colSpan={7}>
                      프로젝트 목록을 불러오는 중이에요.
                    </td>
                  </tr>
                ) : visibleProjects.length === 0 ? (
                  <tr>
                    <td className="admin-table-empty" colSpan={7}>
                      {loadError
                        ? "목록을 불러오지 못했어요."
                        : "조건에 맞는 프로젝트가 없어요."}
                    </td>
                  </tr>
                ) : (
                  visibleProjects.map((project) => {
                    const workflowStatus = project.workflowStatus ?? "";
                    const workflowBadge = getWorkflowBadge(workflowStatus);
                    const canApprove =
                      workflowStatus === WORKFLOW_APPROVAL_REQUEST;

                    return (
                      <tr
                        className="admin-table-row-clickable"
                        key={project.id}
                        onClick={() => {
                          void onOpenProject(project.id);
                        }}
                      >
                        <td>
                          <span className="admin-table-project-id">
                            {project.id}
                          </span>
                        </td>
                        <td>
                          <b className="admin-table-company-name">
                            {readable(project.companyName ?? project.name, "—")}
                          </b>
                        </td>
                        <td>
                          <span className="admin-table-status">
                            {getStatusLabel(project.status)}
                          </span>
                        </td>
                        <td>
                          {workflowBadge ? (
                            <Badge tone={workflowBadge.tone}>
                              {workflowBadge.label}
                            </Badge>
                          ) : (
                            <span className="admin-table-muted">—</span>
                          )}
                        </td>
                        <td>{readable(project.location, "—")}</td>
                        <td>{readable(project.deadline, "—")}</td>
                        <td
                          onClick={(event) => event.stopPropagation()}
                          onKeyDown={(event) => event.stopPropagation()}
                        >
                          <button
                            className="button button-small admin-approve-button"
                            disabled={
                              !canApprove || confirmingProjectId === project.id
                            }
                            onClick={() => {
                              void handleAdminConfirm(project.id);
                            }}
                            type="button"
                          >
                            승인
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {!isLoading && filteredProjects.length > 0 && (
            <div className="admin-table-footer">
              <span>
                {filteredProjects.length === 0
                  ? "0건"
                  : `${pageStart + 1}-${pageEnd} / ${filteredProjects.length}건`}
              </span>
              <div className="admin-table-pagination">
                <label className="admin-table-rows">
                  <span>페이지당</span>
                  <select disabled value={ROWS_PER_PAGE}>
                    <option value={ROWS_PER_PAGE}>{ROWS_PER_PAGE}</option>
                  </select>
                </label>
                <span>
                  {currentPage} / {totalPages}
                </span>
                <button
                  aria-label="이전 페이지"
                  className="button button-small"
                  disabled={currentPage <= 1}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                  type="button"
                >
                  <i aria-hidden="true" className="fa-solid fa-angle-left" />
                </button>
                <button
                  aria-label="다음 페이지"
                  className="button button-small"
                  disabled={currentPage >= totalPages}
                  onClick={() =>
                    setPage((value) => Math.min(totalPages, value + 1))
                  }
                  type="button"
                >
                  <i aria-hidden="true" className="fa-solid fa-angle-right" />
                </button>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

const STATUS_LABELS = {
  created: "요구사항 작성",
  partner_matching: "파트너 매칭 중",
  partner_matched: "파트너 선정 완료",
  quote_uploaded: "견적서 업로드 완료",
  matched: "견적 검토 중",
};

function getStatusLabel(status) {
  const value = String(status ?? "").trim();
  if (!value) return "—";
  return STATUS_LABELS[value] ?? value;
}

function getWorkflowBadge(workflowStatus) {
  const value = String(workflowStatus ?? "").trim();
  if (!value) {
    return { label: "진행 중", tone: "blue" };
  }
  if (value === "컨펌 요청") {
    return { label: "결재 요청", tone: "rose" };
  }
  if (
    value === "확정 완료" ||
    value === "승인 완료" ||
    value === "completed"
  ) {
    return { label: "확정 완료", tone: "green" };
  }
  return null;
}

function readable(value, fallback) {
  const text = String(value ?? "").trim();
  if (!text || /[]/.test(text) || /[?]{2,}/.test(text)) return fallback;
  return text;
}
