import { useCallback, useEffect, useRef, useState } from "react";

const IDLE_MESSAGE = "변경 사항이 없으면 자동 저장됩니다.";

export default function useAutoSaveStatus() {
  const [statusMessage, setStatusMessage] = useState(IDLE_MESSAGE);
  const timerRef = useRef(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => clearTimer, [clearTimer]);

  const setIdle = useCallback(() => {
    clearTimer();
    setStatusMessage(IDLE_MESSAGE);
  }, [clearTimer]);

  const startSaving = useCallback(() => {
    clearTimer();
    setStatusMessage("자동 저장 중입니다.");
  }, [clearTimer]);

  const markSaved = useCallback(() => {
    clearTimer();
    setStatusMessage("저장되었습니다.");
    timerRef.current = setTimeout(() => {
      setStatusMessage(IDLE_MESSAGE);
      timerRef.current = null;
    }, 1800);
  }, [clearTimer]);

  const notifyAutoSave = useCallback(
    (delay = 700) => {
      startSaving();
      clearTimer();
      timerRef.current = setTimeout(() => {
        setStatusMessage("저장되었습니다.");
        timerRef.current = setTimeout(() => {
          setStatusMessage(IDLE_MESSAGE);
          timerRef.current = null;
        }, 1800);
      }, delay);
    },
    [clearTimer, startSaving],
  );

  return {
    statusMessage,
    startSaving,
    markSaved,
    notifyAutoSave,
    setIdle,
  };
}
