// 한글 받침 여부에 따라 조사를 자동으로 붙입니다.
// 받침을 판별할 수 없는 영문/숫자로 끝나는 이름은 "(을)를" 형태로 안전하게 표기합니다.
// 예: "비전텍" → "비전텍을", "A Display" → "A Display을(를)"

function lastCharHasBatchim(word) {
  const text = String(word ?? "").trim();
  if (!text) return null;

  const code = text.charCodeAt(text.length - 1);
  // 한글 음절(가~힣) 범위가 아니면 받침 판별 불가
  if (code < 0xac00 || code > 0xd7a3) return null;

  return (code - 0xac00) % 28 !== 0;
}

function withParticle(word, withBatchim, withoutBatchim, ambiguous) {
  const name = String(word ?? "");
  const batchim = lastCharHasBatchim(name);
  if (batchim === null) return `${name}${ambiguous}`;
  return `${name}${batchim ? withBatchim : withoutBatchim}`;
}

// 목적격 조사: 을/를
function withObjectParticle(word) {
  return withParticle(word, "을", "를", "을(를)");
}

// 주격 조사: 이/가
function withSubjectParticle(word) {
  return withParticle(word, "이", "가", "이(가)");
}

export { withObjectParticle, withSubjectParticle };
