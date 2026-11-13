import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { ApprovalScreen } from './pages/ApprovalScreen';
import { ManagementDashboard } from './pages/ManagementDashboard';
import { DataSourcesScreen } from './pages/DataSourcesScreen';
import { HourlyReport } from './types';
import { api } from './services/api';

export function App() {
  const [activeTab, setActiveTab] = useState<'approval' | 'dashboard' | 'sources'>('approval');
  const [report, setReport] = useState<HourlyReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const rep = await api.getPendingReport();
        setReport(rep);
      } catch (err) {
        console.error('Failed to load initial report:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleTabChange = async (tab: 'approval' | 'dashboard' | 'sources') => {
    setActiveTab(tab);
    if (tab === 'approval' || tab === 'dashboard') {
      try {
        const rep = await api.getPendingReport();
        if (rep) setReport(rep);
      } catch (e) {
        // use existing
      }
    }
  };

  if (loading || !report) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex flex-col items-center space-y-3">
          <div className="w-10 h-10 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin"></div>
          <p className="text-sm font-semibold text-slate-500">Loading RecruiterPulse...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col text-slate-900">
      <Navbar
        activeTab={activeTab}
        setActiveTab={handleTabChange}
        workspaceName="Apex Staffing Solutions"
        hasPendingReport={report.status === 'DRAFT_PENDING_APPROVAL'}
      />

      <main className="flex-1 pb-16">
        {activeTab === 'approval' && (
          <ApprovalScreen
            report={report}
            onReportUpdate={(updated) => setReport(updated)}
          />
        )}
        {activeTab === 'dashboard' && (
          <ManagementDashboard report={report} />
        )}
        {activeTab === 'sources' && (
          <DataSourcesScreen
            onNavigateToApproval={() => handleTabChange('approval')}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-400">
        RecruiterPulse v1.1 — B2B Recruitment MIS Automation & Productivity Intelligence (India)
      </footer>
    </div>
  );

}

export default App;

