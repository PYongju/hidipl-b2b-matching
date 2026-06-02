import { useState } from 'react';
import LoginPage from './pages/LoginPage';
import ProjectListPage from './pages/ProjectListPage';
import ProjectCreatePage from './pages/ProjectCreatePage';
import AnalysisPage from './pages/AnalysisPage';
import DashboardPage from './pages/DashboardPage';
import { createProject, runProjectMatch, uploadProjectQuotes } from './api/apiClient';
import { shouldUseMockApi } from './api/apiMode';
import { initialProjectData, sampleProjects, makeProjectFromData } from './data/mockProjects';

export default function App() {
  const [screen, setScreen] = useState('login');
  const [projectData, setProjectData] = useState(initialProjectData);
  const [projects, setProjects] = useState(sampleProjects);
  const [editingProjectId, setEditingProjectId] = useState('');
  const [activeProjectId, setActiveProjectId] = useState(sampleProjects[0]?.id ?? '');
  const [analysisState, setAnalysisState] = useState('idle');
  const [analysisErrorMessage, setAnalysisErrorMessage] = useState('');

  const startNewProject = () => {
    setEditingProjectId('');
    setProjectData({ ...initialProjectData });
    setScreen('wizard');
  };

  const editProject = (project) => {
    setEditingProjectId(project.id);
    setProjectData({ ...initialProjectData, ...project.data });
    setScreen('wizard');
  };

  const openDashboard = (projectId) => {
    const project = projects.find((item) => item.id === projectId);
    if (project) {
      setProjectData({ ...initialProjectData, ...project.data });
      setActiveProjectId(project.id);
    }
    setScreen('dashboard');
  };

  const deleteProjects = (projectIds) => {
    setProjects((current) => current.filter((project) => !projectIds.includes(project.id)));
    if (projectIds.includes(activeProjectId)) {
      setActiveProjectId('');
    }
  };

  const completeAnalysis = () => {
    const id = editingProjectId || undefined;
    const nextProject = makeProjectFromData(projectData, id);
    setProjects((current) => {
      const exists = current.some((project) => project.id === nextProject.id);
      return exists
        ? current.map((project) => (project.id === nextProject.id ? nextProject : project))
        : [nextProject, ...current];
    });
    setActiveProjectId(nextProject.id);
    setEditingProjectId(nextProject.id);
    setScreen('dashboard');
  };

  const buildProjectRequest = (data) => ({
    company_name: data.companyName,
    location: data.location,
    project_name: data.projectName,
    current_stage: data.currentStage,
    project_date: data.projectDate,
    use_case: data.usage,
    display_size: data.displaySize,
    quantity: Number(data.quantity || 0),
    budget_amount: Number(String(data.budgetAmount || '').replace(/,/g, '')) || null,
    operation_time: data.operationTime,
    review_preset: data.reviewPreset,
  });

  const startAnalysisFlow = async () => {
    setScreen('analysis');
    setAnalysisState('loading');
    setAnalysisErrorMessage('');

    try {
      if (shouldUseMockApi) {
        const mockProjectApiId = projectData.projectApiId || projectData.projectId || `mock-${Date.now()}`;
        const mockMatchId = projectData.matchId || `match-${Date.now()}`;
        const mockQuoteIds = (projectData.quoteFiles ?? []).map((file, index) => (
          `mock-quote-${index + 1}-${file.name}`
        ));

        setProjectData((current) => ({
          ...current,
          projectApiId: mockProjectApiId,
          quoteIds: mockQuoteIds,
          matchId: mockMatchId,
        }));
        setAnalysisState('ready');
        return;
      }

      const createdProject = await createProject(buildProjectRequest(projectData));
      const projectApiId = createdProject.project_id ?? createdProject.id;
      const uploadResult = await uploadProjectQuotes(projectApiId, projectData.quoteFiles ?? []);
      const quoteIds = uploadResult.quote_ids ?? uploadResult.quotes?.map((quote) => quote.quote_id ?? quote.id) ?? [];
      const matchResult = await runProjectMatch(projectApiId);
      const matchId = matchResult.match_id ?? matchResult.id;

      setProjectData((current) => ({
        ...current,
        projectApiId,
        quoteIds,
        matchId,
        quoteUploadResult: uploadResult,
      }));
      setAnalysisState('ready');
    } catch (error) {
      setAnalysisErrorMessage(error.message || 'AI 분석 실행 중 오류가 발생했습니다.');
      setAnalysisState('error');
    }
  };

  if (screen === 'login') {
    return <LoginPage onLogin={() => setScreen('projects')} />;
  }

  if (screen === 'projects') {
    return (
      <ProjectListPage
        projects={projects}
        onCreate={startNewProject}
        onDeleteProjects={deleteProjects}
        onEditProject={editProject}
        onOpenDashboard={openDashboard}
      />
    );
  }

  if (screen === 'wizard') {
    return (
      <ProjectCreatePage
        projectData={projectData}
        onProjectDataChange={setProjectData}
        onAnalyze={startAnalysisFlow}
        onBack={() => setScreen('projects')}
      />
    );
  }

  if (screen === 'analysis') {
    return (
      <AnalysisPage
        errorMessage={analysisErrorMessage}
        onBack={() => setScreen('wizard')}
        onDashboard={completeAnalysis}
        onRetry={startAnalysisFlow}
        state={analysisState}
      />
    );
  }

  return <DashboardPage projectData={projectData} onGoProjects={() => setScreen('projects')} />;
}
