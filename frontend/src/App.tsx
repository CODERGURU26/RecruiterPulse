import React, { useCallback, useEffect, useState } from 'react';
import { Navbar } from './components/Navbar';
import { ApprovalScreen } from './pages/ApprovalScreen';
import { ManagementDashboard } from './pages/ManagementDashboard';
import { DataSourcesScreen } from './pages/DataSourcesScreen';
import { HourlyReport, Workspace } from './types';
import { api, DEFAULT_WORKSPACE_ID } from './services/api';

type AppTab = 'approval' | 'dashboard' | 'sources';

export function App() {
  const [activeTab, setActiveTab] = useState<AppTab>('approval');
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [report, setReport] = useState<HourlyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const currentWorkspace = await api.getWorkspace(DEFAULT_WORKSPACE_ID);
      setWorkspace(currentWorkspace);
      const pending = await api.getPendingReport(currentWorkspace.id);
      const latestApproved = pending ? null : await api.getLatestApprovedReport(currentWorkspace.id);
      setReport(pending || latestApproved);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Unable to load workspace data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const handleTabChange = async (tab: AppTab) => {
    setActiveTab(tab);
    if (!workspace || tab === 'sources') return;

    try {
      const nextReport = tab === 'approval'
        ? await api.getPendingReport(workspace.id)
        : await api.getLatestApprovedReport(workspace.id);
      setReport(nextReport);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Unable to refresh reports.');
    }
  };

  if (loading || !workspace) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <div className="max-w-md text-center space-y-4">
          {loading && <div className="w-10 h-10 mx-auto border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin" />}
          <p className="text-sm font-semibold text-slate-600">
            {loading ? 'Connecting to RecruiterPulse...' : loadError || 'Workspace is unavailable.'}
          </p>
          {!loading && (
            <button onClick={() => void loadWorkspace()} className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-semibold">
              Retry connection
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col text-slate-900">
      <Navbar
        activeTab={activeTab}
        setActiveTab={handleTabChange}
        workspaceName={workspace.name}
        hasPendingReport={report?.status === 'DRAFT_PENDING_APPROVAL'}
      />

      <main className="flex-1 pb-16">
        {loadError && (
          <div role="alert" className="max-w-7xl mx-auto mt-4 px-4 text-sm text-rose-700">
            {loadError}
          </div>
        )}
        {activeTab === 'approval' && (
          report
            ? <ApprovalScreen report={report} onReportUpdate={setReport} />
            : <EmptyReportsMessage message="There are no reports awaiting approval. Upload a recruiter spreadsheet to generate one." />
        )}
        {activeTab === 'dashboard' && (
          report
            ? <ManagementDashboard report={report} />
            : <EmptyReportsMessage message="No approved report is available yet. Upload and approve a recruiter spreadsheet to see management analytics." />
        )}
        {activeTab === 'sources' && (
          <DataSourcesScreen
            workspaceId={workspace.id}
            serviceAccountEmail={workspace.service_account_email}
            onNavigateToApproval={() => void handleTabChange('approval')}
          />
        )}
      </main>

      <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-400">
        RecruiterPulse v1.1 — B2B Recruitment MIS Automation & Productivity Intelligence (India)
      </footer>
    </div>
  );
}

const EmptyReportsMessage: React.FC<{ message: string }> = ({ message }) => (
  <div className="max-w-4xl mx-auto px-4 py-16 text-center">
    <h1 className="text-xl font-bold text-slate-900">No report data yet</h1>
    <p className="text-sm text-slate-500 mt-2">{message}</p>
  </div>
);

export default App;
