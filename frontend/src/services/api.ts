import { HourlyReport, Recruiter, Workspace, ColumnMappingItem } from '../types';

const API_BASE = '/api/v1';

// Default mock data for realistic demo if backend is offline
const MOCK_WORKSPACE: Workspace = {
  id: 'ws-apex-101',
  name: 'Apex Staffing Solutions',
  slug: 'apex-staffing',
  timezone: 'Asia/Kolkata',
  service_account_email: 'sync@recruiterpulse.iam.gserviceaccount.com'
};

const MOCK_PENDING_REPORT: HourlyReport = {
  id: 'rep-draft-1500',
  workspace_id: 'ws-apex-101',
  reporting_date: '2026-11-12',
  hour_slot: '15:00',
  status: 'DRAFT_PENDING_APPROVAL',
  summary_totals: {
    total_calls: 128,
    connected_calls: 84,
    not_connected_calls: 44,
    connected_rate: 65.6,
    next_day_interviews: 6,
    active_recruiters_count: 3
  },
  metrics: [
    {
      id: 'met-1',
      recruiter_id: 'rec-1',
      recruiter_name: 'Priya Sharma',
      job_roles: ['Java Backend', 'DevOps'],
      connected_calls: 28,
      not_connected_calls: 14,
      total_calls: 42,
      connected_rate: 66.7,
      next_day_interviews: 3,
      unassigned_interviews: 0
    },
    {
      id: 'met-2',
      recruiter_id: 'rec-2',
      recruiter_name: 'Rahul Verma',
      job_roles: ['React Frontend'],
      connected_calls: 18,
      not_connected_calls: 17,
      total_calls: 35,
      connected_rate: 51.4,
      next_day_interviews: 1,
      unassigned_interviews: 0
    },
    {
      id: 'met-3',
      recruiter_id: 'rec-3',
      recruiter_name: 'Amit Patel',
      job_roles: ['Data Engineer', 'AWS Cloud'],
      connected_calls: 38,
      not_connected_calls: 13,
      total_calls: 51,
      connected_rate: 74.5,
      next_day_interviews: 2,
      unassigned_interviews: 0
    }
  ],
  created_at: new Date().toISOString()
};

export const api = {
  async getWorkspace(): Promise<Workspace> {
    try {
      const res = await fetch(`${API_BASE}/workspaces/${MOCK_WORKSPACE.id}`);
      if (!res.ok) throw new Error();
      return await res.json();
    } catch {
      return MOCK_WORKSPACE;
    }
  },

  async getPendingReport(workspaceId: string = MOCK_WORKSPACE.id): Promise<HourlyReport | null> {
    try {
      const res = await fetch(`${API_BASE}/reports/pending?workspace_id=${workspaceId}`);
      if (!res.ok) throw new Error();
      const data = await res.json();
      return data || MOCK_PENDING_REPORT;
    } catch {
      return MOCK_PENDING_REPORT;
    }
  },

  async getLatestApprovedReport(workspaceId: string = MOCK_WORKSPACE.id): Promise<HourlyReport | null> {
    try {
      const res = await fetch(`${API_BASE}/reports/latest?workspace_id=${workspaceId}`);
      if (!res.ok) throw new Error();
      return await res.json();
    } catch {
      return {
        ...MOCK_PENDING_REPORT,
        id: 'rep-approved-1400',
        hour_slot: '14:00',
        status: 'APPROVED',
        approved_by_name: 'Pooja Kulkarni (MIS Lead)',
        approved_at: new Date().toISOString()
      };
    }
  },

  async approveReport(reportId: string, approverUserId: string = 'usr-admin'): Promise<HourlyReport> {
    try {
      const res = await fetch(`${API_BASE}/reports/${reportId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approver_user_id: approverUserId })
      });
      if (!res.ok) throw new Error();
      return await res.json();
    } catch {
      return {
        ...MOCK_PENDING_REPORT,
        status: 'APPROVED',
        approved_by_name: 'Pooja Kulkarni (MIS Lead)',
        approved_at: new Date().toISOString()
      };
    }
  },

  async rejectReport(reportId: string, reason: string, approverUserId: string = 'usr-admin'): Promise<HourlyReport> {
    try {
      const res = await fetch(`${API_BASE}/reports/${reportId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approver_user_id: approverUserId, reason })
      });
      if (!res.ok) throw new Error();
      return await res.json();
    } catch {
      return {
        ...MOCK_PENDING_REPORT,
        status: 'REJECTED',
        rejection_reason: reason
      };
    }
  },

  async getWhatsAppText(reportId: string): Promise<string> {
    try {
      const res = await fetch(`${API_BASE}/reports/${reportId}/whatsapp`);
      if (!res.ok) throw new Error();
      const data = await res.json();
      return data.formatted_text;
    } catch {
      return `📊 *Apex Staffing Solutions — MIS Report*\n📅 *Date:* 12-Nov-2026 | *Slot:* 03:00 PM IST\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n👤 *Priya Sharma* (Java Backend, DevOps)\n   Calls: 42 (28 Conn / 14 Not Conn) | 66.7% | 🎯 Intrvws: 3\n\n👤 *Rahul Verma* (React Frontend)\n   Calls: 35 (18 Conn / 17 Not Conn) | 51.4% | 🎯 Intrvws: 1\n\n👤 *Amit Patel* (Data Engineer, AWS Cloud)\n   Calls: 51 (38 Conn / 13 Not Conn) | 74.5% | 🎯 Intrvws: 2\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n📈 *Team Total:* 128 Calls | 65.6% Conn Rate | 🎯 6 Next-Day Interviews\n✅ *Status:* Approved by MIS (Pooja Kulkarni)`;
    }
  },

  async triggerSync(workspaceId: string = MOCK_WORKSPACE.id): Promise<HourlyReport> {
    try {
      const res = await fetch(`${API_BASE}/sync/${workspaceId}`, { method: 'POST' });
      if (!res.ok) throw new Error();
      return await res.json();
    } catch {
      return MOCK_PENDING_REPORT;
    }
  }

};

