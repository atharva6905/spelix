/**
 * API client for insights endpoints.
 * Requirements: FR-HIST-02, FR-HIST-03
 *
 * NOTE: Backend endpoints (B-031) are not yet implemented.
 * These functions will throw on 404 — callers handle gracefully.
 */

import { supabase } from "@/lib/supabase";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ExerciseInsights {
  rolling_avg_confidence: number[];
  rep_count_trend: number[];
  most_common_warning: string | null;
  personal_best_confidence: number;
}

export interface GlobalInsights {
  most_common_warning: string | null;
  highest_variance_exercise: string | null;
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

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/**
 * GET /api/v1/insights/exercise/{type}/{variant}
 * Returns per-exercise insights for the last 7 sessions.
 */
export async function getExerciseInsights(
  type: string,
  variant: string,
): Promise<ExerciseInsights> {
  const token = await getAuthToken();
  const resp = await fetch(
    `${API_BASE}/api/v1/insights/exercise/${encodeURIComponent(type)}/${encodeURIComponent(variant)}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  );

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const message =
      body.error?.message ?? body.detail ?? "Failed to fetch exercise insights";
    const err = new Error(message) as Error & { status: number };
    err.status = resp.status;
    throw err;
  }

  return resp.json() as Promise<ExerciseInsights>;
}

/**
 * GET /api/v1/insights/global
 * Returns global insights across all exercises (last 30 days).
 */
export async function getGlobalInsights(): Promise<GlobalInsights> {
  const token = await getAuthToken();
  const resp = await fetch(`${API_BASE}/api/v1/insights/global`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const message =
      body.error?.message ?? body.detail ?? "Failed to fetch global insights";
    const err = new Error(message) as Error & { status: number };
    err.status = resp.status;
    throw err;
  }

  return resp.json() as Promise<GlobalInsights>;
}
