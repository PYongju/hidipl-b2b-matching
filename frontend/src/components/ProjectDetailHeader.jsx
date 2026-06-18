export default function ProjectDetailHeader({
  projectName = "새 프로젝트",
  infoSummary,
  onBack,
  backLabel = "목록으로",
}) {
  return (
    <section className="requirements-header">
      <div>
        <button
          className="partner-back"
          onClick={onBack}
          type="button"
          aria-label={backLabel}
        >
          ‹
        </button>
        <div className="requirements-header-body">
          <p>프로젝트 상세</p>
          <h1 className="project-title-with-meta">
            <span className="project-title-name">{projectName}</span>
            {infoSummary ? (
              <>
                <span aria-hidden="true" className="project-title-inline-divider">
                  {" "}
                  ·{" "}
                </span>
                <span className="project-title-inline-meta">{infoSummary}</span>
              </>
            ) : null}
          </h1>
        </div>
      </div>
    </section>
  );
}
