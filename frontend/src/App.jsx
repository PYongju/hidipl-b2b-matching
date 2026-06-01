import { useState } from 'react';
import LoginPage from './pages/LoginPage';
import ProjectListPage from './pages/ProjectListPage';
import ProjectCreatePage from './pages/ProjectCreatePage';
import AnalysisPage from './pages/AnalysisPage';
import DashboardPage from './pages/DashboardPage';
import { initialProjectData, sampleProjects, makeProjectFromData } from './data/mockProjects';

export default function App() {
  const [screen, setScreen] = useState('login');
  const [projectData, setProjectData] = useState(initialProjectData);
  const [projects, setProjects] = useState(sampleProjects);
  const [editingProjectId, setEditingProjectId] = useState('');
  const [activeProjectId, setActiveProjectId] = useState(sampleProjects[0]?.id ?? '');

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
        onAnalyze={() => setScreen('analysis')}
        onBack={() => setScreen('projects')}
      />
    );
  }

  if (screen === 'analysis') {
    return <AnalysisPage onDashboard={completeAnalysis} />;
  }

  return <DashboardPage projectData={projectData} onGoProjects={() => setScreen('projects')} />;
}
