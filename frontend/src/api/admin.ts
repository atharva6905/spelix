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

// ---------------------------------------------------------------------------
// Coach Brain Candidate Review Queue (P3-006, FR-ADMN-12)
// ---------------------------------------------------------------------------

export interface CoachBrainCandidate {
  id: string;
  exercise: "squat" | "bench" | "deadlift";
  phase: "setup" | "descent" | "bottom" | "ascent" | "lockout" | "general" | null;
  entry_type: "cue" | "correction" | "principle" | "drill" | "compensation";
  content: string;
  trigger_tags: string[];
  source_analysis_ids: string[];
  confidence_score: number | null;
  eval_scores: Record<string, number>;
  cove_verified: boolean | null;
  cove_explanation: string | null;
  lifecycle_decision: "ADD" | "UPDATE" | "NOOP";
  nearest_entry_id: string | null;
  nearest_cosine_sim: number | null;
  contradiction_flag: boolean;
  review_status: "pending" | "approved" | "rejected" | "superseded";
  created_at: string;
}

export interface ApproveCandidateResponse {
  candidate_id: string;
  entry_id: string;
  qdrant_point_id: string;
}

export interface RejectCandidateResponse {
  candidate_id: string;
  rejected_reason: string;
}

export interface PendingQueueStats {
  total_pending: number;
}

export async function listCoachBrainCandidates(
  limit = 50,
  offset = 0,
): Promise<CoachBrainCandidate[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return adminFetch<CoachBrainCandidate[]>(
    `/api/v1/admin/coach-brain/candidates?${params}`,
  );
}

export async function getCoachBrainCandidateStats(): Promise<PendingQueueStats> {
  return adminFetch<PendingQueueStats>(
    "/api/v1/admin/coach-brain/candidates/stats",
  );
}

export async function approveCoachBrainCandidate(
  id: string,
  contentOverride?: string,
): Promise<ApproveCandidateResponse> {
  const body =
    contentOverride !== undefined && contentOverride.trim() !== ""
      ? { content_override: contentOverride }
      : {};
  return adminFetch<ApproveCandidateResponse>(
    `/api/v1/admin/coach-brain/candidates/${id}/approve`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export async function rejectCoachBrainCandidate(
  id: string,
  reason: string,
): Promise<RejectCandidateResponse> {
  return adminFetch<RejectCandidateResponse>(
    `/api/v1/admin/coach-brain/candidates/${id}/reject`,
    {
      method: "POST",
      body: JSON.stringify({ reason }),
    },
  );
}

export interface SimilarEntry {
  id: string;
  content: string;
  exercise: "squat" | "bench" | "deadlift";
  phase:
    | "setup"
    | "descent"
    | "bottom"
    | "ascent"
    | "lockout"
    | "general"
    | null;
  entry_type:
    | "cue"
    | "correction"
    | "principle"
    | "drill"
    | "compensation";
  cosine_sim: number;
}

export interface SimilarEntriesResponse {
  items: SimilarEntry[];
}

export async function getCoachBrainCandidateSimilar(
  id: string,
  limit = 2,
): Promise<SimilarEntriesResponse> {
  return adminFetch<SimilarEntriesResponse>(
    `/api/v1/admin/coach-brain/candidates/${id}/similar?limit=${limit}`,
  );
}
