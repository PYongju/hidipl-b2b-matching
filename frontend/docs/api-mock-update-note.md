# API mock update note

작성일: 2026-06-02

## 목적

프론트 통합 준비를 위해 local mock 데이터를 백엔드 API 샘플 JSON 구조에 맞춰 정리했다.

## 반영 내용

- `/compare` 응답의 `rows` 배열 구조 유지
- `compare_rows_required_fields.json`의 주요 필드 포함
- `source_items` 구조를 `{ name, category, amount }`로 반영
- `highlights` 구조를 boolean flag로 반영
  - `is_lowest_total_price`
  - `is_fastest_delivery`
  - `is_longest_warranty`
  - `is_highest_score`
- status 6종 케이스 포함
  - `normal`
  - `included`
  - `separate`
  - `missing`
  - `to_be_discussed`
  - `parse_failed`
- 백엔드가 공유한 `cost_breakdown.*.status = "parse_failed"` 예시를 실패 mock에 반영

## 참고

현재 백엔드 샘플 JSON 중 일부는 실제 `rows`가 1개뿐이다. 프론트 화면에서는 3개 공급사 비교, 상태 배지, 하이라이트, 실패 케이스를 함께 검증해야 하므로 local mock은 실제 API 구조를 따르되 3개 공급사 row를 유지한다.

즉, local mock은 실제 API 응답을 그대로 복사한 데이터가 아니라 API 계약 검증과 UI 상태 검증을 위한 확장 mock이다.

## 2026-06-02 추가 정리

통합 시 mock 데이터가 화면 로직에 직접 붙어 있지 않도록 구조를 분리했다.

- `compareAdapter`는 mock을 import하지 않고, 전달받은 `/compare` 응답을 화면용 데이터로 변환만 한다.
- mock 선택 로직은 `src/data/getMockCompareResponse.js`로 분리했다.
- `useCompareResult`는 기본적으로 local mock을 사용하지만, 아래 환경 변수를 설정하면 실제 API를 호출한다.

```env
VITE_API_BASE_URL=https://api.example.com
VITE_USE_MOCK_API=false
```

실제 백엔드 통합 시에는 mock 파일을 바로 삭제하기보다 개발/데모/실패 상태 검증용으로 남겨두고, 화면에서는 API 응답을 우선 사용하도록 관리하는 편이 안전하다.

## 2026-06-02 explanation API 전환 준비

AI 근거 요약도 compare와 같은 방식으로 API 우선 구조로 변경했다.

- `useExplanationResult`는 기본적으로 local mock을 사용한다.
- `VITE_API_BASE_URL`이 있고 `VITE_USE_MOCK_API=false`이면 실제 API를 호출한다.
- 실제 호출 endpoint는 `GET /api/v1/projects/{project_id}/matches/{match_id}/explanation`이다.
- mock 선택 로직은 `src/data/getMockExplanationResponse.js`로 분리했다.
- 응답 변환은 `src/utils/explanationAdapter.js`가 담당한다.

실제 API 호출에는 `project_id`와 `match_id`가 필요하다. 둘 중 하나가 없으면 explanation 영역은 fallback 상태로 표시된다.

## 2026-06-02 mock/API 전환 규칙 통일

mock/API 전환 기준을 `src/api/apiMode.js`로 분리했다.

```js
const shouldUseMockApi = import.meta.env.VITE_USE_MOCK_API !== "false" || !hasApiBaseUrl;
```

따라서 compare와 explanation은 같은 규칙을 따른다.

- `VITE_USE_MOCK_API=false`
- `VITE_API_BASE_URL` 존재

위 두 조건을 만족하면 compare와 explanation 모두 실제 API를 사용한다. 그 외에는 local mock을 사용한다.
