/**
 * Centralized API calls for admin resource.
 * Requirements: FR-ADMN-01 through FR-ADMN-05
 */

import { supabase } from "@/lib/supabase";
import { API_BASE } from "@/api/config";

export interface AdminUser {
  user_id: string;
  height_cm: number | null;
  weight_kg: number | null;
  age: number | null;
  experience_level: string | null;
  analysis_count: number;
  created_at: string;
  updated_at: string;
}

export interface AdminAnalysis {
  id: string;
  user_id: string;
  status: string;
  exercise_type: string;
  exercise_variant: string;
  confidence_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface AdminHealth {
  queue_depth: number;
  worker_heartbeat: boolean;
  db_ok: boolean;
}

async function getAuthToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    throw new Error("Not authenticated");
  }
  return token;
}

async function adminFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getAuthToken();
  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const err = { status: resp.status, ...(body.detail ?? body) };
    throw err;
  }

  if (resp.status === 204) {
    return undefined as unknown as T;
  }

  return resp.json() as Promise<T>;
}

export async function listAdminUsers(limit = 50, offset = 0): Promise<AdminUser[]> {
  return adminFetch<AdminUser[]>(
    `/api/v1/admin/users?limit=${limit}&offset=${offset}`,
  );
}

export async function deleteAdminUser(userId: string): Promise<void> {
  return adminFetch<void>(`/api/v1/admin/users/${userId}`, { method: "DELETE" });
}

export async function disableAdminUser(userId: string): Promise<{ message: string }> {
  return adminFetch<{ message: string }>(`/api/v1/admin/users/${userId}/disable`, {
    method: "PATCH",
  });
}

export async function listAdminAnalyses(
  limit = 50,
  offset = 0,
  status?: string,
): Promise<AdminAnalysis[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (status) {
    params.set("status", status);
  }
  return adminFetch<AdminAnalysis[]>(`/api/v1/admin/analyses?${params.toString()}`);
}

export async function getAdminHealth(): Promise<AdminHealth> {
  return adminFetch<AdminHealth>("/api/v1/admin/health");
}

// ---------------------------------------------------------------------------
// RAG Corpus Management (P2-035, FR-ADMN-06, FR-RAGK-08/09)
// ---------------------------------------------------------------------------

export interface RagDocument {
  id: string;
  title: string;
  source_url: string | null;
  document_type: string;
  exercise_tags: string[];
  chunk_count: number;
  ingested_at: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  study_design: string | null;
  quality_tier: string | null;
  quality_score: number | null;
  review_status: string;
  reviewer_id: string | null;
  reviewed_at: string | null;
  storage_path: string | null;
  created_at: string;
  updated_at: string;
}

export async function listRagDocuments(
  limit = 50,
  offset = 0,
  filters?: { review_status?: string; exercise_tag?: string; quality_tier?: string },
): Promise<RagDocument[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (filters?.review_status) params.set("review_status", filters.review_status);
  if (filters?.exercise_tag) params.set("exercise_tag", filters.exercise_tag);
  if (filters?.quality_tier) params.set("quality_tier", filters.quality_tier);
  return adminFetch<RagDocument[]>(`/api/v1/admin/rag/documents?${params}`);
}

export async function deleteRagDocument(id: string): Promise<void> {
  return adminFetch<void>(`/api/v1/admin/rag/documents/${id}`, { method: "DELETE" });
}

export async function reEmbedRagDocument(id: string): Promise<{ message: string; document_id: string }> {
  return adminFetch(`/api/v1/admin/rag/documents/${id}/re-embed`, { method: "POST" });
}

// ---------------------------------------------------------------------------
// Expert Reviewer Queue (P2-036, FR-ADMN-07)
// ---------------------------------------------------------------------------

export interface AdminExpertQueueItem {
  analysis_id: string;
  exercise_type: string;
  exercise_variant: string | null;
  confidence_score: number | null;
  flagged_for_review: boolean;
  created_at: string;
  annotation_count: number;
  latest_annotation_at: string | null;
}

export interface AdminExpertQueueStats {
  total_flagged: number;
  total_annotated: number;
  golden_dataset_count: number;
}

export async function listExpertQueue(limit = 50, offset = 0): Promise<AdminExpertQueueItem[]> {
  return adminFetch<AdminExpertQueueItem[]>(
    `/api/v1/admin/expert-queue?limit=${limit}&offset=${offset}`,
  );
}

export async function getExpertQueueStats(): Promise<AdminExpertQueueStats> {
  return adminFetch<AdminExpertQueueStats>("/api/v1/admin/expert-queue/stats");
}

// ---------------------------------------------------------------------------
// Coach Brain Management (P2-037, FR-ADMN-10)
// ---------------------------------------------------------------------------

export interface CoachBrainEntry {
  id: string;
  content: string;
  exercise: string;
  phase: string;
  entry_type: string;
  status: string;
  confirmation_count: number;
  source_analysis_ids: string[];
  trigger_tags: string[];
  confidence_score: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CoachBrainEntryCreate {
  content: string;
  exercise: string;
  phase?: string;
  entry_type: string;
  status?: string;
}

export async function listCoachBrainEntries(
  limit = 50,
  offset = 0,
  filters?: { exercise?: string; status?: string; entry_type?: string },
): Promise<CoachBrainEntry[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (filters?.exercise) params.set("exercise", filters.exercise);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.entry_type) params.set("entry_type", filters.entry_type);
  return adminFetch<CoachBrainEntry[]>(`/api/v1/admin/coach-brain?${params}`);
}

export async function createCoachBrainEntry(data: CoachBrainEntryCreate): Promise<CoachBrainEntry> {
  return adminFetch<CoachBrainEntry>("/api/v1/admin/coach-brain", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCoachBrainEntry(
  id: string,
  data: Partial<CoachBrainEntryCreate & { status: string }>,
): Promise<CoachBrainEntry> {
  return adminFetch<CoachBrainEntry>(`/api/v1/admin/coach-brain/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteCoachBrainEntry(id: string): Promise<void> {
  return adminFetch<void>(`/api/v1/admin/coach-brain/${id}`, { method: "DELETE" });
}
