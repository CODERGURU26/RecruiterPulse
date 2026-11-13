export type UserRole = 'AGENCY_OWNER' | 'MANAGER' | 'MIS_EXECUTIVE' | 'RECRUITER';
export type ReportStatus = 'DRAFT_PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'SUPERSEDED';

export interface RecruiterMetric {
  id: string;
  recruiter_id: string;
  recruiter_name: string;
  job_roles: string[];
  connected_calls: number;
  not_connected_calls: number;
  total_calls: number;
  connected_rate: number;
  next_day_interviews: number;
  unassigned_interviews: number;
}

export interface SummaryTotals {
  total_calls: number;
  connected_calls: number;
  not_connected_calls: number;
  connected_rate: number;
  next_day_interviews: number;
  active_recruiters_count?: number;
}

export interface HourlyReport {
  id: string;
  workspace_id: string;
  reporting_date: string;
  hour_slot: string;
  status: ReportStatus;
  approved_by_name?: string | null;
  approved_at?: string | null;
  rejection_reason?: string | null;
  summary_totals: SummaryTotals;
  metrics: RecruiterMetric[];
  created_at: string;
}

export interface Recruiter {
  id: string;
  workspace_id: string;
  full_name: string;
  email?: string | null;
  calendar_identifier?: string | null;
  is_active: boolean;
}

export interface LiveDataSource {
  id: string;
  workspace_id: string;
  recruiter_id: string | null;
  name: string;
  sync_status: 'ACTIVE' | 'PENDING_MAPPING' | 'ERROR' | 'PAUSED';
  last_synced_at: string | null;
  last_error_message: string | null;
}

export interface ColumnMappingItem {
  standard_field: string;
  source_column: string | null;
  confidence: number;
  sample_values: string[];
  is_confirmed: boolean;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  timezone: string;
  service_account_email?: string | null;
}
