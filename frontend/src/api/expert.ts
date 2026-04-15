/**
 * Centralized API calls for expert reviewer resource.
 * Requirements: FR-EXPV-01 through FR-EXPV-07
 */

import { supabase } from "@/lib/supabase";
import { API_BASE } from "@/api/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ExpertQueueItem {
  analysis_id: string;
  exercise_type: string;
  exercise_variant: string | null;
  confidence_score: number | null;
  form_score_overall: number | null;
  flagged_for_review: boolean;
  created_at: string;
  annotation_count: number;
}

export interface ExpertAnalysisDetail {
  id: string;
  exercise_type: string;
  exercise_variant: string | null;
  confidence_score: number | null;
  form_score_safety: number | null;
  form_score_technique: number | null;
  form_score_path_balance: number | null;
  form_score_control: number | null;
  form_score_overall: number | null;
  summary_json: Record<string, unknown> | null;
  quality_gate_result: Record<string, unknown> | null;
  coaching_result: Record<string, unknown> | null;
  rep_metrics: Record<string, unknown>[];
  retrieval_context: Record<string, unknown> | null;
  eval_scores: Record<string, unknown> | null;
  flagged_for_review: boolean;
  is_golden_dataset: boolean;
  created_at: string;
}

export interface AnnotationCreate {
  issues_identified: Record<string, unknown>;
  coaching_quality_score: number | null;
  injury_advice_accurate: boolean | null;
  engagement_advice_accurate: boolean | null;
  suggested_corrections: string | null;
  cited_sources: Record<string, unknown>[];
  is_golden_label: boolean;
}

export interface AnnotationResponse {
  id: string;
  analysis_id: string;
  annotator_id: string;
  issues_identified: Record<string, unknown>;
  coaching_quality_score: number | null;
  injury_advice_accurate: boolean | null;
  engagement_advice_accurate: boolean | null;
  suggested_corrections: string | null;
  cited_sources: Record<string, unknown>[];
  is_golden_label: boolean;
  created_at: string;
  updated_at: string;
}

export interface RagDocumentResponse {
  id: string;
  title: string;
  source_url: string | null;
  document_type: string;
  exercise_tags: string[];
  chunk_count: number;
  authors: string[];
  year: number | null;
  doi: string | null;
  study_design: string | null;
  quality_tier: string | null;
  quality_score: number | null;
  review_status: string;
  reviewer_id: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

// PaperUploadMetadata — ADR-EXPERT-01 three-phase signed-URL flow.
export interface PaperUploadMetadata {
  title: string;
  document_type?:
    | "research_paper"
    | "textbook"
    | "clinical_guideline"
    | "expert_annotation"
    | "other";
  exercise_tags?: string[];
  authors?: string[];
  year?: number;
  doi?: string;
  study_design?:
    | "rct"
    | "observational"
    | "systematic_review"
    | "narrative_review"
    | "guideline"
    | "other";
  population?: string;
  measurement_method?: string;
  quality_tier?:
    | "L1_systematic_review"
    | "L2_rct"
    | "L3_observational"
    | "L4_guideline";
  filename: string;
  file_size_bytes: number;
}

export interface PaperUploadResponse {
  id: string;
  upload_url: string;
  storage_path: string;
  expires_at: string;
}

export interface PaperCompleteResponse {
  id: string;
  review_status: "pending";
  storage_path: string;
}

export interface PaperReviewAction {
  decision: "reviewed_approved" | "reviewed_rejected" | "needs_revision";
  review_notes?: string;
}

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------

async function getAuthToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("Not authenticated");
  return token;
}

async function expertFetch<T>(path: string, options?: RequestInit): Promise<T> {
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

  if (resp.status === 204) return undefined as unknown as T;
  return resp.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Expert Queue (FR-EXPV-02)
// ---------------------------------------------------------------------------

export async function getExpertQueue(
  limit = 20,
  offset = 0,
  queueType = "all",
): Promise<ExpertQueueItem[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    queue_type: queueType,
  });
  return expertFetch<ExpertQueueItem[]>(`/api/v1/expert/queue?${params}`);
}

// ---------------------------------------------------------------------------
// Analysis Detail (FR-EXPV-03)
// ---------------------------------------------------------------------------

export async function getExpertAnalysis(id: string): Promise<ExpertAnalysisDetail> {
  return expertFetch<ExpertAnalysisDetail>(`/api/v1/expert/analyses/${id}`);
}

// ---------------------------------------------------------------------------
// Annotations (FR-EXPV-04)
// ---------------------------------------------------------------------------

export async function submitAnnotation(
  analysisId: string,
  data: AnnotationCreate,
): Promise<AnnotationResponse> {
  return expertFetch<AnnotationResponse>(
    `/api/v1/expert/analyses/${analysisId}/annotations`,
    { method: "POST", body: JSON.stringify(data) },
  );
}

export async function getAnnotations(analysisId: string): Promise<AnnotationResponse[]> {
  return expertFetch<AnnotationResponse[]>(
    `/api/v1/expert/analyses/${analysisId}/annotations`,
  );
}

// ---------------------------------------------------------------------------
// Paper Upload (FR-EXPV-05) — three-phase signed-URL flow (ADR-EXPERT-01)
// ---------------------------------------------------------------------------

export async function requestPaperUploadUrl(
  data: PaperUploadMetadata,
): Promise<PaperUploadResponse> {
  return expertFetch<PaperUploadResponse>("/api/v1/expert/papers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function completePaperUpload(
  paperId: string,
): Promise<PaperCompleteResponse> {
  return expertFetch<PaperCompleteResponse>(
    `/api/v1/expert/papers/${paperId}/complete`,
    { method: "POST" },
  );
}

export function uploadPaperFile(
  uploadUrl: string,
  file: File,
  onProgress: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", "application/pdf");

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });
    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error(`upload failed: HTTP ${xhr.status}`));
    });
    xhr.addEventListener("error", () =>
      reject(new Error("upload failed: network error")),
    );
    xhr.addEventListener("abort", () => reject(new Error("upload aborted")));

    xhr.send(file);
  });
}

// ---------------------------------------------------------------------------
// Paper Review (FR-EXPV-06)
// ---------------------------------------------------------------------------

export async function reviewPaper(
  docId: string,
  action: PaperReviewAction,
): Promise<{ id: string; title: string; review_status: string }> {
  return expertFetch(`/api/v1/expert/papers/${docId}/review`, {
    method: "PATCH",
    body: JSON.stringify(action),
  });
}

// ---------------------------------------------------------------------------
// Golden Dataset (FR-EXPV-07)
// ---------------------------------------------------------------------------

export async function labelGoldenDataset(
  analysisId: string,
  isGolden: boolean,
): Promise<{ id: string; is_golden_dataset: boolean }> {
  return expertFetch(`/api/v1/expert/analyses/${analysisId}/golden`, {
    method: "PATCH",
    body: JSON.stringify({ is_golden_dataset: isGolden }),
  });
}
