const normalExplanationResponse = {
  project_id: "project_mock_001",
  match_id: "match_mock_001",
  request_id: "request_mock_001",
  customer_name: "삼성전자 반도체",
  overall_summary:
    "A Display는 가격, 납기, 스펙 일치율에서 가장 안정적인 선택지입니다. BrightSign Korea는 전문성과 가격 경쟁력이 있으나 일부 조건 확인이 필요합니다. VisionTech는 설치 역량은 있으나 스펙 불일치와 미기재 항목이 있어 원본 확인이 필요합니다.",
  supplier_explanations: [
    {
      quote_id: "quote_a_display",
      vendor_name: "A Display",
      rank: 1,
      card_summary: "가격, 납기, 스펙 조건이 균형적으로 우수한 견적입니다.",
      strengths: ["가격 경쟁력", "납기 대응력", "스펙/구성 충족"],
      weaknesses: ["최종 계약 전 원본 조건 확인 필요"],
      check_required: [],
      metadata: { provider: "mock", filter_reasons: [] },
    },
    {
      quote_id: "quote_brightsign",
      vendor_name: "BrightSign Korea",
      rank: 2,
      card_summary: "사이니지 솔루션 전문성이 있으나 일부 비용 조건 확인이 필요합니다.",
      strengths: ["사이니지 전문성", "솔루션 다양성", "품질 이력 우수"],
      weaknesses: ["일부 항목 검토 필요", "납기 지연 가능성"],
      check_required: ["자재비 확인 필요"],
      metadata: { provider: "mock", filter_reasons: [] },
    },
    {
      quote_id: "quote_visiontech",
      vendor_name: "VisionTech",
      rank: 3,
      card_summary: "설치 역량은 있으나 스펙과 총액 기준 확인이 필요합니다.",
      strengths: ["설치 역량", "현장 대응 가능"],
      weaknesses: ["스펙 일부 불일치", "미기재 항목 존재"],
      check_required: ["총액 미확정", "OCR 분석 실패 항목 확인"],
      metadata: { provider: "mock", filter_reasons: [] },
    },
  ],
  provider: "mock",
  warnings: [],
  metadata: {
    source: "local_mock",
    example_type: "frontend_explanation_mock",
  },
};

const failureExplanationResponse = {
  ...normalExplanationResponse,
  overall_summary:
    "A Display는 필수 항목 대부분이 정상 추출되었습니다. BrightSign Korea는 일부 금액 항목의 확인이 필요하고, VisionTech는 OCR 분석 실패와 총액 미확정 상태라 최저가 비교에서 제외해야 합니다.",
  warnings: ["LLM 설명 생성 실패 시 규칙 기반 요약으로 대체"],
  metadata: {
    source: "local_mock",
    example_type: "frontend_explanation_fallback_mock",
  },
};

export { failureExplanationResponse, normalExplanationResponse };
