export default function BrandHomeButton({ onClick }) {
  const content = (
    <>
      <div className="brand-mark" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </div>
      <div className="brand-title">견적 검토 쿼파일럿</div>
    </>
  );

  if (!onClick) {
    return <div className="brand-home">{content}</div>;
  }

  return (
    <button
      aria-label="프로젝트 목록으로 이동"
      className="brand-home"
      onClick={onClick}
      type="button"
    >
      {content}
    </button>
  );
}
