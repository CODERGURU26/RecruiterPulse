import React, { useState } from 'react';
import {
  HourlyReport,
  RecruiterMetric
} from '../types';
import {
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  Calendar,
  AlertTriangle,
  Clock,
  Sparkles,
  UserCheck,
  TrendingUp,
  FileSpreadsheet,
  RefreshCw,
  Pencil,
  Save,
  X
} from 'lucide-react';
import { api } from '../services/api';

interface EditableMetric {
  id: string;
  job_roles: string;
  connected_calls: string;
  not_connected_calls: string;
  next_day_interviews: string;
}

interface ApprovalScreenProps {
  report: HourlyReport;
  onReportUpdate: (updated: HourlyReport) => void;
}

export const ApprovalScreen: React.FC<ApprovalScreenProps> = ({
  report,
  onReportUpdate
}) => {
  const [copied, setCopied] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [editableMetrics, setEditableMetrics] = useState<EditableMetric[] | null>(null);
  const [isSavingEdits, setIsSavingEdits] = useState(false);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleSyncNow = async () => {
    setIsSyncing(true);
    try {
      const updated = await api.triggerSync(report.workspace_id);
      onReportUpdate(updated);
      showToast('Live Sync Complete: registered recruiter sheets refreshed.');
    } catch (error) {
      showToast(error instanceof Error ? `Sync failed: ${error.message}` : 'Sync failed.');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleCopyWhatsApp = async () => {
    try {
      const text = await api.getWhatsAppText(report.id);
      await navigator.clipboard.writeText(text);
      setCopied(true);
      showToast('Copied WhatsApp summary to clipboard!');
      setTimeout(() => setCopied(false), 2500);
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Unable to copy the report.');
    }
  };

  const handleApprove = async () => {
    setIsApproving(true);
    try {
      const updated = await api.approveReport(report.id);
      onReportUpdate(updated);
      showToast('Report Approved & Published to Management Dashboard!');
    } catch (error) {
      showToast(error instanceof Error ? `Approval failed: ${error.message}` : 'Approval failed.');
    } finally {
      setIsApproving(false);
    }
  };

  const handleRejectConfirm = async () => {
    if (!rejectReason.trim()) return;
    setIsRejecting(true);
    try {
      const updated = await api.rejectReport(report.id, rejectReason);
      onReportUpdate(updated);
      setShowRejectModal(false);
      showToast('Report rejected and flagged for sheet re-sync.');
    } catch (error) {
      showToast(error instanceof Error ? `Rejection failed: ${error.message}` : 'Rejection failed.');
    } finally {
      setIsRejecting(false);
    }
  };

  const handleStartEditing = () => {
    setEditableMetrics(report.metrics.map((metric) => ({
      id: metric.id,
      job_roles: metric.job_roles.join(', '),
      connected_calls: String(metric.connected_calls),
      not_connected_calls: String(metric.not_connected_calls),
      next_day_interviews: String(metric.next_day_interviews)
    })));
  };

  const handleCancelEditing = () => setEditableMetrics(null);

  const handleSaveEdits = async () => {
    if (!editableMetrics) return;
    const parsedMetrics = editableMetrics.map((metric) => ({
      id: metric.id,
      job_roles: metric.job_roles.split(',').map((role) => role.trim()).filter(Boolean),
      connected_calls: Number(metric.connected_calls),
      not_connected_calls: Number(metric.not_connected_calls),
      next_day_interviews: Number(metric.next_day_interviews)
    }));

    if (parsedMetrics.some((metric) =>
      [metric.connected_calls, metric.not_connected_calls, metric.next_day_interviews]
        .some((value) => !Number.isInteger(value) || value < 0)
    )) {
      showToast('Call and interview counts must be non-negative whole numbers.');
      return;
    }

    setIsSavingEdits(true);
    try {
      const updated = await api.editDraftReport(report.id, parsedMetrics);
      onReportUpdate(updated);
      setEditableMetrics(null);
      showToast('Report edits saved and totals recalculated.');
    } catch (error) {
      showToast(error instanceof Error ? `Could not save edits: ${error.message}` : 'Could not save report edits.');
    } finally {
      setIsSavingEdits(false);
    }
  };

  const isPending = report.status === 'DRAFT_PENDING_APPROVAL';
  const isApproved = report.status === 'APPROVED';
  const isRejected = report.status === 'REJECTED';
  const editById = new Map((editableMetrics || []).map((metric) => [metric.id, metric]));
  const displayedMetrics = report.metrics.map((metric) => {
    const edit = editById.get(metric.id);
    if (!edit) return metric;
    const connected = Number(edit.connected_calls) || 0;
    const notConnected = Number(edit.not_connected_calls) || 0;
    const total = connected + notConnected;
    return {
      ...metric,
      job_roles: edit.job_roles.split(',').map((role) => role.trim()).filter(Boolean),
      connected_calls: connected,
      not_connected_calls: notConnected,
      total_calls: total,
      connected_rate: total ? Math.round((connected / total) * 10000) / 100 : 0,
      next_day_interviews: Number(edit.next_day_interviews) || 0
    };
  });
  const displayedSummary = displayedMetrics.reduce((totals, metric) => {
    if (metric.total_calls > 0) {
      totals.connected_calls += metric.connected_calls;
      totals.not_connected_calls += metric.not_connected_calls;
      totals.total_calls += metric.total_calls;
      totals.next_day_interviews += metric.next_day_interviews + metric.unassigned_interviews;
      totals.active_recruiters_count += 1;
    }
    return totals;
  }, {
    connected_calls: 0,
    not_connected_calls: 0,
    total_calls: 0,
    connected_rate: 0,
    next_day_interviews: 0,
    active_recruiters_count: 0
  });
  displayedSummary.connected_rate = displayedSummary.total_calls
    ? Math.round((displayedSummary.connected_calls / displayedSummary.total_calls) * 10000) / 100
    : 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white px-5 py-3 rounded-xl shadow-2xl flex items-center space-x-3 text-sm font-medium animate-bounce">
          <Check className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Hourly MIS Review & Approval
            </h1>
            {isPending && (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
                <Clock className="w-3.5 h-3.5 mr-1" />
                Slot {report.hour_slot} IST — Pending Approval
              </span>
            )}
            {isApproved && (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                Slot {report.hour_slot} IST — Approved
              </span>
            )}
            {isRejected && (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200">
                <XCircle className="w-3.5 h-3.5 mr-1 text-rose-600" />
                Slot {report.hour_slot} IST — Rejected
              </span>
            )}
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Daily calling totals calculated from registered recruiter sheets. Review activity before publishing.
          </p>
        </div>

        {/* Top Action Buttons */}
        <div className="flex items-center space-x-3">
          <button
            onClick={handleSyncNow}
            disabled={isSyncing}
            className="inline-flex items-center space-x-2 px-3.5 py-2.5 rounded-xl font-semibold text-xs border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 shadow-sm transition-all focus:ring-2 focus:ring-brand-500/20 active:scale-95 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${isSyncing ? 'animate-spin' : ''}`} />
            <span>{isSyncing ? 'Syncing...' : 'Sync Live Sheets'}</span>
          </button>

          <button
            onClick={handleCopyWhatsApp}
            className="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl font-semibold text-xs bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all focus:ring-2 focus:ring-emerald-500/20 active:scale-95"
          >
            {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            <span>{copied ? 'Copied!' : 'Copy for WhatsApp'}</span>
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Calls */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Total Calls Logged</span>
            <span className="p-2 bg-indigo-50 text-indigo-600 rounded-lg"><TrendingUp className="w-4 h-4" /></span>
          </div>
          <p className="text-3xl font-extrabold text-slate-900 mt-2">{displayedSummary.total_calls}</p>
          <p className="text-xs text-slate-500 mt-1">Across {displayedSummary.active_recruiters_count} active recruiters today</p>
        </div>

        {/* Connected Calls */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Connected Calls</span>
            <span className="p-2 bg-emerald-50 text-emerald-600 rounded-lg"><CheckCircle2 className="w-4 h-4" /></span>
          </div>
          <p className="text-3xl font-extrabold text-emerald-600 mt-2">{displayedSummary.connected_calls}</p>
          <p className="text-xs text-slate-500 mt-1">
            {displayedSummary.not_connected_calls} non-connected / attempts
          </p>
        </div>

        {/* Connected Rate % */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Connection Rate</span>
            <span className="p-2 bg-brand-50 text-brand-600 rounded-lg"><Sparkles className="w-4 h-4" /></span>
          </div>
          <p className="text-3xl font-extrabold text-brand-600 mt-2">{displayedSummary.connected_rate}%</p>
          <div className="w-full bg-slate-100 rounded-full h-1.5 mt-2">
            <div
              className="bg-brand-600 h-1.5 rounded-full"
              style={{ width: `${Math.min(displayedSummary.connected_rate, 100)}%` }}
            ></div>
          </div>
        </div>

        {/* Tomorrow's Interviews */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Tomorrow's Interviews</span>
            <span className="p-2 bg-amber-50 text-amber-600 rounded-lg"><Calendar className="w-4 h-4" /></span>
          </div>
          <p className="text-3xl font-extrabold text-amber-600 mt-2">{displayedSummary.next_day_interviews}</p>
          <p className="text-xs text-slate-500 mt-1">Calendar data is not included in file uploads</p>
        </div>
      </div>

      {/* Recruiter Activity Breakdown Table */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900">Recruiter Calling Activity Breakdown</h2>
            <p className="text-xs text-slate-500">Hourly snapshot represents cumulative daily calling volume.</p>
          </div>
          <span className="text-xs font-medium text-slate-400">
            Reporting Date: <strong className="text-slate-700">{report.reporting_date}</strong>
          </span>
        </div>
        {isPending && (
          <div className="flex items-center justify-between gap-3 px-6 py-3 bg-indigo-50 border-b border-indigo-100">
            <p className="text-xs text-indigo-800">
              {editableMetrics
                ? 'Edit roles as comma-separated values. Team totals and rates update automatically.'
                : 'If something looks off, edit the recruiter values before approving.'}
            </p>
            {editableMetrics ? (
              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  onClick={handleCancelEditing}
                  disabled={isSavingEdits}
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-50"
                >
                  <X className="h-3.5 w-3.5" /> Cancel
                </button>
                <button
                  type="button"
                  onClick={() => void handleSaveEdits()}
                  disabled={isSavingEdits}
                  className="inline-flex items-center gap-1 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                >
                  <Save className="h-3.5 w-3.5" /> {isSavingEdits ? 'Saving...' : 'Save edits'}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={handleStartEditing}
                className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-brand-700 border border-brand-200 hover:bg-brand-100"
              >
                <Pencil className="h-3.5 w-3.5" /> Edit report
              </button>
            )}
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50/75 border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-500">
                <th className="py-3 px-6">Recruiter</th>
                <th className="py-3 px-6">Job Roles</th>
                <th className="py-3 px-6 text-right">Connected</th>
                <th className="py-3 px-6 text-right">Not Connected</th>
                <th className="py-3 px-6 text-right">Total Calls</th>
                <th className="py-3 px-6 text-center">Conn. Rate</th>
                <th className="py-3 px-6 text-right">Interviews (Tomorrow)</th>
                {editableMetrics && <th className="py-3 px-6 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {displayedMetrics.map((m: RecruiterMetric) => (
                <tr key={m.id} className="hover:bg-slate-50/60 transition-colors">
                  <td className="py-4 px-6 font-semibold text-slate-900 flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center font-bold text-slate-600 text-xs">
                      {m.recruiter_name.split(' ').map(n => n[0]).join('')}
                    </div>
                    <span>{m.recruiter_name}</span>
                  </td>
                  <td className="py-4 px-6">
                    <div className="flex flex-wrap gap-1.5 max-w-xs">
                      {m.job_roles.map((r, i) => (
                        <span key={i} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                          {r}
                        </span>
                      ))}
                    </div>
                    {editableMetrics && (
                      <input
                        type="text"
                        aria-label={`Job roles for ${m.recruiter_name}`}
                        value={editById.get(m.id)?.job_roles ?? ''}
                        onChange={(event) => setEditableMetrics((current) => current?.map((metric) =>
                          metric.id === m.id ? { ...metric, job_roles: event.target.value } : metric
                        ) ?? null)}
                        placeholder="Comma-separated roles"
                        className="mt-2 w-full min-w-40 rounded-lg border border-slate-300 px-2 py-1.5 text-xs"
                      />
                    )}
                  </td>
                  <td className="py-4 px-6 text-right font-semibold text-emerald-600">
                    {editableMetrics ? (
                      <input
                        type="number"
                        min="0"
                        step="1"
                        aria-label={`Connected calls for ${m.recruiter_name}`}
                        value={editById.get(m.id)?.connected_calls ?? ''}
                        onChange={(event) => setEditableMetrics((current) => current?.map((metric) =>
                          metric.id === m.id ? { ...metric, connected_calls: event.target.value } : metric
                        ) ?? null)}
                        className="w-20 rounded-lg border border-slate-300 px-2 py-1.5 text-right text-sm"
                      />
                    ) : m.connected_calls}
                  </td>
                  <td className="py-4 px-6 text-right font-medium text-slate-500">
                    {editableMetrics ? (
                      <input
                        type="number"
                        min="0"
                        step="1"
                        aria-label={`Not connected calls for ${m.recruiter_name}`}
                        value={editById.get(m.id)?.not_connected_calls ?? ''}
                        onChange={(event) => setEditableMetrics((current) => current?.map((metric) =>
                          metric.id === m.id ? { ...metric, not_connected_calls: event.target.value } : metric
                        ) ?? null)}
                        className="w-20 rounded-lg border border-slate-300 px-2 py-1.5 text-right text-sm"
                      />
                    ) : m.not_connected_calls}
                  </td>
                  <td className="py-4 px-6 text-right font-bold text-slate-900">
                    {m.total_calls}
                  </td>
                  <td className="py-4 px-6 text-center">
                    <div className="inline-flex items-center space-x-2">
                      <span className="font-semibold text-xs text-slate-700 w-12 text-right">
                        {m.connected_rate.toFixed(1)}%
                      </span>
                      <div className="w-16 bg-slate-100 rounded-full h-1.5 hidden sm:block">
                        <div
                          className="bg-brand-600 h-1.5 rounded-full"
                          style={{ width: `${Math.min(m.connected_rate, 100)}%` }}
                        ></div>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 px-6 text-right font-bold text-amber-600">
                    {editableMetrics ? (
                      <input
                        type="number"
                        min="0"
                        step="1"
                        aria-label={`Interviews for ${m.recruiter_name}`}
                        value={editById.get(m.id)?.next_day_interviews ?? ''}
                        onChange={(event) => setEditableMetrics((current) => current?.map((metric) =>
                          metric.id === m.id ? { ...metric, next_day_interviews: event.target.value } : metric
                        ) ?? null)}
                        className="w-20 rounded-lg border border-slate-300 px-2 py-1.5 text-right text-sm"
                      />
                    ) : <>🎯 {m.next_day_interviews}</>}
                  </td>
                  {editableMetrics && <td className="py-4 px-6 text-right text-xs text-slate-400">Auto</td>}
                </tr>
              ))}
            </tbody>
            {/* Team Totals Row */}
            <tfoot>
              <tr className="bg-slate-50 font-bold text-slate-900 border-t-2 border-slate-200">
                <td className="py-3 px-6">Team Total</td>
                <td className="py-3 px-6 text-xs text-slate-500">All Roles</td>
                <td className="py-3 px-6 text-right text-emerald-600">{displayedSummary.connected_calls}</td>
                <td className="py-3 px-6 text-right text-slate-500">{displayedSummary.not_connected_calls}</td>
                <td className="py-3 px-6 text-right text-slate-900">{displayedSummary.total_calls}</td>
                <td className="py-3 px-6 text-center text-brand-600">{displayedSummary.connected_rate}%</td>
                <td className="py-3 px-6 text-right text-amber-600">🎯 {displayedSummary.next_day_interviews}</td>
                {editableMetrics && <td className="py-3 px-6" />}
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* Bottom Sticky Approval Actions Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-lg p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center space-x-3">
          <UserCheck className="w-5 h-5 text-brand-600" />
          <div>
            <p className="text-sm font-bold text-slate-900">
              {isApproved
                ? `Approved by ${report.approved_by_name || 'MIS Lead'}`
                : isRejected
                ? `Rejected: ${report.rejection_reason}`
                : 'Awaiting MIS Lead Sign-off'}
            </p>
            <p className="text-xs text-slate-500">
              {isApproved
                ? 'Published and accessible on management dashboard and download channels.'
                : 'Review calling metrics before making them visible to leadership.'}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {isPending && (
            <>
              <button
                onClick={() => setShowRejectModal(true)}
                disabled={isRejecting || isApproving}
                className="px-4 py-2.5 rounded-xl font-semibold text-sm border border-rose-200 text-rose-600 hover:bg-rose-50 transition-colors"
              >
                Reject Report
              </button>
              <button
                onClick={handleApprove}
                disabled={isApproving || isRejecting}
                className="px-6 py-2.5 rounded-xl font-semibold text-sm bg-brand-600 hover:bg-brand-700 text-white shadow-md shadow-brand-500/20 transition-all flex items-center space-x-2"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>{isApproving ? 'Approving...' : 'Approve & Publish'}</span>
              </button>
            </>
          )}

          {isApproved && (
            <div className="flex items-center space-x-2 text-emerald-600 font-semibold text-sm bg-emerald-50 px-4 py-2 rounded-xl">
              <Check className="w-4 h-4" />
              <span>Published to Leadership</span>
            </div>
          )}
        </div>
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Reject Hourly Report</h3>
            <p className="text-sm text-slate-500">
              Please specify why this report was rejected (e.g. awaiting recruiter sheet update, missing data).
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Enter rejection reason..."
              className="w-full h-24 p-3 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-brand-500 focus:outline-none"
            />
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setShowRejectModal(false)}
                className="px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Cancel
              </button>
              <button
                onClick={handleRejectConfirm}
                disabled={!rejectReason.trim()}
                className="px-4 py-2 text-sm font-semibold bg-rose-600 hover:bg-rose-700 text-white rounded-xl disabled:opacity-50"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
