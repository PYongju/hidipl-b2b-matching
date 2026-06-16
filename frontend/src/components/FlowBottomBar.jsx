export default function FlowBottomBar({
  backLabel = "이전 단계",
  nextLabel,
  onBack,
  onNext,
  nextDisabled = false,
  statusMessage = "변경 사항이 없으면 자동 저장됩니다.",
}) {
  return (
    <footer className="flow-bottom-actions">
      <span className="flow-bottom-status">{statusMessage}</span>
      <div>
        <button className="button action-secondary" onClick={onBack} type="button">
          {backLabel}
        </button>
        <button
          className="button action-primary"
          disabled={nextDisabled}
          onClick={onNext}
          type="button"
        >
          {nextLabel}
        </button>
      </div>
    </footer>
  );
}
