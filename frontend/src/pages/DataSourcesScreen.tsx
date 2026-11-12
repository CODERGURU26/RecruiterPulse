import React, { useState } from 'react';
import {
  Database,
  Share2,
  Copy,
  Check,
  FileSpreadsheet,
  Upload,
  CheckCircle2,
  AlertCircle,
  Users,
  Plus
} from 'lucide-react';

export const DataSourcesScreen: React.FC = () => {
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [sheetUrl, setSheetUrl] = useState('');
  const [selectedRecruiter, setSelectedRecruiter] = useState('Priya Sharma');
  const serviceAccount = 'sync@recruiterpulse.iam.gserviceaccount.com';

  const handleCopyEmail = () => {
    navigator.clipboard.writeText(serviceAccount);
    setCopiedEmail(true);
    setTimeout(() => setCopiedEmail(false), 2000);
  };

  const sampleMappings = [
    { field: 'Activity Date', detected: 'Calling Date', confidence: 0.95, sample: '12/11/2026', confirmed: true },
    { field: 'Call Status', detected: 'Call Outcome', confidence: 0.92, sample: 'Connected, RNR, Switched off', confirmed: true },
    { field: 'Candidate Identifier', detected: 'Mobile Number', confidence: 0.88, sample: '9876543210', confirmed: true },
    { field: 'Job Role / Profile', detected: 'Requirement', confidence: 0.90, sample: 'Java Developer, React Lead', confirmed: true }
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Spreadsheets & Data Sources</h1>
        <p className="text-sm text-slate-500 mt-1">
          Connect your team's Google Sheets or upload files. RecruiterPulse auto-maps columns without altering your workflow.
        </p>
      </div>

      {/* Service Account Instruction Card */}
      <div className="bg-gradient-to-r from-brand-900 to-indigo-900 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-500/30 text-brand-200 border border-brand-400/30">
              <Share2 className="w-3.5 h-3.5 mr-1" />
              Google Service Account Model (Zero-OAuth Friction)
            </span>
            <h2 className="text-xl font-bold tracking-tight">Share spreadsheets with your dedicated agent</h2>
            <p className="text-xs text-indigo-200 max-w-2xl">
              No individual recruiter logins required. Simply share your recruiter calling Google Sheets with <strong>Viewer</strong> access to this email:
            </p>
          </div>

          <button
            onClick={handleCopyEmail}
            className="inline-flex items-center space-x-2 px-4 py-2.5 bg-white text-brand-900 hover:bg-slate-100 rounded-xl font-bold text-xs shadow-md transition-all active:scale-95 self-start md:self-auto"
          >
            {copiedEmail ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4 text-brand-600" />}
            <span>{copiedEmail ? 'Copied Email!' : 'Copy Service Account Email'}</span>
          </button>
        </div>

        <div className="mt-4 p-3 bg-black/20 rounded-xl flex items-center justify-between text-xs font-mono text-indigo-200">
          <span>{serviceAccount}</span>
          <span className="text-[10px] text-emerald-400 font-semibold uppercase tracking-wider">Read-Only Safe</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Connect Google Sheet Form */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center space-x-2 text-slate-900 font-bold">
            <FileSpreadsheet className="w-5 h-5 text-brand-600" />
            <h2>Connect Recruiter Google Sheet</h2>
          </div>
          <p className="text-xs text-slate-500">
            Paste the public or shared Google Sheets link and assign it to a recruiter roster profile.
          </p>

          <div className="space-y-3 pt-2">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Assign to Recruiter
              </label>
              <select
                value={selectedRecruiter}
                onChange={(e) => setSelectedRecruiter(e.target.value)}
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
              >
                <option>Priya Sharma</option>
                <option>Rahul Verma</option>
                <option>Amit Patel</option>
                <option>Agency Master Sheet (All Recruiters)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Google Spreadsheet URL
              </label>
              <input
                type="url"
                value={sheetUrl}
                onChange={(e) => setSheetUrl(e.target.value)}
                placeholder="https://docs.google.com/spreadsheets/d/1BxiM.../edit"
                className="w-full p-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
              />
            </div>

            <button
              onClick={() => {
                if (sheetUrl) alert('Connected sheet and triggered column auto-detection!');
              }}
              className="w-full py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-bold text-sm rounded-xl shadow-sm transition-all"
            >
              Analyze & Connect Sheet
            </button>
          </div>
        </div>

        {/* Offline File Upload (.xlsx / .csv) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center space-x-2 text-slate-900 font-bold">
              <Upload className="w-5 h-5 text-brand-600" />
              <h2>Upload Offline Spreadsheet (.xlsx, .csv)</h2>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              For teams working with local Excel files. Generates on-demand MIS reports upon upload.
            </p>
          </div>

          <div className="border-2 border-dashed border-slate-200 hover:border-brand-500 rounded-2xl p-8 text-center transition-colors cursor-pointer bg-slate-50/50">
            <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
            <p className="text-sm font-semibold text-slate-700">Drag & drop your Excel or CSV file here</p>
            <p className="text-xs text-slate-400 mt-1">Supports .xlsx, .xls, and .csv files up to 25MB</p>
          </div>

          <div className="flex items-center space-x-2 text-xs text-slate-400">
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            <span>DPDP Act Compliant: Candidate contacts purged immediately after aggregation.</span>
          </div>
        </div>
      </div>

      {/* Column Auto-Detection Wizard Preview */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900">Active Column Mappings</h2>
            <p className="text-xs text-slate-500">
              Heuristic detector maps varied agency terminology to standardized fields.
            </p>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-lg border border-emerald-200">
            Auto-Confirmed ($\ge 85\%$ Confidence)
          </span>
        </div>

        <div className="divide-y divide-slate-100">
          {sampleMappings.map((m, idx) => (
            <div key={idx} className="p-4 px-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50 transition-colors">
              <div className="space-y-0.5">
                <div className="flex items-center space-x-2">
                  <span className="font-bold text-sm text-slate-900">{m.field}</span>
                  <span className="text-xs text-slate-400 font-mono">mapped to</span>
                  <span className="px-2 py-0.5 bg-brand-50 text-brand-700 rounded text-xs font-bold border border-brand-200">
                    "{m.detected}"
                  </span>
                </div>
                <p className="text-xs text-slate-400">Sample preview: {m.sample}</p>
              </div>

              <div className="flex items-center space-x-3">
                <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-1 rounded">
                  {(m.confidence * 100).toFixed(0)}% Confidence
                </span>
                <span className="text-xs font-semibold text-slate-500 cursor-pointer hover:text-brand-600">
                  Edit Mapping
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

