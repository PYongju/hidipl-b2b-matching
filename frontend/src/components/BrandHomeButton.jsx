export default function BrandHomeButton({ onClick }) {
  const content = (
    <>
      <img
        alt=""
        aria-hidden="true"
        className="brand-mark"
        height={28}
        src="/quopilot-logo.png"
        width={28}
      />
      <div className="brand-title">QuoPilot</div>
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
