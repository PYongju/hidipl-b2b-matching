const initialProjectData = {
  companyName: "",
  location: "",
  projectName: "",
  currentStage: "견적 수집 중",
  projectDate: "",
  usage: "",
  displaySize: "W 12000 x H 3000 mm",
  displayUnit: "mm",
  displayWidth: "12000",
  displayHeight: "3000",
  displayInch: "",
  quantity: "",
  budgetAmount: "",
  operationTime: "24/7",
  reviewPreset: "균형 추천",
  solutions: [],
  quoteFiles: [],
};

function makeProjectFromData(data, id) {
  const projectId = id ?? `PV-${new Date().getFullYear()}-${String(Date.now()).slice(-4)}`;
  const quoteFileNames = (data.quoteFiles ?? []).map((file) => file.name);
  const serializableData = Object.fromEntries(
    Object.entries(data).filter(([key]) => key !== "quoteFiles"),
  );

  return {
    id: projectId,
    name: data.projectName || "이름 없는 프로젝트",
    status: "검토 중",
    statusTone: "blue",
    desc: data.usage || "요구사항 미입력",
    meta: [
      data.projectDate || "일정 미정",
      data.budgetAmount ? `${data.budgetAmount}원 이하` : "예산 미정",
      "공급사 3개",
    ],
    data: { ...serializableData, quoteFileNames },
  };
}

export { initialProjectData, makeProjectFromData };
