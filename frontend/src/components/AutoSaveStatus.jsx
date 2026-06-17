export default function AutoSaveStatus({ status = "idle" }) {
  if (status === "idle") return null;

  const labelByStatus = {
    saving: "자동 저장 중입니다.",
    saved: "자동 저장되었습니다.",
    error: "자동 저장에 실패했습니다.",
  };

  return (
    <span className={`auto-save-indicator ${status}`}>
      {labelByStatus[status] ?? labelByStatus.saving}
    </span>
  );
}
