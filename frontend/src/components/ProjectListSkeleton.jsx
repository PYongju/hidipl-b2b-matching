const DEFAULT_SKELETON_COUNT = 3;

function ProjectListSkeletonCard() {
  return (
    <article className="history-card project-skeleton-card" aria-hidden="true">
      <div className="history-card-top">
        <div className="history-card-title-row">
          <span className="skeleton-bone skeleton-id" />
        </div>
        <div className="history-card-actions">
          <span className="skeleton-bone skeleton-badge" />
          <span className="skeleton-bone skeleton-menu" />
        </div>
      </div>
      <div className="project-skeleton-body">
        <span className="skeleton-bone skeleton-title" />
        <span className="skeleton-bone skeleton-desc" />
        <span className="skeleton-bone skeleton-desc skeleton-desc-short" />
      </div>
      <div className="history-meta">
        <span className="skeleton-bone skeleton-meta" />
        <span className="skeleton-bone skeleton-meta" />
        <span className="skeleton-bone skeleton-meta" />
      </div>
    </article>
  );
}

export default function ProjectListSkeleton({
  count = DEFAULT_SKELETON_COUNT,
}) {
  return Array.from({ length: count }, (_, index) => (
    <ProjectListSkeletonCard key={`project-skeleton-${index}`} />
  ));
}
