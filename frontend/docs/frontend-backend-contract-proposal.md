# 프론트-백엔드 데이터 계약 정리 제안

작성일: 2026-06-02  
작성 목적: 프론트와 백엔드의 `/compare` 연동 전, 데이터 구조 불일치 지점을 정리하고 해결 방향을 제안한다.  
문서 성격: 확정안이 아닌 논의용 제안서

---

## 1. 현재 상황 요약

현재 git 병합 자체는 큰 문제가 없지만, 실제 화면에 백엔드 데이터를 연결하려면 프론트와 백엔드 사이의 데이터 계약을 맞춰야 한다.

프론트는 기존에 화면 표시용 mock 데이터를 기준으로 개발되어 있었고, 백엔드는 원본 숫자, 상태값, 근거 항목을 포함한 구조화된 데이터를 내려주는 방향이다.

따라서 현재 문제는 "화면이 없다" 또는 "API가 없다"가 아니라, 아래 네 가지 불일치를 어떻게 정리할 것인지에 가깝다.

- 금액 표현 방식
- 셀 데이터 구조
- 키 네이밍 방식
- 응답 봉투 처리 방식

---

## 2. 불일치 1 — 금액 표현 방식

### 현재 상태

백엔드는 금액을 숫자로 내려준다.

```json
{
  "amount": 11500000
}
```

프론트 mock은 이미 화면에 표시할 문자열로 가지고 있었다.

```js
displayHw: "₩ 15,200,000"
```

### 문제

프론트가 문자열 금액을 기준으로 처리하면 정렬, 최저가 비교, 합계 계산, 통화 포맷 변경이 어려워진다.

반대로 백엔드가 화면 표시용 문자열까지 만들어주면, 화면 정책이 바뀔 때 백엔드까지 수정해야 한다.

### 제안

금액은 백엔드가 number 원본값으로 내려주고, 화면 표시용 콤마와 원 표시는 프론트에서 처리한다.

```text
백엔드: 11500000
프론트 표시: ₩ 11,500,000
```

### 제안 이유

- 숫자로 받아야 정렬과 최저가 비교가 안정적이다.
- 통화 표시 방식이 바뀌어도 프론트에서만 수정하면 된다.
- 백엔드는 데이터 원본 제공에 집중하고, 프론트는 화면 표현에 집중할 수 있다.

---

## 3. 불일치 2 — 셀 데이터 구조

### 현재 상태

백엔드는 셀을 객체로 내려준다.

```json
"display_hw": {
  "amount": 11500000,
  "status": "포함",
  "source_items": []
}
```

프론트 mock은 셀을 문자열 하나로 가지고 있었다.

```js
displayHw: "₩ 15,200,000"
```

### 문제

문자열 하나만 있으면 아래 정보를 분리해서 사용하기 어렵다.

- 실제 금액
- 화면 표시값
- 상태 배지
- 근거 항목

예를 들어 `"확인 필요"`라는 문자열이 값인지, 상태인지, 배지 문구인지 구분하기 어려워진다.

### 제안

백엔드는 현재처럼 `{ amount, status, source_items }` 구조를 유지하고, 프론트 adapter에서 화면용 셀 구조로 변환한다.

백엔드 응답:

```json
{
  "amount": 11500000,
  "status": "included",
  "source_items": []
}
```

프론트 adapter 결과:

```js
{
  value: 11500000,
  display: "₩ 11,500,000",
  status: "included",
  sourceItems: []
}
```

### 제안 이유

- 화면에는 `display`를 보여주면 된다.
- 배지는 `status`를 보고 붙일 수 있다.
- 행 근거 보기에는 `sourceItems`를 사용할 수 있다.
- 값과 상태가 섞이지 않아 유지보수가 쉬워진다.

---

## 4. 불일치 3 — 키 네이밍 방식

### 현재 상태

백엔드는 Python/FastAPI 기준의 snake_case를 사용한다.

```json
{
  "display_hw": {},
  "travel_expense": {},
  "source_items": []
}
```

프론트는 React 기준의 camelCase 또는 화면용 key를 사용한다.

```js
{
  displayHw: {},
  travelCost: {},
  sourceItems: []
}
```

### 문제

컴포넌트에서 백엔드 key를 직접 읽기 시작하면 화면 코드가 API 구조에 강하게 묶인다.

예를 들어 `DashboardPage`가 직접 `cost_breakdown.display_hw.amount`를 읽으면, API key가 바뀔 때 화면 컴포넌트까지 계속 수정해야 한다.

### 제안

API 응답은 백엔드 기준 snake_case를 유지하고, 프론트 내부에서는 adapter에서 camelCase 또는 화면용 key로 변환한다.

```text
display_hw → displayHw
travel_expense → travelExpense 또는 travelCost
source_items → sourceItems
```

### 제안 이유

- 백엔드는 Python 스타일을 유지할 수 있다.
- 프론트는 React 코드 스타일을 유지할 수 있다.
- 변환 규칙이 adapter 한 곳에만 모이므로 수정 범위가 줄어든다.

---

## 5. 불일치 4 — 응답 봉투 처리 방식

### 현재 상태

