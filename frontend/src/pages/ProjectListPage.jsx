import { useMemo, useState } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import { EMPTY_PROJECTS } from "../constants/uiText";

const FILTER_OPTIONS = ["전체", "진행 중", "검토 중", "완료"];

export default function ProjectListPage({
  projects,
  loadError = "",
  onCreate,
  onOpenDashboard,
  onDeleteProjects,
  onReloadProjects,
  onGoHome,
}) {
  const [selectedIds, setSelectedIds] = useState([]);
  const [managementMode, setManagementMode] = useState(false);
  const [activeFilter, setActiveFilter] = useState("전체");
  const [searchTerm, setSearchTerm] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);

  const completedCount = projects.filter(
    (project) => normalizeStatus(project.status) === "완료",
  ).length;
  const activeCount = projects.filter(
    (project) => normalizeStatus(project.status) === "진행 중",
  ).length;
  const reviewCount = projects.filter(
    (project) => normalizeStatus(project.status) === "검토 중",
  ).length;

  const filteredProjects = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    return projects.filter((project) => {
      const projectId = String(project.id ?? "");
      const projectName = String(project.name ?? "");
      const matchesSearch =
        !normalizedSearch ||
        projectId.toLowerCase().includes(normalizedSearch) ||
        projectName.toLowerCase().includes(normalizedSearch);

      if (!matchesSearch) return false;
      if (activeFilter === "전체") return true;
      return normalizeStatus(project.status) === activeFilter;
    });
  }, [activeFilter, projects, searchTerm]);

  const selectedCount = selectedIds.length;
  const visibleProjectIds = filteredProjects.map((project) => project.id);
  const allVisibleSelected =
    visibleProjectIds.length > 0 &&
    visibleProjectIds.every((projectId) => selectedIds.includes(projectId));

  const openCreatePage = () => {
    onCreate?.();
  };

  const enterManagementMode = () => {
    setManagementMode(true);
    setSelectedIds([]);
  };

  const exitManagementMode = () => {
    setManagementMode(false);
    setSelectedIds([]);
    setDeleteTarget(null);
  };

  const toggleSelected = (projectId) => {
    setSelectedIds((current) =>
      current.includes(projectId)
        ? current.filter((id) => id !== projectId)
        : [...current, projectId],
    );
  };

  const toggleSelectAllVisible = () => {
    if (allVisibleSelected) {
      setSelectedIds((current) =>
        current.filter((id) => !visibleProjectIds.includes(id)),
      );
      return;
    }

    setSelectedIds((current) => {
      const next = new Set(current);
      visibleProjectIds.forEach((projectId) => next.add(projectId));
      return Array.from(next);
    });
  };

  const handleCardClick = (projectId) => {
    if (managementMode) {
      toggleSelected(projectId);
      return;
    }

    onOpenDashboard(projectId);
  };

  const requestDelete = () => {
    if (selectedCount === 0) return;

    setDeleteTarget({
      count: selectedCount,
      ids: selectedIds,
    });
  };

  const confirmDelete = () => {
    if (!deleteTarget) return;

    onDeleteProjects(deleteTarget.ids);
    setDeleteTarget(null);
    setSelectedIds([]);
    setManagementMode(false);
  };

  return (
    <div className="flow-page">
      <FlowTopbar
        onHome={onGoHome}
        action={
          <>
            <div className="avatar" />
            <div className="user-name">
              <b>김담당자</b>
              <small>구매검토팀</small>
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
              진행 중인 견적 검토와 완료된 선정 이력을 프로젝트 단위로 관리해요.
            </span>
          </div>
          <button
            className="button action-primary"
            onClick={openCreatePage}
            type="button"
          >
            {EMPTY_PROJECTS.cta}
          </button>
        </section>

        <section className="flow-stats">
          <article>
            <b>{projects.length}</b>
            <span>전체 프로젝트</span>
          </article>
          <article>
            <b className="blue-text">{activeCount}</b>
            <span>진행 중</span>
          </article>
          <article>
            <b className="orange-text">{reviewCount}</b>
            <span>검토 중</span>
          </article>
          <article>
            <b className="green-text">{completedCount}</b>
            <span>완료</span>
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

        <section className={`project-tools${managementMode ? " management-mode" : ""}`}>
          <input
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="프로젝트명 또는 ID 검색"
            value={searchTerm}
          />

          {FILTER_OPTIONS.map((filter) => (
            <button
              className={`chip ${activeFilter === filter ? "active" : ""}`}
              key={filter}
              onClick={() => setActiveFilter(filter)}
              type="button"
            >
              {filter}
            </button>
          ))}

          {!managementMode ? (
            <button
              className="chip danger-chip"
              disabled={projects.length === 0}
              onClick={enterManagementMode}
              type="button"
            >
              관리
            </button>
          ) : (
            <>
              <button
                className="chip"
                disabled={filteredProjects.length === 0}
                onClick={toggleSelectAllVisible}
                type="button"
              >
                {allVisibleSelected ? "전체 선택 해제" : "전체 선택"}
              </button>
              <button
                className="chip danger-chip"
                disabled={selectedCount === 0}
                onClick={requestDelete}
                type="button"
              >
                {selectedCount}개 삭제
              </button>
              <button className="chip" onClick={exitManagementMode} type="button">
                취소
              </button>
            </>
          )}
        </section>

        {managementMode && (
          <div className="project-selection-guide" role="status">
            <strong>삭제할 항목을 선택하세요.</strong>
          </div>
        )}

        <section className="project-card-grid">
          {filteredProjects.map((project) => {
            const isSelected = selectedIds.includes(project.id);

            return (
              <article
                className={`history-card ${managementMode ? "selection-mode" : ""} ${isSelected ? "selected" : ""}`}
                key={project.id}
                onClick={() => handleCardClick(project.id)}
              >
                <div className="history-card-top">
                  {managementMode ? (
                    <label
                      className="project-select-check"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <input
                        checked={isSelected}
                        onChange={() => toggleSelected(project.id)}
                        type="checkbox"
                      />
                      <span>{project.id}</span>
                    </label>
                  ) : (
                    <span className="project-card-id">{project.id}</span>
                  )}
                  <Badge tone={project.statusTone}>
                    {normalizeStatus(project.status)}
                  </Badge>
                </div>

                <button
                  className="history-card-main"
                  onClick={(event) => {
                    event.stopPropagation();
                    handleCardClick(project.id);
                  }}
                  type="button"
                >
                  <h2>{readable(project.name, "미입력 프로젝트")}</h2>
                  <p>{readable(project.desc, "요구사항")}</p>
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
          })}

          {filteredProjects.length === 0 && !loadError && (
            <div className="empty-project-result">
              <p>{EMPTY_PROJECTS.message}</p>
              <span>{EMPTY_PROJECTS.hint}</span>
              <button
                className="button action-primary"
                onClick={openCreatePage}
                type="button"
              >
                {EMPTY_PROJECTS.cta}
              </button>
            </div>
          )}
        </section>
      </main>

      {deleteTarget && (
        <div className="confirm-delete-backdrop" role="presentation">
          <button
            aria-label="삭제 확인 닫기"
            className="confirm-delete-dismiss"
            onClick={() => setDeleteTarget(null)}
            type="button"
          />
          <section
            aria-labelledby="confirm-delete-title"
            aria-modal="true"
            className="confirm-delete-modal"
            role="dialog"
          >
            <p>삭제 확인</p>
            <h2 id="confirm-delete-title">
              선택한 {deleteTarget.count}개 프로젝트를 삭제할까요?
            </h2>
            <span>삭제 후에는 되돌릴 수 없습니다.</span>
            <div className="confirm-delete-actions">
              <button
                className="button"
                onClick={() => setDeleteTarget(null)}
                type="button"
              >
                취소
              </button>
              <button
                className="button action-danger"
                onClick={confirmDelete}
                type="button"
              >
                삭제
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function normalizeStatus(value) {
  const text = String(value ?? "");
  if (text.includes("완료")) return "완료";
  if (text.includes("검토")) return "검토 중";
  if (text.includes("진행")) return "진행 중";
  return readable(value, "진행 중");
}

function readable(value, fallback) {
  const text = String(value ?? "").trim();
  if (!text || /[?]{2,}/.test(text)) return fallback;
  return text;
}
