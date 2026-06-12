import { useState } from "react";
import LoginPage from "./pages/LoginPage";
import ProjectListPage from "./pages/ProjectListPage";
import ProjectCreatePage from "./pages/ProjectCreatePage";
import ProjectRequirementsPage from "./pages/ProjectRequirementsPage";
import AnalysisPage from "./pages/AnalysisPage";
import DashboardPage from "./pages/DashboardPage";
import PartnerMatchingPage from "./pages/PartnerMatchingPage";
import PartnerMatchingLoadingModal from "./components/PartnerMatchingLoadingModal";
import QuoteWaitingPage from "./pages/QuoteWaitingPage";
import QuoteReviewLoadingPage from "./pages/QuoteReviewLoadingPage";
import {
  createProject,
  deleteProjects as deleteProjectsApi, // 6/12 백엔드 작업에서 추가
  fetchCandidateVendors,
  fetchProject,
  fetchProjects, // 6/12 백엔드 작업에서 추가
  runProjectMatch,
  uploadProjectQuotes,
} from "./api/apiClient";
import { initialProjectData, makeProjectFromData } from "./data/mockProjects";
import { createMatchViewModel } from "./utils/matchAdapter";

const PARTNER_MATCHING_MIN_STEP_MS = 1800;

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function runPartnerMatchingStep(step, setStep, action) {
  const stepStartedAt = Date.now();
  setStep(step);
  const result = await action();
  const remainingStepMs =
    PARTNER_MATCHING_MIN_STEP_MS - (Date.now() - stepStartedAt);
  if (remainingStepMs > 0) {
    await wait(remainingStepMs);
  }
  return result;
}

