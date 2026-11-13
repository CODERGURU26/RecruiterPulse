import React, { useEffect, useState, useRef } from 'react';
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
  Plus,
  FileCheck,
  Sparkles,
  ArrowRight,
  TrendingUp,
  AlertTriangle
} from 'lucide-react';
import { api } from '../services/api';
import { LiveDataSource, Recruiter } from '../types';

interface DataSourcesScreenProps {
  workspaceId: string;
  serviceAccountEmail?: string;
  onNavigateToApproval?: () => void;
}

const AUTO_DETECT_RECRUITERS = '__auto__';
const ALL_RECRUITERS = 'Agency Master Sheet (All Recruiters)';

export const DataSourcesScreen: React.FC<DataSourcesScreenProps> = ({
  workspaceId,
  serviceAccountEmail,
  onNavigateToApproval
}) => {
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [sheetUrl, setSheetUrl] = useState('');
  const [liveRecruiterName, setLiveRecruiterName] = useState('');
  const [selectedRecruiter, setSelectedRecruiter] = useState(AUTO_DETECT_RECRUITERS);
  const [recruiters, setRecruiters] = useState<Recruiter[]>([]);
  const [liveSources, setLiveSources] = useState<LiveDataSource[]>([]);
  const [isRegisteringLiveSheet, setIsRegisteringLiveSheet] = useState(false);
  const [liveSyncMessage, setLiveSyncMessage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<any | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const serviceAccount = serviceAccountEmail || 'Service account not configured';

  useEffect(() => {
    api.getRecruiters(workspaceId)
      .then(setRecruiters)
      .catch((err: Error) => setErrorMessage(`Could not load recruiter roster: ${err.message}`));
    api.getDataSources(workspaceId)
      .then(setLiveSources)
      .catch((err: Error) => setErrorMessage(`Could not load live sheets: ${err.message}`));
  }, [workspaceId]);

  const handleCopyEmail = () => {
    if (!serviceAccountEmail) return;
    navigator.clipboard.writeText(serviceAccount);
    setCopiedEmail(true);
    setTimeout(() => setCopiedEmail(false), 2000);
  };

  const handleFile = async (file: File) => {
    if (!file) return;
    setErrorMessage(null);
    setIsUploading(true);

    try {
      const result = await api.processRealFile(
        file,
        workspaceId,
        selectedRecruiter === AUTO_DETECT_RECRUITERS ? undefined : selectedRecruiter
      );
      setUploadResult(result);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to process spreadsheet.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleGoogleSheet = async () => {
    setErrorMessage(null);
    setIsUploading(true);
    try {
      const result = await api.processGoogleSheet(
        sheetUrl.trim(),
        workspaceId,
        selectedRecruiter === AUTO_DETECT_RECRUITERS
          ? liveRecruiterName.trim() || undefined
          : selectedRecruiter
      );
      setUploadResult(result);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to read Google Sheet.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleRegisterLiveSheet = async () => {
    setErrorMessage(null);
    setLiveSyncMessage(null);
    if (!liveRecruiterName.trim()) {
      setErrorMessage('Enter the recruiter who owns the selected call-log tab.');
      return;
    }

    setIsRegisteringLiveSheet(true);
    try {
      const source = await api.registerGoogleSheet(
        workspaceId,
        liveRecruiterName.trim(),
        sheetUrl.trim()
      );
      const report = await api.triggerSync(workspaceId);
      setLiveSources(await api.getDataSources(workspaceId));
      setLiveSyncMessage(
        `${source.name} is registered. Initial sync found ${report.summary_totals.total_calls} calls; sheets refresh every 15 minutes.`
      );
      onNavigateToApproval?.();
    } catch (err) {
      let message = err instanceof Error
        ? `Live sheet setup/sync failed: ${err.message}`
        : 'Live sheet setup/sync failed.';
      try {
        setLiveSources(await api.getDataSources(workspaceId));
      } catch (refreshError) {
        const detail = refreshError instanceof Error ? refreshError.message : 'unknown error';
        message += ` Also could not refresh the source list: ${detail}`;
      }
      setErrorMessage(message);
    } finally {
      setIsRegisteringLiveSheet(false);
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = () => {
    setIsDragging(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const onFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Spreadsheets & Data Sources</h1>
        <p className="text-sm text-slate-500 mt-1">
          Import a Google Sheets tab or upload an Excel/CSV file. RecruiterPulse detects call columns and creates a draft report from the actual rows.
        </p>
      </div>

      {/* Service Account Instruction Card */}
      <div className="bg-gradient-to-r from-brand-900 to-indigo-900 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-500/30 text-brand-200 border border-brand-400/30">
              <Share2 className="w-3.5 h-3.5 mr-1" />
              Read-only Google Sheets import
            </span>
            <h2 className="text-xl font-bold tracking-tight">Share private sheets with the configured service account</h2>
            <p className="text-xs text-indigo-200 max-w-2xl">
              For private sheets, share with this service account after its credentials are configured on the backend:
            </p>
          </div>

          <button
            onClick={handleCopyEmail}
            disabled={!serviceAccountEmail}
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

      {/* Ingestion Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Google Sheets import */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center space-x-2 text-slate-900 font-bold">
            <FileSpreadsheet className="w-5 h-5 text-brand-600" />
            <h2>Import a Google Sheets tab</h2>
          </div>
          <p className="text-xs text-slate-500">
            Paste a Google Sheets URL. This imports the selected tab once and creates or updates the day's draft report.
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
                <option value={AUTO_DETECT_RECRUITERS}>Auto-detect from sheet/tab</option>
                <option value={ALL_RECRUITERS}>Process all recruiters in sheet</option>
                {recruiters.map((recruiter) => (
                  <option key={recruiter.id} value={recruiter.full_name}>{recruiter.full_name}</option>
                ))}
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
              onClick={() => void handleGoogleSheet()}
              disabled={!sheetUrl.trim() || isUploading}
              className="w-full py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-bold text-sm rounded-xl shadow-sm transition-all"
            >
              {isUploading ? 'Analyzing sheet...' : 'Analyze Google Sheet'}
            </button>

            <div className="border-t border-slate-100 pt-4 space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Recruiter owning this tab
                </label>
                <input
                  type="text"
                  value={liveRecruiterName}
                  onChange={(e) => setLiveRecruiterName(e.target.value)}
                  placeholder="For example, Tanmay"
                  className="w-full p-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
                />
              </div>
              <p className="text-xs text-slate-500">
                Select the recruiter&apos;s call-log tab before copying its URL; it must contain a gid. Do not register Naukri, Internshala, or daily-summary tabs as recruiters.
              </p>
              <button
                onClick={() => void handleRegisterLiveSheet()}
                disabled={!sheetUrl.trim() || !liveRecruiterName.trim() || isRegisteringLiveSheet}
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm rounded-xl shadow-sm transition-all disabled:opacity-50"
              >
                {isRegisteringLiveSheet ? 'Registering and syncing...' : 'Enable 15-minute live sync'}
              </button>
              {liveSyncMessage && (
                <p role="status" className="text-xs font-semibold text-emerald-700">{liveSyncMessage}</p>
              )}
            </div>
          </div>
        </div>

        {/* Spreadsheet file upload */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center space-x-2 text-slate-900 font-bold">
              <Upload className="w-5 h-5 text-brand-600" />
              <h2>Upload Spreadsheet (.xlsx, .xls, .csv)</h2>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Drag and drop or browse to analyze your actual recruiter data and create a draft report.
            </p>
          </div>

          {/* Hidden File Input */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={onFileInputChange}
            accept=".csv, .xlsx, .xls"
            className="hidden"
          />

          {/* Interactive Dropzone */}
          <div
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer ${
              isDragging
                ? 'border-brand-500 bg-brand-50 scale-[1.01]'
                : 'border-slate-200 hover:border-brand-500 hover:bg-slate-50/80 bg-slate-50/50'
            }`}
          >
            {isUploading ? (
              <div className="flex flex-col items-center space-y-3 py-2">
                <div className="w-8 h-8 border-3 border-brand-200 border-t-brand-600 rounded-full animate-spin"></div>
                <p className="text-sm font-bold text-brand-700">Analyzing columns and calculating calling metrics...</p>
                <p className="text-xs text-slate-400">Filtering dates, running deduplication, classifying statuses...</p>
              </div>
            ) : (
              <>
                <Upload className="w-8 h-8 text-brand-600 mx-auto mb-2" />
                <p className="text-sm font-bold text-slate-800">
                  Click to browse or drag & drop your real recruiter sheet
                </p>
                <p className="text-xs text-slate-400 mt-1">Supports Excel (.xlsx, .xls) and CSV (.csv) files</p>
              </>
            )}
          </div>

          {errorMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-2 text-xs font-semibold text-rose-700">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="flex items-center space-x-2 text-xs text-slate-400">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
            <span>DPDP Act Compliant: Candidate names & phone numbers are purged immediately after calculation.</span>
          </div>
        </div>
      </div>

      {liveSources.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 space-y-3">
          <div>
            <h2 className="text-base font-bold text-slate-900">Registered live recruiter sheets</h2>
            <p className="text-xs text-slate-500 mt-1">The backend refreshes these tabs every 15 minutes while it is running.</p>
          </div>
          <div className="divide-y divide-slate-100">
            {liveSources.map((source) => (
              <div key={source.id} className="py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-sm">
                <span className="font-semibold text-slate-800">{source.name}</span>
                <span className={source.last_error_message ? 'text-rose-600 text-xs' : 'text-slate-500 text-xs'}>
                  {source.last_error_message
                    ? `Sync error: ${source.last_error_message}`
                    : source.last_synced_at
                      ? `Last synced ${new Date(source.last_synced_at).toLocaleString()}`
                      : source.sync_status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Uploaded File Processing Results Banner */}
      {uploadResult && (
        <div className="bg-emerald-50/80 border border-emerald-200 rounded-2xl p-6 shadow-sm space-y-5 animate-in fade-in duration-300">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center space-x-3">
              <div className="p-2.5 bg-emerald-600 text-white rounded-xl shadow-md shadow-emerald-500/20">
                <FileCheck className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-bold text-base text-slate-900">
                  Spreadsheet Successfully Analyzed: {uploadResult.filename}
                </h3>
                <p className="text-xs text-emerald-800 font-medium">
                  Processed for <strong>{uploadResult.recruiter_name}</strong> | Reporting Date: <strong>{uploadResult.reporting_date}</strong>
                </p>
              </div>
            </div>

            {onNavigateToApproval && (
              <button
                onClick={onNavigateToApproval}
                className="inline-flex items-center space-x-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl shadow-md shadow-emerald-600/20 transition-all self-start sm:self-auto active:scale-95"
              >
                <span>View in MIS Approval Dashboard</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Quick Metrics Cards from Real File */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-white p-4 rounded-xl border border-emerald-100 shadow-sm">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Calls Found</span>
              <p className="text-2xl font-extrabold text-slate-900 mt-1">{uploadResult.metrics.total_calls}</p>
              <p className="text-[11px] text-slate-400 mt-0.5">{uploadResult.total_rows_in_file} total rows parsed</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-emerald-100 shadow-sm">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Connected Calls</span>
              <p className="text-2xl font-extrabold text-emerald-600 mt-1">{uploadResult.metrics.connected_calls}</p>
              <p className="text-[11px] text-slate-400 mt-0.5">{uploadResult.metrics.not_connected_calls} not connected</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-emerald-100 shadow-sm">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Connected Rate</span>
              <p className="text-2xl font-extrabold text-brand-600 mt-1">{uploadResult.metrics.connected_rate}%</p>
              <p className="text-[11px] text-slate-400 mt-0.5">Conversion efficiency</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-emerald-100 shadow-sm">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Duplicates Purged</span>
              <p className="text-2xl font-extrabold text-amber-600 mt-1">{uploadResult.duplicates_removed}</p>
              <p className="text-[11px] text-slate-400 mt-0.5">Deduplication safeguard</p>
            </div>
          </div>

          {/* Multi-Recruiter Breakdown if Master Sheet */}
          {uploadResult.recruiters_processed && uploadResult.recruiters_processed.length > 1 && (
            <div className="bg-white rounded-xl border border-emerald-100 p-4 space-y-2">
              <span className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">
                Recruiters Detected in Sheet ({uploadResult.recruiters_processed.length})
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 pt-1">
                {uploadResult.recruiters_processed.map((r: any, idx: number) => (
                  <div key={idx} className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs flex justify-between items-center">
                    <div>
                      <p className="font-bold text-slate-800">{r.name}</p>
                      <p className="text-[11px] text-slate-500">{r.total_calls} calls ({r.connected_calls} conn)</p>
                    </div>
                    <span className="px-2 py-0.5 bg-brand-50 text-brand-700 rounded text-xs font-bold font-mono">
                      {r.connected_rate}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Unmapped Status Warning if applicable */}
          {uploadResult.unmapped_statuses && uploadResult.unmapped_statuses.length > 0 && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs flex items-center space-x-2 text-amber-800">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <span>
                <strong>Unmapped Statuses Detected:</strong> {uploadResult.unmapped_statuses.join(', ')} (defaulted to attempt for safety).
              </span>
            </div>
          )}
        </div>
      )}

      {/* Auto-Detected Column Mappings List */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              {uploadResult ? 'Columns Detected From Your File' : 'Standard Field Mappings'}
            </h2>
            <p className="text-xs text-slate-500">
              Heuristic detector recognizes variations in date, status, candidate, and role headers.
            </p>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-lg border border-emerald-200">
            Auto-Confirmed ($\ge 85\%$ Confidence)
          </span>
        </div>

        <div className="divide-y divide-slate-100">
          {uploadResult?.detected_columns ? (
            Object.entries(uploadResult.detected_columns).map(([field, item]: [string, any], idx: number) => (
              <div key={idx} className="p-4 px-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50 transition-colors">
                <div className="space-y-0.5">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-sm text-slate-900 capitalize">{field.replace('_', ' ')}</span>
                    <span className="text-xs text-slate-400 font-mono">mapped to</span>
                    <span className="px-2 py-0.5 bg-brand-50 text-brand-700 rounded text-xs font-bold border border-brand-200">
                      "{item.source_column || 'Not found'}"
                    </span>
                  </div>
                  {item.sample_values && item.sample_values.length > 0 && (
                    <p className="text-xs text-slate-400">Sample preview: {item.sample_values.join(', ')}</p>
                  )}
                </div>

                <div className="flex items-center space-x-3">
                  <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-1 rounded">
                    {(item.confidence * 100).toFixed(0)}% Confidence
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="p-6 text-sm text-slate-500">
              Upload a spreadsheet to see detected columns, confidence, and sample values.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
