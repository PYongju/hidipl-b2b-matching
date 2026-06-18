export default function ProjectDetailHeader({
  projectName = "새 프로젝트",
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
        <div>
          <p>프로젝트 상세</p>
          <h1>{projectName}</h1>
        </div>
      </div>
    </section>
  );
}
