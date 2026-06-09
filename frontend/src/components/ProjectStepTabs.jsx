const STEP_LABELS = [
  "1 요구사항",
  "2 파트너 매칭/견적 요청",
  "3 견적 수신",
  "4 견적 검토",
];

export default function ProjectStepTabs({
  activeStep,
  onGoRequirements,
  onGoPartnerMatching,
  onGoQuoteWaiting,
  onGoQuoteReview,
}) {
  const handlers = [
    onGoRequirements,
    onGoPartnerMatching,
    onGoQuoteWaiting,
    onGoQuoteReview,
  ];

  return (
    <nav className="partner-stepper project-step-tabs" aria-label="프로젝트 상세 단계">
      {STEP_LABELS.map((label, index) => {
        const step = index + 1;
        const handler = handlers[index];
        return (
          <button
            className={activeStep === step ? "active" : ""}
            disabled={!handler && activeStep !== step}
            key={label}
            onClick={handler}
            type="button"
          >
            {label}
          </button>
        );
      })}
    </nav>
  );
}
