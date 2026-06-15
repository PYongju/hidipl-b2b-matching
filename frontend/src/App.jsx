import { useState, useEffect } from "react";
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
  fetchProjectMatches,
  fetchProjects, // 6/12 백엔드 작업에서 추가
  runProjectMatch,
  updateProject,
  uploadProjectQuotes,
} from "./api/apiClient";
import { initialProjectData, makeProjectFromData } from "./data/mockProjects";
import { createMatchViewModel } from "./utils/matchAdapter";
import {
  buildHydratedProjectFields,
  shouldHydrateMatchData,
} from "./utils/projectMatchHydration";
import {
  applyParsedRequestTextToProjectData,
  buildProjectRequestPayload,
  formatProjectSolutions,
  normalizeProjectSolutions,
} from "./utils/projectRequestText";

const PARTNER_MATCHING_MIN_STEP_MS = 1800;
const SESSION_SCREEN_KEY = "hidipl_screen";
const SESSION_PROJECT_KEY = "hidipl_active_project_id";
const KNOWN_SERVER_STATUSES = new Set([
  "matched",
  "created",
  "partner_matched",
  "quote_uploaded",
]);
const PROJECT_FLOW_SCREENS = new Set([
  "requirements",
  "partnerMatching",
  "quoteWaiting",
  "quoteReviewLoading",
  "dashboard",
  "analysis",
  "wizard",
]);

function readSavedSession() {
  return {
    screen: localStorage.getItem(SESSION_SCREEN_KEY),
    projectApiId: localStorage.getItem(SESSION_PROJECT_KEY),
  };
}

function shouldRestoreProjectSession(savedScreen, savedProjectApiId) {
  return Boolean(
    savedProjectApiId
    && savedScreen
    && savedScreen !== "projects"
    && savedScreen !== "login",
  );
}

function persistAppSession(screenName, projectApiId) {
  localStorage.setItem(SESSION_SCREEN_KEY, screenName);
  if (projectApiId && PROJECT_FLOW_SCREENS.has(screenName)) {
    localStorage.setItem(SESSION_PROJECT_KEY, projectApiId);
    return;
  }
  if (screenName === "projects" || screenName === "login") {
    localStorage.removeItem(SESSION_PROJECT_KEY);
  }
}

function resolveProjectListId(data, fallbackId = "") {
  return data.projectApiId ?? data.projectId ?? fallbackId;
}

