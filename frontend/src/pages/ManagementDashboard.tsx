import React from 'react';
import { HourlyReport } from '../types';
import { Download, Award, TrendingUp } from 'lucide-react';

interface ManagementDashboardProps {
  report: HourlyReport;
}

export const ManagementDashboard: React.FC<ManagementDashboardProps> = ({ report }) => {
  const handleDownloadCSV = () => {
    const headers = ['Recruiter', 'Job Roles', 'Connected', 'Not Connected', 'Total Calls', 'Connected Rate %', 'Next-Day Interviews'];
    const escapeCsv = (value: string | number) => `"${String(value).replace(/"/g, '""')}"`;
    const rows = report.metrics.map(m => [
      escapeCsv(m.recruiter_name),
      escapeCsv(m.job_roles.join(', ')),
      m.connected_calls,
      m.not_connected_calls,
      m.total_calls,
      m.connected_rate,
      m.next_day_interviews
    ]);
    const csvContent = `\uFEFF${[headers.map(escapeCsv).join(','), ...rows.map(row => row.join(','))].join('\r\n')}`;
    const fileUrl = URL.createObjectURL(new Blob([csvContent], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.setAttribute('href', fileUrl);
    link.setAttribute('download', `RecruiterPulse_MIS_${report.reporting_date}_${report.hour_slot}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(fileUrl);
  };

  const sortedRecruiters = [...report.metrics].sort((a, b) => b.connected_rate - a.connected_rate);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Report Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Management MIS Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">
            Spreadsheet analysis for {report.reporting_date}, report slot {report.hour_slot}.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleDownloadCSV}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 text-xs font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 rounded-xl shadow-sm transition-all"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download CSV</span>
          </button>
        </div>
      </div>

      {/* Primary KPI Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-gradient-to-br from-brand-600 to-indigo-700 p-6 rounded-2xl text-white shadow-lg shadow-brand-500/20">
          <div className="flex items-center justify-between opacity-80 text-xs font-semibold uppercase tracking-wider">
            <span>Total Calls</span>
            <TrendingUp className="w-4 h-4" />
          </div>
          <p className="text-4xl font-extrabold mt-3">{report.summary_totals.total_calls}</p>
          <p className="text-xs text-indigo-100 mt-2">
            {report.summary_totals.connected_calls} connected ({report.summary_totals.connected_rate}% conversion)
          </p>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>Confirmed Interviews (Tomorrow)</span>
            <TrendingUp className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-4xl font-extrabold text-amber-600 mt-3">{report.summary_totals.next_day_interviews}</p>
          <p className="text-xs text-slate-500 mt-2">Calendar data is not included in file uploads</p>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>Top Performing Recruiter</span>
            <Award className="w-4 h-4 text-emerald-500" />
          </div>
          {sortedRecruiters.length > 0 && (
            <>
              <p className="text-2xl font-extrabold text-slate-900 mt-3">{sortedRecruiters[0].recruiter_name}</p>
              <p className="text-xs text-emerald-600 font-semibold mt-2">
                {sortedRecruiters[0].connected_rate.toFixed(1)}% connect rate ({sortedRecruiters[0].connected_calls} calls)
              </p>
            </>
          )}
        </div>
      </div>

      {/* Recruiter Leaderboard Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-900">Recruiter Productivity Ranking</h2>
          <span className="text-xs text-slate-500">Sorted by Connection Rate</span>
        </div>

        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-500">
            <tr>
              <th className="py-3 px-6">Rank</th>
              <th className="py-3 px-6">Recruiter</th>
              <th className="py-3 px-6">Active Roles</th>
              <th className="py-3 px-6 text-right">Connected</th>
              <th className="py-3 px-6 text-right">Total Calls</th>
              <th className="py-3 px-6 text-center">Efficiency</th>
              <th className="py-3 px-6 text-right">Interviews</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sortedRecruiters.map((rec, idx) => (
              <tr key={rec.id} className="hover:bg-slate-50 transition-colors">
                <td className="py-4 px-6 font-bold text-slate-400 text-xs">
                  #{idx + 1}
                </td>
                <td className="py-4 px-6 font-bold text-slate-900">
                  {rec.recruiter_name}
                </td>
                <td className="py-4 px-6 text-xs text-slate-600">
                  {rec.job_roles.join(', ') || 'General'}
                </td>
                <td className="py-4 px-6 text-right font-semibold text-emerald-600">
                  {rec.connected_calls}
                </td>
                <td className="py-4 px-6 text-right font-bold text-slate-900">
                  {rec.total_calls}
                </td>
                <td className="py-4 px-6 text-center">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-brand-50 text-brand-700">
                    {rec.connected_rate.toFixed(1)}%
                  </span>
                </td>
                <td className="py-4 px-6 text-right font-bold text-amber-600">
                  🎯 {rec.next_day_interviews}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