백엔드 응답은 `{ ok, data, error }` 형태로 감싸질 수 있다.

```json
{
  "ok": true,
  "data": {
    "rows": []
  },
  "error": null
}
```

프론트 mock에는 이런 봉투 구조가 없다.

### 문제

화면 컴포넌트나 adapter가 매번 `res.data.rows`를 직접 신경 쓰면, API 응답 구조가 화면 코드 전체에 퍼진다.

또한 에러 처리도 화면마다 중복될 가능성이 있다.

### 제안

응답 봉투는 API client에서 한 번만 해제한다.

```js
const envelope = await response.json();

if (!envelope.ok) {
  throw new Error(envelope.error?.message ?? "API 요청 실패");
}

return envelope.data;
```

그 다음 adapter에는 `data`만 전달한다.

```js
const compareData = await fetchCompare(projectId);
const viewModel = createCompareViewModel(compareData);
```

### 제안 이유

- `{ ok, data, error }` 처리는 API client 책임으로 고정된다.
- adapter와 화면 컴포넌트는 실제 데이터만 다루면 된다.
- 에러 처리 위치가 명확해진다.

---

## 6. 권장 처리 흐름

프론트와 백엔드 연결은 아래 흐름으로 정리하는 것을 제안한다.

```text
백엔드 응답
{ ok, data, error }
        ↓
API client
ok/error 처리 후 data 반환
        ↓
compareAdapter
snake_case → 화면용 key
number → display string
status → UI status
        ↓
DashboardPage
화면 렌더링
```

이 구조에서는 `DashboardPage`가 백엔드 응답 세부 구조를 직접 알 필요가 없다.

---

## 7. status / 배지 처리 제안

### 현재 쟁점

문서 기준으로 현재 status와 배지 책임이 명확히 정리되지 않았다.

- ML 구현: status를 계산해서 내려줌
- 백엔드 주석: 프론트가 배지 처리한다고 적혀 있음
- 기존 프론트: status를 보지 않고 mock 위치 기반으로 하드코딩

이 상태에서는 실제 API 연결 시 배지가 잘못 붙거나, 같은 상태가 여러 문구로 표시될 수 있다.

### 제안

백엔드는 셀의 의미 상태를 enum으로 내려주고, 프론트는 status를 화면 문구와 색상으로 매핑한다.

추천 enum:

```text
normal
included
separate
missing
to_be_discussed
parse_failed
```

프론트 표시 예시:

| status | 화면 문구 | 색상 | 의미 |
| --- | --- | --- | --- |
| normal | 없음 | 기본 | 정상 값 |
| included | 포함 | 초록 | 다른 항목에 포함 |
| separate | 별도 청구 | 회색 | 별도 비용 가능 |
| missing | 미기재 | 회색 | 견적서에 없음 |
| to_be_discussed | 검토 필요 | 주황 | 값은 있으나 계약 전 확인 필요 |
| parse_failed | OCR 분석 실패 | 빨강 | 시스템이 제대로 추출하지 못함 |

### 비교 결과 배지 분리 제안

`최저가`, `납기 우위`, `보증 우위`, `AI 추천`은 셀 상태라기보다 비교 결과다.

따라서 status에 섞기보다 `highlights` 플래그로 처리하는 것이 좋다.

```json
"highlights": {
  "is_lowest_total_price": true,
  "is_fastest_delivery": false,
  "is_longest_warranty": true,
  "is_highest_score": false
}
```

---

## 8. 팀에 제안할 문장

아래 문장을 회의나 노션 댓글에 사용할 수 있다.

```text
프론트-백엔드 데이터 불일치는 adapter 계층을 두는 방식으로 해결하면 좋겠습니다.

1. 금액은 백엔드가 number 원본값으로 내려주고, 화면용 콤마/원 표시는 프론트에서 처리
2. 셀은 문자열이 아니라 { amount, status, source_items } 객체 기준으로 유지
3. API key는 snake_case를 유지하고, 프론트 adapter에서 화면용 key로 변환
4. { ok, data, error } 응답 봉투는 API client에서만 해제
5. status는 백엔드에서 enum으로 내려주고, 프론트는 라벨과 색상 매핑만 담당
6. 최저가/납기 우위/보증 우위는 status가 아니라 highlights로 분리

이렇게 하면 백엔드와 프론트가 각자 편한 구조를 유지하면서도, 화면 연결은 안정적으로 처리할 수 있을 것 같습니다.
```

---

## 9. 프론트 작업 방향

프론트에서는 다음 구조를 우선 준비하는 것이 좋다.

```text
src/api/apiClient.js
src/utils/compareAdapter.js
src/utils/statusMap.js
```

역할:

| 파일 | 역할 |
| --- | --- |
| `apiClient.js` | 실제 API 호출, `{ ok, data, error }` 처리 |
| `compareAdapter.js` | 백엔드 응답을 화면 데이터 구조로 변환 |
| `statusMap.js` | status enum을 배지 문구와 색상으로 변환 |

현재 프론트에서 이미 준비한 `compareAdapter`, `statusMap`, `mockCompareResponse` 방향은 이 제안과 일치한다.

---

