import { useState } from "react";
import LoginPage from "./pages/LoginPage";
import ProjectListPage from "./pages/ProjectListPage";
import ProjectCreatePage from "./pages/ProjectCreatePage";
import ProjectRequirementsPage from "./pages/ProjectRequirementsPage";
import AnalysisPage from "./pages/AnalysisPage";
import DashboardPage from "./pages/DashboardPage";
import PartnerMatchingPage from "./pages/PartnerMatchingPage";
import PartnerMatchingLoadingPage from "./pages/PartnerMatchingLoadingPage";
import QuoteWaitingPage from "./pages/QuoteWaitingPage";
import QuoteReviewLoadingPage from "./pages/QuoteReviewLoadingPage";
import ReportHistoryPage from "./pages/ReportHistoryPage";
import {
  createProject,
  runProjectMatch,
  uploadProjectQuotes,
} from "./api/apiClient";
import {
  initialProjectData,
  makeProjectFromData,
} from "./data/mockProjects";
import { createMatchViewModel } from "./utils/matchAdapter";

export default function App() {
  const [screen, setScreen] = useState("login");
  const [projectData, setProjectData] = useState(initialProjectData);
  const [projects, setProjects] = useState([]);
  const [editingProjectId, setEditingProjectId] = useState("");
  const [activeProjectId, setActiveProjectId] = useState("");
  const [analysisState, setAnalysisState] = useState("idle");
  const [analysisErrorMessage, setAnalysisErrorMessage] = useState("");

  const startNewProject = () => {
    setEditingProjectId("");
    setProjectData({ ...initialProjectData });
    setScreen("wizard");
  };

  const createDraftProject = (draftData, shouldContinue = false) => {
    const projectId = `PV-${new Date().getFullYear()}-${String(Date.now()).slice(-4)}`;
    const nextData = {
      ...initialProjectData,
      ...draftData,
      projectId,
      currentStage: draftData.currentStage || "요구사항",
    };
    const nextProject = {
      id: projectId,
      name: nextData.projectName || `${nextData.companyName || "신규 고객"} 검토 건`,
      status: "초안",
      statusTone: "gray",
      desc: nextData.usage || "요구사항 정리 중",
      meta: [
        nextData.projectDate || "일정 미정",
        nextData.budgetAmount ? `${nextData.budgetAmount} 이하` : "예산 미정",
        nextData.category || "카테고리 미정",
      ],
      data: nextData,
    };

    setProjects((current) => [nextProject, ...current]);
    setProjectData(nextData);
    setActiveProjectId(projectId);
    setEditingProjectId(projectId);

    if (shouldContinue) {
      setScreen("requirements");
    }
  };

  const editProject = (project) => {
    setEditingProjectId(project.id);
    setProjectData({ ...initialProjectData, ...project.data });
    setScreen("wizard");
  };

  const openRequirements = (projectId) => {
    const project = projects.find((item) => item.id === projectId);
    if (project) {
      setProjectData({ ...initialProjectData, ...project.data });
      setActiveProjectId(project.id);
      setEditingProjectId(project.id);
    }
    setScreen("requirements");
  };

  const openDashboard = () => {
    setScreen("dashboard");
  };

  const deleteProjects = (projectIds) => {
    setProjects((current) =>
      current.filter((project) => !projectIds.includes(project.id)),
    );
    if (projectIds.includes(activeProjectId)) {
      setActiveProjectId("");
    }
  };

  const completeAnalysis = () => {
    const id = editingProjectId || undefined;
    const nextProject = makeProjectFromData(projectData, id);
    setProjects((current) => {
      const exists = current.some((project) => project.id === nextProject.id);
      return exists
        ? current.map((project) =>
            project.id === nextProject.id ? nextProject : project,
          )
        : [nextProject, ...current];
    });
    setActiveProjectId(nextProject.id);
    setEditingProjectId(nextProject.id);
    setScreen("partnerMatching");
  };

  const startPartnerMatchingFromRequirements = async () => {
    setAnalysisErrorMessage("");
    setScreen("partnerMatchingLoading");

    if (projectData.projectApiId) {
      return;
    }

    try {
      const createdProject = await createProject(buildProjectRequest(projectData));
      const projectApiId = createdProject.project_id ?? createdProject.id;
      const requestId = createdProject.request_id ?? createdProject.requestId;

      setProjectData((current) => ({
        ...current,
        projectApiId,
        requestId,
        createdProject,
      }));
    } catch (error) {
      setAnalysisErrorMessage(
        error.message || "프로젝트 요구사항 저장 중 오류가 발생했습니다.",
      );
      setScreen("requirements");
    }
  };

  const buildProjectRequest = (data) => {
    const displaySizeText = data.displaySize || "";

    return {
      company_name: data.companyName || "미입력",
      location: data.location || null,
      deadline: data.projectDate || null,
      request_text: [
        `프로젝트명: ${data.projectName || "미입력"}`,
        `활용 용도: ${data.usage || "미입력"}`,
        `디스플레이 크기: ${displaySizeText || "미입력"}`,
        `수량: ${data.quantity || "미입력"}`,
        `운영 시간: ${data.operationTime || "미입력"}`,
        `카테고리: ${data.category || "미입력"}`,
        `예산 상한: ${data.budgetAmount || "미입력"}`,
        `현재 단계: ${data.currentStage || "미입력"}`,
        `우선 검토 기준: ${data.reviewPreset || "미입력"}`,
        `추가 요청사항: ${data.otherConditions || "없음"}`,
        `첨부 메모: ${data.attachmentMemo || "없음"}`,
      ].join("\n"),
    };
  };

  /*
  const buildProjectRequestLegacy = (data) => ({
    company_name: data.companyName,
    location: data.location,
    deadline: data.projectDate,
    request_text: [
      `프로젝트명: ${data.projectName}`,
      `활용 용도: ${data.usage}`,
      `디스플레이 요구: ${data.displayRequirements || data.displaySize}`,
      `수량: ${data.quantity}`,
      `예산: ${data.budgetAmount}`,
      `운영 조건: ${data.operationTime}`,
      `현재 단계: ${data.currentStage}`,
    ].join(", "),
  });
  */

  const startAnalysisFlow = async () => {
    setScreen("analysis");
    setAnalysisState("loading");
    setAnalysisErrorMessage("");

    try {
      const createdProject = await createProject(
        buildProjectRequest(projectData),
      );
      const projectApiId = createdProject.project_id ?? createdProject.id;
      const requestId = createdProject.request_id ?? createdProject.requestId;
      const uploadResult = await uploadProjectQuotes(
        projectApiId,
        projectData.quoteFiles ?? [],
      );
      const quoteIds =
        uploadResult.quote_ids ??
        uploadResult.quotes?.map((quote) => quote.quote_id ?? quote.id) ??
        [];
      const matchResult = await runProjectMatch(projectApiId);
      const matchViewModel = createMatchViewModel(matchResult);
      const matchId = matchViewModel.matchId;

      setProjectData((current) => ({
        ...current,
        projectApiId,
        requestId,
        createdProject,
        quoteIds,
        matchId,
        matchResult: matchViewModel,
        quoteUploadResult: uploadResult,
      }));
      setAnalysisState("ready");
    } catch (error) {
      setAnalysisErrorMessage(
        error.message || "AI 분석 실행 중 오류가 발생했습니다.",
      );
      setAnalysisState("error");
    }
  };

  if (screen === "login") {
    return <LoginPage onLogin={() => setScreen("projects")} />;
  }

  if (screen === "projects") {
    return (
      <ProjectListPage
        projects={projects}
        onCreate={startNewProject}
        onCreateDraft={createDraftProject}
        onDeleteProjects={deleteProjects}
        onEditProject={editProject}
        onOpenDashboard={openRequirements}
      />
    );
  }

  if (screen === "requirements") {
    return (
      <ProjectRequirementsPage
        projectData={projectData}
        onBack={() => setScreen("projects")}
        onNext={startPartnerMatchingFromRequirements}
        onProjectDataChange={setProjectData}
      />
    );
  }

  if (screen === "wizard") {
    return (
      <ProjectCreatePage
        projectData={projectData}
        onProjectDataChange={setProjectData}
        onAnalyze={startAnalysisFlow}
        onBack={() => setScreen("projects")}
      />
    );
  }

  if (screen === "analysis") {
    return (
      <AnalysisPage
        errorMessage={analysisErrorMessage}
        onBack={() => setScreen("wizard")}
        onDashboard={completeAnalysis}
        onRetry={startAnalysisFlow}
        state={analysisState}
      />
    );
  }

  if (screen === "partnerMatchingLoading") {
    return (
      <PartnerMatchingLoadingPage
        projectData={projectData}
        onBack={() => setScreen("requirements")}
        onComplete={() => setScreen("partnerMatching")}
      />
    );
  }

  if (screen === "partnerMatching") {
    return (
      <PartnerMatchingPage
        projectData={projectData}
        onBack={() => setScreen("requirements")}
        onGoDashboard={() => setScreen("quoteWaiting")}
      />
    );
  }

  if (screen === "quoteWaiting") {
    return (
      <QuoteWaitingPage
        projectData={projectData}
        onBack={() => setScreen("partnerMatching")}
        onGoDashboard={() => setScreen("quoteReviewLoading")}
        onProjectDataChange={setProjectData}
      />
    );
  }

  if (screen === "quoteReviewLoading") {
    return (
      <QuoteReviewLoadingPage
        projectData={projectData}
        onBack={() => setScreen("quoteWaiting")}
        onComplete={openDashboard}
        onProjectDataChange={setProjectData}
      />
    );
  }

  if (screen === "reportHistory") {
    return (
      <ReportHistoryPage
        projectData={projectData}
        onBack={openDashboard}
        onGoProjects={() => setScreen("projects")}
      />
    );
  }

  return (
    <DashboardPage
      projectData={projectData}
      onGoProjects={() => setScreen("projects")}
      onGoQuoteWaiting={() => setScreen("quoteWaiting")}
      onGoReport={() => setScreen("reportHistory")}
    />
  );
}
