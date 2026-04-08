/**
 * Centralized API calls for the analyses resource.
 * Requirements: FR-UPLD-01 through FR-UPLD-09, FR-XDET-01, FR-XDET-02, FR-XDET-05, FR-XDET-08, FR-XDET-09
 */

import { supabase } from "@/lib/supabase";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

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

async function getAuthToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    throw new Error("Not authenticated");
  }
  return token;
}

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
