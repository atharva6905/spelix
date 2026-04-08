/**
 * Centralized API calls for the analyses resource.
 * Requirements: FR-RESL-13, NFR-RELI-06
 */

import { supabase } from "@/lib/supabase";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

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

async function getAuthToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    throw new Error("Not authenticated");
  }
  return token;
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
