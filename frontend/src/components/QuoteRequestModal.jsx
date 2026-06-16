import { useEffect, useRef, useState } from "react";

/**
 * 견적 요청 문구를 보여주고, 카톡에 바로 붙여넣어 전달할 수 있게 복사하는 팝업.
 * 업체명([업체명])만 수정해서 공급사에 발송하면 된다.
 */
export default function QuoteRequestModal({ message, targetNames = [], onClose }) {
  const [copied, setCopied] = useState(false);
  const textRef = useRef(null);
  const copyTimer = useRef(null);

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
      // 클립보드 권한이 없으면 사용자가 직접 드래그해 복사할 수 있도록 텍스트를 선택해 준다.
      textRef.current?.select();
    }
  };

  return (
    <div className="quote-request-backdrop" onClick={onClose} role="presentation">
      <div
        className="quote-request-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="견적 요청 문구"
      >
        <div className="quote-request-header">
          <div>
            <p>카톡 견적 요청</p>
            <h2>이 문구를 복사해 공급사에 보내세요</h2>
          </div>
          <button
            className="quote-request-close"
            onClick={onClose}
            type="button"
            aria-label="닫기"
          >
            ×
          </button>
        </div>

        <textarea
          className="quote-request-text"
          ref={textRef}
          value={message}
          readOnly
          rows={Math.min(16, message.split("\n").length + 2)}
        />

        <p className="quote-request-guide">
          위 내용을 복사 붙여넣기 후 견적 요청을 발송하세요.
          <b> [업체명] 부분을 꼭 확인하세요.</b>
        </p>

        {targetNames.length > 0 && (
          <p className="quote-request-targets">
            발송 대상 {targetNames.length}곳: {targetNames.join(", ")}
          </p>
        )}

        <div className="quote-request-actions">
          <button className="button action-secondary" onClick={onClose} type="button">
            닫기
          </button>
          <button className="button button-blue" onClick={handleCopy} type="button">
            {copied ? "복사됨 ✓" : "복사"}
          </button>
        </div>

        {copied && <div className="quote-request-toast">클립보드에 복사했어요</div>}
      </div>
    </div>
  );
}
