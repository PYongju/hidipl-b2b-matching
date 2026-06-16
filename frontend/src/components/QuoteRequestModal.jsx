import { useEffect, useMemo, useRef, useState } from "react";

export default function QuoteRequestModal({
  buildMessage,
  drafts = {},
  onDraftChange,
  targets = [],
  onClose,
}) {
  const [copied, setCopied] = useState(false);
  const [selectedTargetId, setSelectedTargetId] = useState(targets[0]?.id ?? "");
  const [isEditing, setIsEditing] = useState(false);
  const textRef = useRef(null);
  const copyTimer = useRef(null);

  useEffect(() => {
    setSelectedTargetId(targets[0]?.id ?? "");
  }, [targets]);

  useEffect(() => {
    const handleKey = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      if (copyTimer.current) clearTimeout(copyTimer.current);
    };
  }, [onClose]);

  const selectedTarget =
    targets.find((target) => target.id === selectedTargetId) ?? targets[0] ?? null;
  const baseMessage = useMemo(
    () => buildMessage?.(selectedTarget?.name ?? "") ?? "",
    [buildMessage, selectedTarget?.name],
  );
  const message =
    drafts[selectedTarget?.id ?? ""] ??
    baseMessage;

  const handleEditStart = () => {
    setIsEditing(true);
    requestAnimationFrame(() => {
      textRef.current?.focus();
      const textLength = textRef.current?.value?.length ?? 0;
      textRef.current?.setSelectionRange?.(textLength, textLength);
    });
  };

  const handleMessageChange = (event) => {
    onDraftChange?.(selectedTarget?.id ?? "", event.target.value);
  };

  const handleCopy = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(message);
      } else {
        textRef.current?.select();
        document.execCommand("copy");
      }
      setCopied(true);
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      textRef.current?.select();
    }
  };

  return (
    <div className="quote-request-backdrop" onClick={onClose} role="presentation">
      <div
        aria-label="견적 요청 문구"
        aria-modal="true"
        className="quote-request-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="quote-request-header">
          <div>
            <p>견적 요청 메시지</p>
            <h2>발송할 메시지를 확인해 주세요</h2>
          </div>
          <button
            aria-label="닫기"
            className="quote-request-close"
            onClick={onClose}
            type="button"
          />
        </div>

        {targets.length > 0 && (
          <div className="quote-request-targets">
            {targets.map((target) => (
              <button
                className={
                  target.id === selectedTargetId
                    ? "quote-request-target-chip active"
                    : "quote-request-target-chip"
                }
                key={target.id}
                onClick={() => setSelectedTargetId(target.id)}
                type="button"
              >
                {target.name}
              </button>
            ))}
          </div>
        )}

        <textarea
          className="quote-request-text"
          onChange={handleMessageChange}
          ref={textRef}
          rows={Math.max(18, message.split("\n").length + 2)}
          value={message}
        />

        <p className="quote-request-guide">
          발송 대상을 누르면 인사말의 업체명이 자동으로 바뀝니다.
          <b> 복사 전에 선택된 업체명을 한 번만 확인해 주세요.</b>
        </p>

        <div className="quote-request-actions">
          <button
            className="button action-secondary"
            onClick={handleEditStart}
            type="button"
          >
            {isEditing ? "수정 중" : "수정"}
          </button>
          <button className="button button-blue" onClick={handleCopy} type="button">
            {copied ? "복사 완료" : "복사"}
          </button>
        </div>

        {copied && <div className="quote-request-toast">클립보드에 복사됐어요.</div>}
      </div>
    </div>
  );
}
