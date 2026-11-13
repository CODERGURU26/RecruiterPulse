import { HourlyReport, LiveDataSource, Recruiter, Workspace } from '../types';

const API_BASE = '/api/v1';
export const DEFAULT_WORKSPACE_ID = 'ws-apex-101';
const DEFAULT_APPROVER_USER_ID = 'usr-admin';

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getWorkspace(workspaceId?: string): Promise<Workspace> {
    const path = workspaceId
      ? `${API_BASE}/workspaces/${workspaceId}`
      : `${API_BASE}/workspaces/default`;
    return request(path);
  },

  getRecruiters(workspaceId = DEFAULT_WORKSPACE_ID): Promise<Recruiter[]> {
    return request(`${API_BASE}/workspaces/${workspaceId}/recruiters`);
  },

  getDataSources(workspaceId: string): Promise<LiveDataSource[]> {
    return request(`${API_BASE}/data-sources/${workspaceId}`);
  },

  registerGoogleSheet(
    workspaceId: string,
    recruiterName: string,
    sheetUrl: string
  ): Promise<LiveDataSource> {
    return request(`${API_BASE}/data-sources/${workspaceId}/google-sheet`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recruiter_name: recruiterName, sheet_url: sheetUrl })
    });
  },

  getPendingReport(workspaceId = DEFAULT_WORKSPACE_ID): Promise<HourlyReport | null> {
    return request(`${API_BASE}/reports/pending?workspace_id=${encodeURIComponent(workspaceId)}`);
  },

  getLatestApprovedReport(workspaceId = DEFAULT_WORKSPACE_ID): Promise<HourlyReport | null> {
    return request(`${API_BASE}/reports/latest?workspace_id=${encodeURIComponent(workspaceId)}`);
  },

  approveReport(reportId: string, approverUserId = DEFAULT_APPROVER_USER_ID): Promise<HourlyReport> {
    return request(`${API_BASE}/reports/${reportId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approver_user_id: approverUserId })
    });
  },

  rejectReport(
    reportId: string,
    reason: string,
    approverUserId = DEFAULT_APPROVER_USER_ID
  ): Promise<HourlyReport> {
    return request(`${API_BASE}/reports/${reportId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approver_user_id: approverUserId, reason })
    });
  },

  async getWhatsAppText(reportId: string): Promise<string> {
    const data = await request<{ formatted_text: string }>(`${API_BASE}/reports/${reportId}/whatsapp`);
    return data.formatted_text;
  },

  triggerSync(workspaceId = DEFAULT_WORKSPACE_ID): Promise<HourlyReport> {
    return request(`${API_BASE}/sync/${workspaceId}`, { method: 'POST' });
  },

  async processRealFile(file: File, workspaceId: string, recruiterName?: string): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('workspace_id', workspaceId);
    if (recruiterName) formData.append('recruiter_name', recruiterName);

    return request(`${API_BASE}/data-sources/process-real-file`, {
      method: 'POST',
      body: formData
    });
  },

  async processGoogleSheet(url: string, workspaceId: string, recruiterName?: string): Promise<any> {
    const formData = new FormData();
    formData.append('google_sheet_url', url);
    formData.append('workspace_id', workspaceId);
    if (recruiterName) formData.append('recruiter_name', recruiterName);

    return request(`${API_BASE}/data-sources/process-real-file`, {
      method: 'POST',
      body: formData
    });
  }
};