function matchesProjectEntry(project, targetId, data = {}) {
  const projectApiId = data.projectApiId ?? targetId;
  const projectId = data.projectId;

  return (
    project.id === targetId
    || project.id === projectApiId
    || project.id === projectId
    || project.data?.projectApiId === projectApiId
    || project.data?.projectApiId === targetId
    || project.data?.projectId === projectId
  );
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function normalizeProjectsResponse(list) {
  if (Array.isArray(list)) return list;
  if (Array.isArray(list?.projects)) return list.projects;
  if (Array.isArray(list?.items)) return list.items;
  return null;
}

function resolveServerProjectId(item) {
  return item?.project_id ?? item?.projectId ?? item?.id ?? "";
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
  const savedSession = readSavedSession();
  const shouldRestoreSession = shouldRestoreProjectSession(
    savedSession.screen,
    savedSession.projectApiId,
  );
  const [restoring, setRestoring] = useState(shouldRestoreSession);
  const [screen, setScreen] = useState(() => {
    if (shouldRestoreSession) {
      return savedSession.screen;
    }
    return savedSession.screen === "projects" ? "projects" : "login";
  });
  const [projects, setProjects] = useState([]);
  const [projectData, setProjectData] = useState(initialProjectData); //6/12 추가
  const [editingProjectId, setEditingProjectId] = useState("");
  const [activeProjectId, setActiveProjectId] = useState("");
  const [analysisState, setAnalysisState] = useState("idle");
  const [analysisErrorMessage, setAnalysisErrorMessage] = useState("");
  const [partnerMatchingTransition, setPartnerMatchingTransition] =
    useState("idle");
  const [partnerMatchingStep, setPartnerMatchingStep] =
    useState("creating-project");
  const [partnerMatchingError, setPartnerMatchingError] = useState("");
  const [projectsLoadError, setProjectsLoadError] = useState("");

  const buildProjectListItem = (data, id = data.projectId, overrides = {}) => ({
    id,
    name: data.projectName || `${data.companyName || "신규 고객"} 프로젝트`,
    status: overrides.status || data.workflowStatus || "진행 중",
    statusTone:
      overrides.statusTone ||
      getProjectStatusTone(overrides.status || data.workflowStatus),
    desc:
      overrides.desc || data.currentStage || data.usage || "요구사항 정리 중",
    meta: [
      data.projectDate || "일정 미정",
      data.budgetAmount ? `${data.budgetAmount} 이하` : "예산 미정",
      formatProjectSolutions(data, "솔루션 미정"),
    ],
    data: {
      ...data,
      ...(overrides.data ?? {}),
    },
  });

  const syncProjectList = (data, overrides = {}) => {
    const id = resolveProjectListId(data, editingProjectId);
    if (!id) return;
    const nextProject = buildProjectListItem(data, id, overrides);
    setProjects((current) => {
      const exists = current.some((project) => matchesProjectEntry(project, id, data));
      if (!exists) return [nextProject, ...current];
      return current.map((project) => (
        matchesProjectEntry(project, id, data) ? nextProject : project
      ));
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

  const hydrateProjectMatchData = async (apiProjectId, baseData) => {
    try {
      const matchesResponse = await fetchProjectMatches(apiProjectId);
      return {
        ...baseData,
        ...buildHydratedProjectFields(matchesResponse, baseData),
        matchHydrationAttempted: true,
      };
    } catch (error) {
      console.error("매칭 결과 조회 실패:", error);
      return {
        ...baseData,
        matchHydrationAttempted: true,
      };
    }
  };

  const loadProjects = async () => {
    try {
      const list = await fetchProjects();
      const items = normalizeProjectsResponse(list);

      if (!items) {
        console.error("프로젝트 목록 응답 형식 오류:", list);
        setProjectsLoadError("프로젝트 목록 응답 형식이 올바르지 않습니다.");
        setProjects([]);
        return [];
      }

      const mappedProjects = items
        .map((item) => {
          const projectId = resolveServerProjectId(item);
          if (!projectId) return null;

          const parsedFields = applyParsedRequestTextToProjectData(
            {},
            item.request_text,
          );

          return buildProjectListItem(
            {
              projectApiId: projectId,
              companyName: item.company_name ?? item.companyName ?? "",
              location: item.location ?? "",
              projectDate: item.deadline ?? item.projectDate ?? "",
              requestText: item.request_text ?? item.requestText ?? "",
              ...parsedFields,
              solutions: parsedFields.solutions ?? [],
              serverStatus: item.status,
              workflowStatus: getWorkflowStatusFromServerStatus(item.status),
              currentStage: getCurrentStageFromServerStatus(item.status),
            },
            projectId,
          );
        })
        .filter(Boolean);

      setProjectsLoadError("");
      setProjects((current) =>
        mappedProjects.map((mapped) => {
          const existing = current.find((p) => p.id === mapped.id);
          if (existing?.status === "완료") {
            return {
              ...mapped,
              status: "완료",
              statusTone: getProjectStatusTone("완료"),
              desc: existing.desc,
              data: {
                ...mapped.data,
                workflowStatus: "완료",
                currentStage: existing.data?.currentStage ?? "검토 완료",
              },
            };
          }
          return mapped;
        }),
      );
      return mappedProjects;
    } catch (error) {
      console.error("프로젝트 목록 조회 실패:", error);
      setProjectsLoadError(
        error.message
        || "프로젝트 목록을 불러오지 못했습니다. 백엔드(http://localhost:8000)가 실행 중인지 확인해주세요.",
      );
      setProjects([]);
      return [];
    }
  };

  const upsertProjectInList = (
    data,
    id = resolveProjectListId(data),
    overrides = {},
  ) => {
    if (!id) return;
    const nextProject = buildProjectListItem(data, id, overrides);
    setProjects((current) => {
      const exists = current.some((project) => matchesProjectEntry(project, id, data));
      if (!exists) return [nextProject, ...current];
      return current.map((project) => (
        matchesProjectEntry(project, id, data) ? nextProject : project
      ));
    });
    setActiveProjectId(id);
    setEditingProjectId(id);
  };

  const restoreProjectSession = async (savedProjectApiId, savedScreen) => {
    const loadedProjects = await loadProjects();
    const cachedProject = loadedProjects.find(
      (project) =>
        project.id === savedProjectApiId
        || project.data?.projectApiId === savedProjectApiId,
    );
    const localProjectData = {
      ...initialProjectData,
      ...(cachedProject?.data ?? {}),
      projectId: savedProjectApiId,
      projectApiId: savedProjectApiId,
      lastScreen: savedScreen,
    };

    const serverProject = await fetchProject(savedProjectApiId);
    let restoredProjectData = mergeServerProjectData(localProjectData, serverProject);

    if (shouldHydrateMatchData(restoredProjectData)) {
      restoredProjectData = await hydrateProjectMatchData(
        savedProjectApiId,
        restoredProjectData,
      );
    }

    const nextScreen = resolveRestoredScreen(restoredProjectData, savedScreen);
    upsertProjectInList(restoredProjectData, savedProjectApiId);
    setProjectData(restoredProjectData);
    setScreen(nextScreen);
    persistAppSession(nextScreen, savedProjectApiId);
    return nextScreen;
  };

  const goToProjects = async () => {
    await loadProjects();
    setScreen("projects");
    persistAppSession("projects");
  };

  const goHome = async () => {
    await loadProjects();
    setScreen("projects");
    persistAppSession("projects");
  };

  useEffect(() => {
    let ignore = false;

    (async () => {
      if (shouldRestoreSession) {
        try {
          await restoreProjectSession(
            savedSession.projectApiId,
            savedSession.screen,
          );
        } catch (error) {
          console.error("세션 복원 실패:", error);
          if (!ignore) {
            await loadProjects();
            setScreen("projects");
            persistAppSession("projects");
          }
        } finally {
          if (!ignore) {
            setRestoring(false);
          }
        }
        return;
      }

      if (savedSession.screen === "projects" || screen === "projects") {
        await loadProjects();
      }
      if (!ignore) {
        setRestoring(false);
      }
    })();

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    if (restoring) return;
    persistAppSession(screen, projectData.projectApiId);
  }, [restoring, screen, projectData.projectApiId]);

  useEffect(() => {
    let ignore = false;
    const apiProjectId = projectData.projectApiId;

    if (screen !== "dashboard" || !apiProjectId) return undefined;
    if (!shouldHydrateMatchData(projectData) || projectData.matchHydrationAttempted) {
      return undefined;
    }

    hydrateProjectMatchData(apiProjectId, projectData).then((nextData) => {
      if (!ignore) {
        setProjectData(nextData);
        syncProjectList(nextData);
      }
    });

    return () => {
      ignore = true;
    };
  }, [
    screen,
    projectData.projectApiId,
    projectData.matchId,
    projectData.quoteIds,
    projectData.cachedExplanation,
    projectData.matchHydrationAttempted,
    projectData.serverStatus,
    projectData.lastScreen,
  ]);
  const startNewProject = () => {
    setEditingProjectId("");
    setProjectData({ ...initialProjectData });
    setScreen("wizard");
  };

  const createDraftProject = async (draftData, shouldContinue = false) => {
    let projectApiId = null;
    try {
      const created = await createProject({
        company_name: draftData.companyName || "미입력",
        location: draftData.location || null,
        deadline: draftData.projectDate || null,
        request_text: draftData.usage || "",
      });
      projectApiId = created.project_id;
    } catch (error) {
      console.error("프로젝트 생성 실패:", error);
    }

    const projectId = projectApiId || `PV-${new Date().getFullYear()}-${String(Date.now()).slice(-4)}`;
    const nextData = {
      ...initialProjectData,
      ...draftData,
      projectId,
      projectApiId,
      currentStage: draftData.currentStage || "요구사항",
      workflowStatus: "진행 중",
      lastScreen: "requirements",
    };

    upsertProjectInList(nextData, projectApiId || projectId, {
      status: "진행 중",
      statusTone: "blue",
      desc: shouldContinue ? "요구사항 작성 중" : "요구사항 정리 중",
    });
    setProjectData(nextData);
    setActiveProjectId(projectId);
    setEditingProjectId(projectId);

    if (shouldContinue) {
      setScreen("requirements");
    }
  };

  const editProject = async (project) => {
    const localProjectData = { ...initialProjectData, ...project.data };
    setEditingProjectId(project.id);
    setActiveProjectId(project.id);
    setProjectData(localProjectData);

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
      } catch (error) {
        console.error("프로젝트 수정 화면 진입 중 서버 상태 조회 실패:", error);
      }
    }

    setScreen("requirements");
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
          const nextProjectData = shouldHydrateMatchData(restoredProjectData)
            ? await hydrateProjectMatchData(apiProjectId, restoredProjectData)
            : restoredProjectData;
          const nextScreen = getScreenFromProject(nextProjectData);
          setProjectData(nextProjectData);
          upsertProjectInList(nextProjectData, apiProjectId);
          setScreen(nextScreen);
          persistAppSession(nextScreen, apiProjectId);
          return;
        } catch (error) {
          setAnalysisErrorMessage(
            error.message || "프로젝트 상태를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
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

  const buildProjectRequest = (data) => buildProjectRequestPayload(data);

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
        throw new Error("프로젝트 정보를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.");
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
          "요구사항 저장 또는 공급사 추천 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
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
        error.message || "AI 분석 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
      );
      setAnalysisState("error");
    }
  };

  if (restoring) {
    return (
      <div aria-busy="true" aria-live="polite" className="app-shell app-restoring">
        <p>프로젝트를 불러오는 중입니다...</p>
      </div>
    );
  }

  if (screen === "login") {
    return <LoginPage onLogin={goToProjects} />;
  }

  //6/12 백엔드 작업에서 수정
  if (screen === "projects") {
    return (
      <ProjectListPage
        loadError={projectsLoadError}
        projects={projects}
        onCreate={startNewProject}
        onCreateDraft={createDraftProject}
        onDeleteProjects={deleteProjects}
        onEditProject={editProject}
        onOpenDashboard={openProjectFromList}
        onReloadProjects={loadProjects}
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
          onGoHome={goHome}
          onNext={startPartnerMatchingFromRequirements}
          onProjectDataChange={updateProjectData}
          onSaveDraft={() =>
            saveCurrentProjectScreen("requirements", {
              currentStage: "요구사항",
              workflowStatus: "진행 중",
            })
          }
          onAutoSave={async (data) => {
            if (!projectData.projectApiId) return;
            try {
              await updateProject(projectData.projectApiId, data);
            } catch (error) {
              console.error("자동저장 실패:", error);
            }
          }}
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
          category={formatProjectSolutions(projectData, "미선택")}
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
        onGoHome={goHome}
      />
    );
  }

  if (screen === "analysis") {
    return (
      <AnalysisPage
        errorMessage={analysisErrorMessage}
        onBack={() => setScreen("wizard")}
        onDashboard={completeAnalysis}
        onGoHome={goHome}
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
        onGoHome={goHome}
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
        onGoHome={goHome}
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
        onGoHome={goHome}
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

function resolveRestoredScreen(projectData, savedScreen) {
  const serverStatus = projectData.serverStatus ?? projectData.status;

  if (serverStatus === "created") {
    return "requirements";
  }

  if (serverStatus && KNOWN_SERVER_STATUSES.has(serverStatus)) {
    return getScreenFromProject(projectData);
  }

  return getScreenFromProject({
    ...projectData,
    lastScreen: savedScreen ?? projectData.lastScreen,
  });
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
  const workflowStatus =
    localData.workflowStatus === "완료"
      ? "완료"
      : getWorkflowStatusFromServerStatus(serverStatus, localData.workflowStatus);
  const requestText = serverProject?.request_text ?? localData.requestText;
  const parsedFields = applyParsedRequestTextToProjectData(
    localData,
    serverProject?.request_text,
  );

  return {
    ...localData,
    ...parsedFields,
    projectApiId: serverProject?.project_id ?? localData.projectApiId,
    serverStatus,
    companyName: serverProject?.company_name ?? localData.companyName,
    location: serverProject?.location ?? localData.location,
    projectDate: serverProject?.deadline ?? localData.projectDate,
    requestText,
    solutions:
      parsedFields.solutions?.length > 0
        ? parsedFields.solutions
        : normalizeProjectSolutions({ ...localData, ...parsedFields }),
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
  if (status === "partner_matched") return fallback;
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
