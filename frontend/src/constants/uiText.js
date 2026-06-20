// 화면에 노출되는 공통 UI 문구 모음 (UX Writing 가이드 v1.1 기준)
// 하드코딩 문구를 한곳으로 모아 비개발자도 문구만 수정할 수 있게 하고, 추후 i18n을 대비합니다.
// 신규/주요 문구부터 이 파일을 참조하도록 점진적으로 이관합니다. (가이드 §9-1 #16)

// 브랜드 (가이드 §4 — QuoPilot으로 통일, 한글 음차 미사용)
export const BRAND = {
  name: "QuoPilot",
  tagline: "구매 검토팀을 위한 AI 견적 비교 워크스페이스",
};

// 사용자 호칭 (가이드 §1 — 구매검토팀으로 통일)
export const USER = {
  name: "김과장",
  team: "구매검토팀",
};

export function getUserDisplayName(userRole) {
  return userRole === "admin" ? "김부장" : USER.name;
}

// 핵심 용어 (가이드 §4 — 한 개념엔 한 단어)
export const TERMS = {
  supplier: "공급사",
  project: "프로젝트",
};

// AI 비교 유의 문구 (가이드 §원칙2 — 책임 환기를 위해 "반드시"는 유지, 강압적 어조만 완화)
export const AI_COMPARE_NOTICE =
  "이 비교는 AI가 추출한 정보를 바탕으로 해요. 최종 선정 전에 주요 항목을 반드시 확인하고, 필요하면 공급사에 문의해 보세요.";

// AI 설명 폴백 안내 (가이드 §6 — "기본 요약" 표현 사용, 내부 용어 노출 금지)
export const AI_FALLBACK_NOTICE =
  "AI 설명을 일시적으로 만들지 못해, 기본 요약을 보여드려요.";

// 적합도 점수 정의 툴팁 (가이드 §6, #11 — 점수 단독 노출 시 앵커링 방지)
export const FIT_SCORE_TOOLTIP =
  "요구사항 대비 부합도(0~100)예요. 선정 기준이 아니라 참고 지표예요.";

// 견적서 내용 추출 실패 보조 안내 (가이드 §4 상태 단어 — 배지는 "수정 필요", 원인은 이 문구로)
export const PARSE_FAIL_NOTE =
  "견적서에서 값을 읽지 못했어요. 원본을 확인한 뒤 입력해 주세요.";

// 최종 선정 (가이드 §원칙4 — 되돌릴 수 없는 행위의 결과 안내)
export const FINAL_SELECTION = {
  dialogTitle: "최종 선정 확정",
  dialogMessage: "업체를 최종 선정 업체로 확정하시겠습니까?",
  toast: "최종 선정이 확정됐어요.",
  doneEmotion: "최종 선정을 마쳤어요. 수고하셨어요.",
  statusChanged: "프로젝트 상태가 승인 완료로 바뀌었어요.",
  noPermission: "최종 선정 확정 권한이 없어요.",
  noPermissionTitle: "권한 없음",
};

export const REVIEW_COMPLETE = {
  dialogTitle: "검토 완료",
  dialogMessage: "검토를 완료하고 결재를 요청할까요?",
  dialogResult: "완료하면 관리자 결재 목록에 요청이 등록돼요.",
  toast: "결재 요청이 완료되었습니다.",
  doneEmotion: "결재 요청을 보냈어요.",
  statusChanged: "프로젝트 목록에서 결재 진행 상태를 확인할 수 있어요.",
};

// 빈 상태 + 첫 행동 CTA (가이드 §원칙5, #12)
export const EMPTY_PROJECTS = {
  message: "조건에 맞는 프로젝트가 없어요.",
  cta: "+ 새 프로젝트",
  hint: "‘+ 새 프로젝트’로 첫 검토를 시작해 보세요.",
};