export default function App() {
  // 6/12 수정
  const [screen, setScreen] = useState(() => {
    return localStorage.getItem("hidipl_screen") === "projects"
      ? "projects"
      : "login";
  });
  const [projects, setProjects] = useState([]);
  const [editingProjectId, setEditingProjectId] = useState("");
  const [activeProjectId, setActiveProjectId] = useState("");
  const [analysisState, setAnalysisState] = useState("idle");
  const [analysisErrorMessage, setAnalysisErrorMessage] = useState("");
  const [partnerMatchingTransition, setPartnerMatchingTransition] =
    useState("idle");
  const [partnerMatchingStep, setPartnerMatchingStep] =
    useState("creating-project");
  const [partnerMatchingError, setPartnerMatchingError] = useState("");

  const buildProjectListItem = (data, id = data.projectId, overrides = {}) => ({
    id,
    name: data.projectName || `${data.companyName || "신규 고객"} 검토 건`,
    status: overrides.status || data.workflowStatus || "진행 중",
    statusTone:
      overrides.statusTone ||
      getProjectStatusTone(overrides.status || data.workflowStatus),
    desc:
      overrides.desc || data.currentStage || data.usage || "요구사항 정리 중",
    meta: [
      data.projectDate || "일정 미정",
      data.budgetAmount ? `${data.budgetAmount} 이하` : "예산 미정",
      data.category || "카테고리 미정",
    ],
    data: {
      ...data,
      ...(overrides.data ?? {}),
    },
  });

  const syncProjectList = (data, overrides = {}) => {
    const id = editingProjectId || data.projectId;
    if (!id) return;
    const nextProject = buildProjectListItem(data, id, overrides);
    setProjects((current) => {
      const exists = current.some((project) => project.id === id);
      return exists
        ? current.map((project) => (project.id === id ? nextProject : project))
        : [nextProject, ...current];
    });
    setActiveProjectId(id);
    setEditingProjectId(id);
  };

  const updateProjectData = (updater, listOverrides = {}) => {
    setProjectData((current) => {
      const nextData =
        typeof updater === "function" ? updater(current) : updater;
      syncProjectList(nextData, listOverrides);
      return nextData;
    });
  };

  const goToProjects = async () => {
    try {
      const list = await fetchProjects();
      setProjects(
        (list ?? []).map((item) =>
          buildProjectListItem(
            {
              ...initialProjectData,
              projectApiId: item.project_id,
              companyName: item.company_name,
              location: item.location,
              projectDate: item.deadline,
              requestText: item.request_text,
              serverStatus: item.status,
              workflowStatus: getWorkflowStatusFromServerStatus(item.status),
              currentStage: getCurrentStageFromServerStatus(item.status),
            },
            item.project_id,
          ),
        ),
      );
    } catch (error) {
      console.error("프로젝트 목록 조회 실패:", error);
    }
    setScreen("projects");
    localStorage.setItem("hidipl_screen", "projects");
  };

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
      workflowStatus: "진행 중",
      lastScreen: "requirements",
    };
    const nextProject = buildProjectListItem(nextData, projectId, {
      status: "진행 중",
      statusTone: "blue",
      desc: shouldContinue ? "요구사항 작성 중" : "요구사항 정리 중",
    });

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

  const openProjectFromList = async (projectId) => {
    const project = projects.find((item) => item.id === projectId);
    if (project) {
      const localProjectData = { ...initialProjectData, ...project.data };
      setProjectData(localProjectData);
      setActiveProjectId(project.id);
      setEditingProjectId(project.id);

      const apiProjectId =
        localProjectData.projectApiId ?? localProjectData.project_id;
      if (apiProjectId) {
        try {
          const serverProject = await fetchProject(apiProjectId);
          const restoredProjectData = mergeServerProjectData(
            localProjectData,
            serverProject,
          );
          setProjectData(restoredProjectData);
          syncProjectList(restoredProjectData);
          setScreen(getScreenFromProject(restoredProjectData));
          return;
        } catch (error) {
          setAnalysisErrorMessage(
            error.message || "프로젝트 상태 조회 중 오류가 발생했습니다.",
          );
        }
      }

      setScreen(getScreenFromProject(localProjectData));
      return;
    }
    setScreen("requirements");
  };

  const saveCurrentProjectScreen = (screenName, overrides = {}) => {
    updateProjectData((current) => ({
      ...current,
      ...overrides,
      lastScreen: screenName,
    }));
  };

  const openDashboard = () => {
    setScreen("dashboard");
  };

  const deleteProjects = async (projectIds) => {
    try {
      await deleteProjectsApi(projectIds);
    } catch (error) {
      console.error("프로젝트 삭제 실패:", error);
    }
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

  const unwrapCandidateVendors = (response) =>
    response?.candidate_vendors ?? response?.candidates ?? [];

  const startPartnerMatchingFromRequirements = async () => {
    if (partnerMatchingTransition === "loading") return;

    if (projectData.projectApiId && projectData.candidateVendors?.length) {
      setScreen("partnerMatching");
      return;
    }

    setPartnerMatchingTransition("loading");
    setPartnerMatchingStep("creating-project");
    setPartnerMatchingError("");

    try {
      const createdProject = projectData.projectApiId
        ? projectData.createdProject
        : await runPartnerMatchingStep(
            "creating-project",
            setPartnerMatchingStep,
            () => createProject(buildProjectRequest(projectData)),
          );
      const projectApiId =
        projectData.projectApiId ??
        createdProject?.project_id ??
        createdProject?.id;

      if (!projectApiId) {
        throw new Error("서버 프로젝트 ID를 확인하지 못했습니다.");
      }

      const candidateResponse = await runPartnerMatchingStep(
        "fetching-candidates",
        setPartnerMatchingStep,
        () => fetchCandidateVendors(projectApiId, 10),
      );
      const candidateVendors = unwrapCandidateVendors(candidateResponse);

      await runPartnerMatchingStep(
        "finishing",
        setPartnerMatchingStep,
        async () => {},
      );

      updateProjectData(
        (current) => ({
          ...current,
          projectApiId,
          requestId:
            createdProject?.request_id ??
            createdProject?.requestId ??
            current.requestId,
          createdProject: createdProject ?? current.createdProject,
          candidateVendors,
          candidateVendorsLoaded: true,
          candidateVendorsResponse: candidateResponse,
          currentStage: "요청 대상 검토중",
          workflowStatus: "진행 중",
          lastScreen: "partnerMatching",
        }),
        {
          status: "진행 중",
          statusTone: "blue",
          desc: "파트너 추천/요청 대상 검토 중",
        },
      );
      setPartnerMatchingTransition("idle");
      setScreen("partnerMatching");
    } catch (error) {
      setPartnerMatchingTransition("error");
      setPartnerMatchingError(
        error.message ||
          "프로젝트 요구사항 저장 또는 파트너 추천 중 오류가 발생했습니다.",
      );
    }
  };

  const cancelPartnerMatchingTransition = () => {
    setPartnerMatchingTransition("idle");
    setPartnerMatchingStep("creating-project");
    setPartnerMatchingError("");
  };

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
    return <LoginPage onLogin={goToProjects} />;
  }

  //6/12 백엔드 작업에서 수정
  if (screen === "projects") {
    return (
      <ProjectListPage
        projects={projects}
        onCreate={startNewProject}
        onCreateDraft={createDraftProject}
        onDeleteProjects={deleteProjects}
        onEditProject={editProject}
        onOpenDashboard={openProjectFromList}
        onMount={goToProjects}
      />
    );
  }

  const goQuoteWaitingFromPartner = () => {
    updateProjectData(
      (current) => ({
        ...current,
        currentStage: "견적서 업로드 대기",
        workflowStatus: "진행 중",
        lastScreen: "quoteWaiting",
      }),
      {
        status: "진행 중",
        statusTone: "blue",
        desc: "견적서 업로드 대기",
      },
    );
    setScreen("quoteWaiting");
  };

  const goQuoteReviewLoading = () => {
    updateProjectData(
      (current) => ({
        ...current,
        currentStage: "견적 비교 분석 중",
        workflowStatus: "검토 중",
        lastScreen: "quoteReviewLoading",
      }),
      {
        status: "검토 중",
        statusTone: "orange",
        desc: "견적 비교 분석 중",
      },
    );
    setScreen("quoteReviewLoading");
  };

  const openDashboardAfterMatch = () => {
    updateProjectData(
      (current) => ({
        ...current,
        currentStage: "견적 검토",
        workflowStatus: "검토 중",
        lastScreen: "dashboard",
      }),
      {
        status: "검토 중",
        statusTone: "orange",
        desc: "견적 검토 중",
      },
    );
    openDashboard();
  };

  if (screen === "requirements") {
    return (
      <>
        <ProjectRequirementsPage
          isPartnerMatchingLoading={partnerMatchingTransition === "loading"}
          projectData={projectData}
          onBack={() => setScreen("projects")}
          onNext={startPartnerMatchingFromRequirements}
          onProjectDataChange={updateProjectData}
          onSaveDraft={() =>
            saveCurrentProjectScreen("requirements", {
              currentStage: "요구사항",
              workflowStatus: "진행 중",
            })
          }
        />
        <PartnerMatchingLoadingModal
          errorMessage={partnerMatchingError}
          loadingStep={partnerMatchingStep}
          onCancel={cancelPartnerMatchingTransition}
          onRetry={startPartnerMatchingFromRequirements}
          open={
            partnerMatchingTransition === "loading" ||
            partnerMatchingTransition === "error"
          }
          category={projectData.category}
          companyName={projectData.companyName}
          status={partnerMatchingTransition === "error" ? "error" : "loading"}
        />
      </>
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

  if (screen === "partnerMatching") {
    return (
      <PartnerMatchingPage
        projectData={projectData}
        onBack={() => setScreen("requirements")}
        onGoDashboard={goQuoteWaitingFromPartner}
        onProjectDataChange={updateProjectData}
      />
    );
  }

  if (screen === "quoteWaiting") {
    return (
      <QuoteWaitingPage
        projectData={projectData}
        onBack={() => setScreen("partnerMatching")}
        onGoDashboard={goQuoteReviewLoading}
        onProjectDataChange={updateProjectData}
        onSaveDraft={() =>
          saveCurrentProjectScreen("quoteWaiting", {
            currentStage: "견적서 업로드 대기",
            workflowStatus: "진행 중",
          })
        }
      />
    );
  }

  if (screen === "quoteReviewLoading") {
    return (
      <QuoteReviewLoadingPage
        projectData={projectData}
        onBack={() => setScreen("quoteWaiting")}
        onComplete={openDashboardAfterMatch}
        onProjectDataChange={updateProjectData}
      />
    );
  }

  return (
    <DashboardPage
      projectData={projectData}
      onGoProjects={goToProjects}
      onProjectDataChange={updateProjectData}
    />
  );
}

function getProjectStatusTone(status) {
  if (status === "완료") return "green";
  if (status === "검토 중") return "orange";
  return "blue";
}

function mergeServerProjectData(localData, serverProject) {
  const serverStatus =
    serverProject?.status ?? localData.serverStatus ?? localData.status;
  const lastScreen = getScreenFromServerStatus(
    serverStatus,
    localData.lastScreen,
  );
  const workflowStatus = getWorkflowStatusFromServerStatus(
    serverStatus,
    localData.workflowStatus,
  );

  return {
    ...localData,
    projectApiId: serverProject?.project_id ?? localData.projectApiId,
    serverStatus,
    companyName: serverProject?.company_name ?? localData.companyName,
    location: serverProject?.location ?? localData.location,
    projectDate: serverProject?.deadline ?? localData.projectDate,
    requestText: serverProject?.request_text ?? localData.requestText,
    createdAt: serverProject?.created_at ?? localData.createdAt,
    currentStage: getCurrentStageFromServerStatus(
      serverStatus,
      localData.currentStage,
    ),
    workflowStatus,
    lastScreen,
  };
}

function getCurrentStageFromServerStatus(status, fallback = "요구사항") {
  if (status === "matched") return "견적 검토";
  if (status === "quote_uploaded") return "견적 비교 분석 중";
  if (status === "partner_matched") return "견적서 업로드 대기";
  if (status === "created") return "요구사항";
  return fallback;
}

function getWorkflowStatusFromServerStatus(status, fallback = "진행 중") {
  if (status === "matched") return "검토 중";
  if (status === "quote_uploaded") return "검토 중";
  if (status === "partner_matched") return "진행 중";
  if (status === "created") return "진행 중";
  return fallback;
}

function getScreenFromServerStatus(status, fallback = "requirements") {
  if (status === "matched") return "dashboard";
  if (status === "quote_uploaded") return "quoteReviewLoading";
  if (status === "partner_matched") return "quoteWaiting";
  if (status === "created") return "requirements";
  return fallback;
}

function getScreenFromProject(data) {
  const lastScreen = getScreenFromServerStatus(
    data?.serverStatus ?? data?.status,
    data?.lastScreen,
  );
  if (
    lastScreen === "partnerMatching" ||
    lastScreen === "quoteWaiting" ||
    lastScreen === "quoteReviewLoading" ||
    lastScreen === "dashboard"
  ) {
    return lastScreen;
  }
  return "requirements";
}