## 10. Dashboard 데이터 흐름 확인

2026-06-02 기준으로 `DashboardPage`는 견적 비교 데이터를 `mockProjects`에서 직접 가져오지 않고, adapter 결과만 사용한다.

현재 흐름:

```text
mockCompareResponse
        ↓
getCompareMockResponse(projectData)
        ↓
createCompareViewModel(response)
        ↓
DashboardPage
```

`DashboardPage`에서 직접 사용하는 값:

```js
const { comparisonSections, suppliers, totalRows } = createCompareViewModel(...);
```

확인 결과:

- `DashboardPage`는 `mockProjects`의 `suppliers`, `comparisonSections`, `totalRows`를 직접 import하지 않는다.
- `DashboardPage`는 `supplier.comparison`, `statusBySupplier`, `highlightBySupplier`를 직접 읽지 않는다.
- `App.jsx`는 프로젝트 목록, 생성 기본값, 카드 표시용으로만 `mockProjects`를 사용한다.
- `TableCell.jsx`에는 예전 `supplier.comparison` 로직이 남아 있으나 현재 어디에서도 import되지 않는 미사용 컴포넌트다. 혼동 방지를 위해 추후 삭제 또는 adapter 기반 리팩터링 후보로 둔다.

---

## 11. 로딩/에러 상태 UI 준비

API 연결 전이라도 비교 대시보드는 다음 3가지 상태를 분리해서 처리한다.

| 상태 | 의미 | 화면 처리 |
| --- | --- | --- |
| `ready` | 비교 데이터가 정상 준비됨 | 공급사 카드, 비교 테이블, AI 근거 패널, 하단 액션 노출 |
| `loading` | `/compare` 응답 또는 adapter 변환 대기 중 | 공급사 카드/테이블/우측 패널 위치에 skeleton UI 표시 |
| `error` | API 실패, 응답 구조 불일치, 프로젝트 ID 오류 등으로 비교 데이터 로드 실패 | 에러 안내 카드, 확인 항목, 다시 시도, 프로젝트 목록 이동 버튼 표시 |

프론트 임시 기준:

```js
const compareState = projectData.compareState ?? "ready";
const compareErrorMessage =
  projectData.compareErrorMessage ?? "견적 비교 데이터를 불러오지 못했습니다.";
```

실제 API 연결 후에는 `fetchCompare()` 호출 상태에 따라 `compareState`를 결정한다.

```text
요청 전/요청 중: loading
성공 + adapter 변환 성공: ready
네트워크 실패/API error/adapter 변환 실패: error
```

주의할 점:

- `loading` 상태에서는 기존 mock 데이터가 잠깐 보이지 않도록 비교 본문을 숨긴다.
- `error` 상태에서는 최종 선정, 보고서 내보내기 등 비교 결과 기반 액션을 숨긴다.
- `다시 시도` 버튼은 실제 API 연결 시 `fetchCompare()` 재호출로 교체한다. 현재 로컬 UI에서는 페이지 새로고침으로 동작한다.

---

## 12. 확정된 API 연결 흐름

2026-06-02 백엔드 답변 기준으로 다음 항목은 확정으로 본다.

### 12-1. OCR/파싱 실패 셀

특정 비교 셀의 값 추출 실패는 `cost_breakdown.*.status = "parse_failed"`로 내려온다.

예:

```json
{
  "display_hw": {
    "amount": null,
    "status": "parse_failed",
    "source_items": []
  }
}
```

프론트 표시:

- 셀 본문: `OCR 분석 실패`
- 배지: `OCR 분석 실패`
- 색상: 빨강
- 의미: 시스템이 제대로 추출하지 못했으므로 수정 필수

### 12-2. 프로젝트 생성부터 LLM 근거 조회까지

프론트 연결 흐름은 다음 순서로 본다.

```text
1. POST /api/v1/projects
   -> project_id 생성

2. POST /api/v1/projects/{project_id}/quotes
   -> 견적서 업로드 및 Quote Pool 생성

3. POST /api/v1/projects/{project_id}/matches
   -> 추천 실행, 응답에서 match_id 확보

4. GET /api/v1/projects/{project_id}/matches/{match_id}/explanation
   -> 해당 match_id 기준 AI 추천 사유 조회
```

현재 `src/api/apiClient.js`에는 위 흐름에 맞춰 `createProject`, `uploadProjectQuotes`, `runProjectMatch`, `fetchExplanation`을 준비해둔다.

---

## 13. 결론

백엔드에게 모든 데이터를 프론트 화면 문자열로 바꿔달라고 할 필요는 없다.

반대로 프론트가 백엔드 응답을 화면 컴포넌트에서 직접 해석하는 것도 좋지 않다.

가장 안정적인 방향은 다음과 같다.

```text
백엔드는 원본 데이터와 의미 상태를 정확히 내려준다.
프론트는 adapter에서 화면용 데이터로 변환한다.
화면 컴포넌트는 변환된 데이터만 렌더링한다.
```

이 방식으로 진행하면 API 응답이 조금 바뀌더라도 수정 범위를 adapter 쪽으로 제한할 수 있고, 발표 전 통합 리스크도 줄일 수 있다.
