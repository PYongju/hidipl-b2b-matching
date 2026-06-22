export default function AutoSaveStatus({ status = "idle" }) {
  if (status === "idle") return null;

  const labelByStatus = {
    saving: "자동 저장 중이에요.",
    saved: "자동 저장됐어요.",
    error: "자동 저장에 실패했어요. 다시 시도해 주세요.",
  };

  return (
    <span className={`auto-save-indicator ${status}`}>
      {labelByStatus[status] ?? labelByStatus.saving}
    </span>
  );
}
