/**
 * Centralized API calls for the analyses resource.
 * Requirements: FR-UPLD-01 through FR-UPLD-09, FR-XDET-01, FR-RESL-13, NFR-RELI-06
 */

import { supabase } from "@/lib/supabase";
import { API_BASE } from "@/api/config";

// ---------------------------------------------------------------------------
// Types — Upload (B-013)
// ---------------------------------------------------------------------------

export type ExerciseType = "squat" | "bench" | "deadlift";

export type ExerciseVariant =
  | "high_bar"
  | "low_bar"
  | "flat"
  | "incline"
  | "decline"
  | "conventional"
  | "sumo"
  | "romanian";

export interface CreateAnalysisRequest {
  exercise_type: ExerciseType;
  exercise_variant: ExerciseVariant;
  filename: string;
  file_size_bytes: number;
}

export interface CreateAnalysisResponse {
  id: string;
  upload_url: string;
  status: string;
  expires_at: string;
}

// ---------------------------------------------------------------------------
// Types — Status (B-014)
// ---------------------------------------------------------------------------

export type AnalysisStatus =
  | "queued"
  | "quality_gate_pending"
  | "quality_gate_rejected"
  | "processing"
  | "coaching"
  | "completed"
  | "failed";

export interface QualityGateCheck {
  name: string;
  passed: boolean;
  user_message: string;
}

export interface QualityGateResult {
  checks: QualityGateCheck[];
}

export interface AnalysisStatusResponse {
  id: string;
  status: AnalysisStatus;
  updated_at: string;
  quality_gate_result?: QualityGateResult | null;
  retry_count?: number;
  error_message?: string | null;
}

// ---------------------------------------------------------------------------
// Types — Detail (B-026, FR-RESL-01a–05)
// ---------------------------------------------------------------------------

export interface CoachingIssue {
  rep_number: number;
  joint: string;
  description: string;
  severity: "High" | "Medium" | "Low";
}

export interface CoachingOutput {
  summary: string;
  strengths: string[];
  issues: CoachingIssue[];
  correction_plan: string[];
  disclaimer: string;
}

export interface CoachingResultDetail {
  structured_output_json: CoachingOutput | null;
  created_at: string;
}

export interface RepMetricDetail {
  rep_index: number;
  start_frame: number;
  end_frame: number;
  confidence_score: number | null;
  metrics_json: Record<string, unknown> | null;
}

export interface AnalysisDetail {
  id: string;
  status: AnalysisStatus;
  exercise_type: string;
  exercise_variant: string;
  confidence_score: number | null;
  video_path: string | null;
  annotated_video_path: string | null;
  plot_path: string | null;
  pdf_path: string | null;
  tags: string[] | null;
  quality_gate_result: Record<string, unknown> | null;
  summary_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  coaching_result: CoachingResultDetail | null;
  rep_metrics: RepMetricDetail[];
}

// ---------------------------------------------------------------------------
// Auth helper
// ---------------------------------------------------------------------------

async function getAuthToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    throw new Error("Not authenticated");
  }
  return token;
}

export async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAuthToken();
  return { Authorization: `Bearer ${token}` };
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function createAnalysis(
  data: CreateAnalysisRequest,
): Promise<CreateAnalysisResponse> {
  const token = await getAuthToken();
  const resp = await fetch(`${API_BASE}/api/v1/analyses`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const err = { status: resp.status, ...(body.error ?? body.detail ?? body) };
    throw err;
  }

  return resp.json() as Promise<CreateAnalysisResponse>;
}

/**
 * POST /api/v1/analyses/{id}/start
 * Triggers the analysis pipeline after TUS upload completes.
 * Requirements: FR-UPLD-08
 */
export async function startAnalysis(
  id: string,
): Promise<{ id: string; status: string }> {
  const response = await fetch(`${API_BASE}/api/v1/analyses/${id}/start`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error?.message ?? "Failed to start analysis");
  }
  return response.json() as Promise<{ id: string; status: string }>;
}

/**
 * GET /api/v1/analyses/{id}/status
 * Returns current status of an analysis.
 * NOTE: Backend endpoint (B-027) not yet implemented — used as polling fallback.
 */
export async function getAnalysisStatus(
  id: string,
): Promise<AnalysisStatusResponse> {
  const token = await getAuthToken();
  const resp = await fetch(`${API_BASE}/api/v1/analyses/${id}/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const message =
      body.error?.message ?? body.detail ?? "Failed to fetch status";
    throw new Error(message);
  }

  return resp.json() as Promise<AnalysisStatusResponse>;
}

/**
 * GET /api/v1/analyses/{id}
 * Returns full analysis detail including coaching result and rep metrics.
 * Requirements: FR-RESL-01a–05, FR-RESL-08, FR-RESL-10–11
 */
export async function getAnalysisDetail(
  id: string,
): Promise<AnalysisDetail> {
  const token = await getAuthToken();
  const resp = await fetch(`${API_BASE}/api/v1/analyses/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const message =
      body.error?.message ?? body.detail ?? "Failed to fetch analysis";
    throw new Error(message);
  }

  return resp.json() as Promise<AnalysisDetail>;
}

// ---------------------------------------------------------------------------
// Types — List (B-032, FR-HIST-01)
// ---------------------------------------------------------------------------

export interface AnalysisListItem {
  id: string;
  status: AnalysisStatus;
  exercise_type: string;
  exercise_variant: string;
  confidence_score: number | null;
  created_at: string;
}

export type AnalysisListResponse = AnalysisListItem[];

/**
 * GET /api/v1/analyses
 * Returns paginated reverse-chronological list of user's analyses.
 * Requirements: FR-HIST-01
 */
export async function listAnalyses(
  limit = 50,
  offset = 0,
): Promise<AnalysisListResponse> {
  const token = await getAuthToken();
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const resp = await fetch(`${API_BASE}/api/v1/analyses?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const message =
      body.error?.message ?? body.detail ?? "Failed to fetch analyses";
    throw new Error(message);
  }

  return resp.json() as Promise<AnalysisListResponse>;
}
