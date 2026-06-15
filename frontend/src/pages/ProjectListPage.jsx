// 6/12 수정
import { useState, useEffect } from "react";
import Badge from "../components/Badge";
import FlowTopbar from "../components/FlowTopbar";
import { formatNumberInput } from "../utils/formatters";

const filterOptions = ["전체", "진행 중", "검토 중", "완료"];

export default function ProjectListPage({
  projects,
  loadError = "",
  onCreate,
  onCreateDraft,
  onOpenDashboard,
  onEditProject,
  onDeleteProjects,
  onReloadProjects,
  onGoHome,
}) {
  const [selectedIds, setSelectedIds] = useState([]);
  const [openMenuId, setOpenMenuId] = useState("");
  const [activeFilter, setActiveFilter] = useState("전체");
  const [searchTerm, setSearchTerm] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [draft, setDraft] = useState(() => getEmptyDraft());

  const completedCount = projects.filter(
    (project) => normalizeStatus(project.status) === "완료",
  ).length;
  const activeCount = projects.filter(
    (project) => normalizeStatus(project.status) === "진행 중",
  ).length;
  const reviewCount = projects.filter(
    (project) => normalizeStatus(project.status) === "검토 중",
  ).length;
  const filteredProjects = projects.filter((project) => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
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
  const canSubmitDraft = true;

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

  const openCreateDrawer = () => {
    const emptyDraft = getEmptyDraft();
    setDraft(emptyDraft);
    if (onCreateDraft) {
      onCreateDraft(emptyDraft, true);
    } else {
      onCreate?.();
    }
  };

  const closeCreateDrawer = () => {
    setDrawerOpen(false);
  };

  const updateDraft = (field, value) => {
    setDraft((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const submitDraft = (shouldContinue) => {
    if (onCreateDraft) {
      onCreateDraft(draft, shouldContinue);
    } else {
      onCreate?.();
    }
    setDrawerOpen(false);
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
              진행 중인 견적 검토와 완료된 선정 이력을 프로젝트 단위로
              관리합니다.
            </span>
          </div>
          <button
            className="button action-primary"
            onClick={openCreateDrawer}
            type="button"
          >
            + 신규 검토 건 생성
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
            <article className="history-card" key={project.id}>
              <div className="history-card-top">
                <label className="project-select-check">
                  <input
                    checked={selectedIds.includes(project.id)}
                    onChange={() => toggleSelected(project.id)}
                    type="checkbox"
                  />
                  <span>{project.id}</span>
                </label>
                <Badge tone={project.statusTone}>
                  {normalizeStatus(project.status)}
                </Badge>
                <button
                  className="project-more-button"
                  onClick={() =>
                    setOpenMenuId(openMenuId === project.id ? "" : project.id)
                  }
                  type="button"
                  aria-label={`${project.name} 메뉴`}
                >
                  ...
                </button>
                {openMenuId === project.id && (
                  <div className="project-menu">
                    <button
                      onClick={() => onEditProject(project)}
                      type="button"
                    >
                      수정
                    </button>
                    <button
                      onClick={() => onDeleteProjects([project.id])}
                      type="button"
                    >
                      삭제
                    </button>
                  </div>
                )}
              </div>
              <button
                className="history-card-main"
                onClick={() => onOpenDashboard(project.id)}
                type="button"
              >
                <h2>{readable(project.name, "신규 검토 프로젝트")}</h2>
                <p>{readable(project.desc, "요구사항 정리 중")}</p>
              </button>
              <div className="history-meta">
                {project.meta.map((item) => (
                  <Badge tone="gray" key={item}>
                    {readable(item, "미정")}
                  </Badge>
                ))}
              </div>
            </article>
          ))}
          {filteredProjects.length === 0 && !loadError && (
            <div className="empty-project-result">
              조건에 맞는 프로젝트가 없습니다.
            </div>
          )}
        </section>
      </main>

      {drawerOpen && (
        <div className="quick-create-layer" role="presentation">
          <button
            className="quick-create-backdrop"
            onClick={closeCreateDrawer}
            type="button"
            aria-label="검토 건 생성 닫기"
          />
          <aside className="quick-create-drawer" aria-label="신규 검토 건 생성">
            <header className="quick-create-header">
              <div>
                <p>신규 프로젝트</p>
                <h2>검토 건 생성</h2>
              </div>
              <button
                className="drawer-close"
                onClick={closeCreateDrawer}
                type="button"
                aria-label="닫기"
              >
                ×
              </button>
            </header>

            <div className="quick-create-body">
              <section className="quick-create-section">
                <div className="quick-create-section-title">
                  <span>1</span>
                  <strong>필수 정보</strong>
                </div>
                <label>
                  <span>회사명 *</span>
                  <input
                    onChange={(event) =>
                      updateDraft("companyName", event.target.value)
                    }
                    placeholder="예: Microsoft"
                    value={draft.companyName}
                  />
                </label>
                <label>
                  <span>설치 위치/주소 *</span>
                  <input
                    onChange={(event) =>
                      updateDraft("location", event.target.value)
                    }
                    placeholder="예: 수원사업장 본관 로비"
                    value={draft.location}
                  />
                </label>
                <label>
                  <span>프로젝트 일정</span>
                  <input
                    onChange={(event) =>
                      updateDraft("projectDate", event.target.value)
                    }
                    type="date"
                    value={draft.projectDate}
                  />
                </label>
                <label>
                  <span>활용 용도/디스플레이 요구 *</span>
                  <textarea
                    onChange={(event) =>
                      updateDraft("usage", event.target.value)
                    }
                    placeholder="활용 용도, 설치 환경, 화면 크기, 운영 조건 등을 간단히 적어주세요."
                    value={draft.usage}
                  />
                </label>
                <label>
                  <span>현재 단계</span>
                  <select
                    onChange={(event) =>
                      updateDraft("currentStage", event.target.value)
                    }
                    value={draft.currentStage}
                  >
                    <option>요구사항</option>
                    <option>파트너 매칭 필요</option>
                    <option>견적 수신중</option>
                    <option>비교 검토중</option>
                  </select>
                </label>
              </section>

              <section className="quick-create-section">
                <div className="quick-create-section-title">
                  <span>2</span>
                  <strong>추가 설정</strong>
                </div>
                <label>
                  <span>발주처 유형</span>
                  <select
                    onChange={(event) =>
                      updateDraft("clientType", event.target.value)
                    }
                    value={draft.clientType}
                  >
                    <option>기업</option>
                    <option>공공기관</option>
                    <option>병원/학교</option>
                    <option>리테일/상업공간</option>
                  </select>
                </label>
                <label>
                  <span>솔루션</span>
                  <select
                    onChange={(event) =>
                      updateDraft("category", event.target.value)
                    }
                    value={draft.category}
                  >
                    <option>디스플레이</option>
                    <option>사이니지</option>
                    <option>키오스크</option>
                    <option>화상회의/회의실</option>
                    <option>기타</option>
                  </select>
                </label>
                <label>
                  <span>예산 범위</span>
                  <input
                    inputMode="numeric"
                    onChange={(event) =>
                      updateDraft(
                        "budgetAmount",
                        formatNumberInput(event.target.value),
                      )
                    }
                    placeholder="예: 120,000,000"
                    value={draft.budgetAmount}
                  />
                </label>
                <div className="quick-create-field">
                  <span>우선 검토 프리셋</span>
                  <div className="quick-preset-grid">
                    {["균형 추천", "최저가 우선", "납기 우선", "A/S 우선"].map(
                      (preset) => (
                        <button
                          className={
                            draft.reviewPreset === preset
                              ? "quick-preset active"
                              : "quick-preset"
                          }
                          key={preset}
                          onClick={() => updateDraft("reviewPreset", preset)}
                          type="button"
                        >
                          {preset}
                        </button>
                      ),
                    )}
                  </div>
                </div>
              </section>
            </div>

            <footer className="quick-create-footer">
              <button
                className="button"
                onClick={closeCreateDrawer}
                type="button"
              >
                취소
              </button>
              <button
                className="button"
                disabled={!canSubmitDraft}
                onClick={() => submitDraft(false)}
                type="button"
              >
                임시 저장
              </button>
              <button
                className="button action-primary"
                disabled={!canSubmitDraft}
                onClick={() => submitDraft(true)}
                type="button"
              >
                생성하고 계속
              </button>
            </footer>
          </aside>
        </div>
      )}
    </div>
  );
}

function getEmptyDraft() {
  return {
    companyName: "",
    location: "",
    projectName: "",
    projectDate: "",
    usage: "",
    currentStage: "요구사항",
    clientType: "기업",
    category: "디스플레이",
    budgetAmount: "",
    reviewPreset: "균형 추천",
  };
}

function normalizeStatus(value) {
  if (value === "완료" || String(value).includes("완료")) return "완료";
  if (String(value).includes("검토")) return "검토 중";
  if (String(value).includes("진행")) return "진행 중";
  return readable(value, "진행 중");
}

function readable(value, fallback) {
  const text = String(value ?? "").trim();
  if (!text || /[�]/.test(text) || /[?]{2,}/.test(text)) return fallback;
  return text;
}
