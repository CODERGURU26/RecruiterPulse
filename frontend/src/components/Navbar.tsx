import React, { useState, useEffect } from 'react';
import { Activity, Clock, ShieldCheck, BarChart3, Database } from 'lucide-react';

interface NavbarProps {
  activeTab: 'approval' | 'dashboard' | 'sources';
  setActiveTab: (tab: 'approval' | 'dashboard' | 'sources') => void;
  workspaceName?: string;
  hasPendingReport?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  workspaceName = 'Apex Staffing Solutions',
  hasPendingReport = true
}) => {
  const [time, setTime] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(
        now.toLocaleTimeString('en-IN', {
          timeZone: 'Asia/Kolkata',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true
        }) + ' IST'
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo & Workspace */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-brand-500/20">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-lg tracking-tight text-slate-900">
                  Recruiter<span className="text-brand-600">Pulse</span>
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">
                  v1.1
                </span>
              </div>
              <p className="text-xs text-slate-500 font-medium truncate max-w-[200px] sm:max-w-none">
                {workspaceName}
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex space-x-1 sm:space-x-2">
            <button
              onClick={() => setActiveTab('approval')}
              className={`relative px-3.5 py-2 rounded-lg text-sm font-semibold transition-all flex items-center space-x-2 ${
                activeTab === 'approval'
                  ? 'bg-brand-50 text-brand-700 shadow-sm ring-1 ring-brand-200'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              <span>MIS Approval</span>
              {hasPendingReport && (
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('dashboard')}
              className={`px-3.5 py-2 rounded-lg text-sm font-semibold transition-all flex items-center space-x-2 ${
                activeTab === 'dashboard'
                  ? 'bg-brand-50 text-brand-700 shadow-sm ring-1 ring-brand-200'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              <span>Management View</span>
            </button>

            <button
              onClick={() => setActiveTab('sources')}
              className={`px-3.5 py-2 rounded-lg text-sm font-semibold transition-all flex items-center space-x-2 ${
                activeTab === 'sources'
                  ? 'bg-brand-50 text-brand-700 shadow-sm ring-1 ring-brand-200'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Database className="w-4 h-4" />
              <span>Spreadsheets & Mapping</span>
            </button>
          </nav>

          {/* Live IST Clock */}
          <div className="hidden md:flex items-center space-x-2 px-3 py-1.5 bg-slate-100 rounded-lg text-xs font-semibold text-slate-700">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span>{time}</span>
          </div>
        </div>
      </div>
    </header>
  );
};

