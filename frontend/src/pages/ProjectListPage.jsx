import { useState } from 'react';
import Badge from '../components/Badge';
import FlowTopbar from '../components/FlowTopbar';

export default function ProjectListPage({ projects, onCreate, onOpenDashboard, onEditProject, onDeleteProjects }) {
  const [selectedIds, setSelectedIds] = useState([]);
  const [openMenuId, setOpenMenuId] = useState("");
  const [activeFilter, setActiveFilter] = useState("전체");
  const [searchTerm, setSearchTerm] = useState("");
  const completedCount = projects.filter((project) => project.status === "완료").length;
  const activeCount = projects.filter((project) => project.status === "진행 중").length;
  const reviewCount = projects.filter((project) => project.status === "검토 중").length;
  const filteredProjects = projects.filter((project) => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    const matchesSearch =
      !normalizedSearch ||
      project.id.toLowerCase().includes(normalizedSearch) ||
      project.name.toLowerCase().includes(normalizedSearch);

    if (!matchesSearch) return false;
    if (activeFilter === "전체") return true;
    return project.status === activeFilter;
  });
  const filterOptions = ["전체", "진행 중", "검토 중", "완료"];

  const toggleSelected = (projectId) => {
    setSelectedIds((current) =>
      current.includes(projectId)
        ? current.filter((id) => id !== projectId)
        : [...current, projectId],
    );
  };

  const deleteSelected = () => {
    onDeleteProjects(selectedIds);
    setSelectedIds([]);
  };

  return (
    <div className="flow-page">
      <FlowTopbar
        action={
          <>
            <div className="bell">
              알림<span>3</span>
            </div>
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
            <span>진행 중인 견적 검토와 완료된 선정 이력을 프로젝트 단위로 관리합니다.</span>
          </div>
          <button className="button action-primary" onClick={onCreate} type="button">
            + 새 프로젝트 생성
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
          <button
            className="chip danger-chip"
            disabled={selectedIds.length === 0}
            onClick={deleteSelected}
            type="button"
          >
            선택 삭제
          </button>
          <button
            className="chip danger-chip"
            disabled={projects.length === 0}
            onClick={() => {
              onDeleteProjects(projects.map((project) => project.id));
              setSelectedIds([]);
            }}
            type="button"
          >
            전체 삭제
          </button>
        </section>

        <section className="project-card-grid">
          {filteredProjects.map((project) => (
            <article
              className="history-card"
              key={project.id}
            >
              <div className="history-card-top">
                <label className="project-select-check">
                  <input
                    checked={selectedIds.includes(project.id)}
                    onChange={() => toggleSelected(project.id)}
                    type="checkbox"
                  />
                  <span>{project.id}</span>
                </label>
                <Badge tone={project.statusTone}>{project.status}</Badge>
                <button
                  className="project-more-button"
                  onClick={() => setOpenMenuId(openMenuId === project.id ? "" : project.id)}
                  type="button"
                  aria-label={`${project.name} 메뉴`}
                >
                  ⋯
                </button>
                {openMenuId === project.id && (
                  <div className="project-menu">
                    <button onClick={() => onEditProject(project)} type="button">수정</button>
                    <button onClick={() => onDeleteProjects([project.id])} type="button">삭제</button>
                  </div>
                )}
              </div>
              <button className="history-card-main" onClick={() => onOpenDashboard(project.id)} type="button">
                <h2>{project.name}</h2>
                <p>{project.desc}</p>
              </button>
              <div className="history-meta">
                {project.meta.map((item) => (
                  <Badge tone="gray" key={item}>{item}</Badge>
                ))}
              </div>
            </article>
          ))}
          {filteredProjects.length === 0 && (
            <div className="empty-project-result">
              조건에 맞는 프로젝트가 없습니다.
            </div>
          )}

        </section>
      </main>
    </div>
  );
}
