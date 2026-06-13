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
  annotated_video_url: string | null;
}

export interface AnnotationCreate {
  issues_identified: Record<string, unknown>;
  coaching_quality_score: number | null;
  movement_advice_accurate: boolean | null;
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
  movement_advice_accurate: boolean | null;
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
  sex_applicability: string;
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
  // Required iff document_type === "research_paper" (FR-EXPV-02, issue #234);
  // omit for DOI-less document types when the field is empty.
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
  sex_applicability?: "male" | "female" | "both";
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

// ---------------------------------------------------------------------------
// Typed transport error (issue #235)
// ---------------------------------------------------------------------------

/**
 * Typed error thrown by {@link expertFetch} for every non-ok response. A real
 * `Error` subclass (not a hand-rolled object literal) so consumers can use
 * `instanceof Error`/`err.message` and the {@link isExpertApiError} guard
 * pins them to the actual transport shape — hand-mocked rejections used to
 * hide drift from both tsc and vitest (PR #233 review finding #1).
 *
 * NOTE (follow-up, issue #235 4th bullet): `beta.ts`, `admin.ts`,
 * `profiles.ts`, and `analyses.ts` still hand-roll the `{ status, ...detail }`
 * throw shape and should migrate to this class. `analyses.ts:263` additionally
 * diverges on spread precedence (`body.error ?? body.detail ?? body`); aligning
 * it touches the core user analysis path and is deferred to that follow-up to
 * keep this PR's blast radius confined to the expert upload surface.
 */
export class ExpertApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly detail?: unknown;

  constructor(args: { status: number; message: string; code?: string; detail?: unknown }) {
    super(args.message);
    this.name = "ExpertApiError";
    this.status = args.status;
    this.code = args.code;
    this.detail = args.detail;
  }
}

/**
 * Type guard for {@link ExpertApiError}. Uses `instanceof` first, then
 * duck-types on `name === "ExpertApiError"` so the guard survives any
 * transpile/realm boundary where `instanceof` could fail.
 */
export function isExpertApiError(e: unknown): e is ExpertApiError {
  if (e instanceof ExpertApiError) return true;
  return (
    typeof e === "object" &&
    e !== null &&
    (e as { name?: unknown }).name === "ExpertApiError" &&
    typeof (e as { status?: unknown }).status === "number"
  );
}

/**
 * Build an {@link ExpertApiError} from a parsed error body. Never throws from
 * the error path itself — every unexpected shape falls back to a safe message.
 */
function buildExpertApiError(status: number, body: unknown): ExpertApiError {
  const fallback = `Request failed (HTTP ${status}).`;
  const detail =
    typeof body === "object" && body !== null
      ? (body as { detail?: unknown }).detail
      : undefined;

  // FastAPI structured error: { detail: { error: { code, message } } }
  if (typeof detail === "object" && detail !== null && !Array.isArray(detail)) {
    const errObj = (detail as { error?: unknown }).error;
    if (typeof errObj === "object" && errObj !== null) {
      const code = (errObj as { code?: unknown }).code;
      const message = (errObj as { message?: unknown }).message;
      return new ExpertApiError({
        status,
        code: typeof code === "string" ? code : undefined,
        message: typeof message === "string" ? message : fallback,
        detail,
      });
    }
    // Plain detail object (e.g. { detail: { code: "NOT_FOUND" } }).
    const code = (detail as { code?: unknown }).code;
    const message = (detail as { message?: unknown }).message;
    return new ExpertApiError({
      status,
      code: typeof code === "string" ? code : undefined,
      message: typeof message === "string" ? message : fallback,
      detail,
    });
  }

  // Pydantic validation: detail is an array of {loc, msg, type}. No code.
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown } | undefined;
    const msg = first && typeof first.msg === "string" ? first.msg : fallback;
    return new ExpertApiError({ status, message: msg, detail });
  }

  // Plain string detail.
  if (typeof detail === "string") {
    return new ExpertApiError({ status, message: detail, detail });
  }

  // No detail field: fall back to a top-level message/code if the body has one,
  // else the safe fallback. Preserves the pre-#235 top-level-spread behaviour.
  if (typeof body === "object" && body !== null) {
    const code = (body as { code?: unknown }).code;
    const message = (body as { message?: unknown }).message;
    return new ExpertApiError({
      status,
      code: typeof code === "string" ? code : undefined,
      message: typeof message === "string" ? message : fallback,
    });
  }

  return new ExpertApiError({ status, message: fallback });
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
    throw buildExpertApiError(resp.status, body);
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
// Paper Metadata Edit (issue #223, FR-RAGK-05 ext.)
// ---------------------------------------------------------------------------

// Editable post-upload metadata; backend restamps existing Qdrant points
// via set_payload (no re-embed).
export interface PaperMetadataPatch {
  sex_applicability: "male" | "female" | "both";
}

// Shared select options for sex_applicability (issue #223, FR-RAGK-05 ext.)
// — single source of truth for ExpertPaperUploadPage + ExpertPortalPage.
export const SEX_APPLICABILITY_OPTIONS = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "both", label: "Both" },
] as const satisfies ReadonlyArray<{
  value: PaperMetadataPatch["sex_applicability"];
  label: string;
}>;

// `restamp_failed` is true when the DB write committed but the papers_rag
// Qdrant payload restamp failed; the backend enqueues a retry task to
// reconcile it (issue #258, FR-RAGK-05/FR-AICP-12 ext.).
export async function updatePaperMetadata(
  docId: string,
  patch: PaperMetadataPatch,
): Promise<{ id: string; sex_applicability: string; restamp_failed: boolean }> {
  return expertFetch(`/api/v1/expert/papers/${docId}/metadata`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

// ---------------------------------------------------------------------------
// My Papers (expert-uploaded documents)
// ---------------------------------------------------------------------------

export async function listExpertPapers(
  limit = 20,
  offset = 0,
): Promise<RagDocumentResponse[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return expertFetch<RagDocumentResponse[]>(`/api/v1/expert/papers?${params}`);
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

// ---------------------------------------------------------------------------
// Threshold Validation (FR-EXPV-08)
// ---------------------------------------------------------------------------

// Session 3 (ADR-SAGITTAL-METRICS-REGISTRY): expert reviewers can flag
// Unvalidated-Metrics rows via FR-EXPV-08 even though those keys don't yet
// have current-value entries in config/thresholds_v1.json. The backend
// service short-circuits the config lookup when section ===
// "unvalidated_metrics".
export type ThresholdSection =
  | "squat"
  | "bench"
  | "deadlift"
  | "control"
  | "unvalidated_metrics";

export interface ThresholdRow {
  section: ThresholdSection;
  key: string;
  value: number;
  unit: string;
  provenance_citation: string | null;
  last_modified_by: string | null;
}

export interface ThresholdListing {
  version: string;
  // The /thresholds endpoint only populates the four config-backed sections;
  // `unvalidated_metrics` rows never appear in this response. The Record key
  // is still typed as ThresholdSection for ergonomic indexing from callers
  // that already hold a ThresholdSection.
  sections: Partial<Record<ThresholdSection, ThresholdRow[]>>;
}

export interface ThresholdFlagCreate {
  section: ThresholdSection;
  key: string;
  proposed_value: number;
  proposed_citation: string;
  rationale: string;
}

export interface ThresholdFlagResponse {
  id: string;
  reviewer_id: string;
  section: ThresholdSection;
  key: string;
  current_value: number;
  current_citation: string | null;
  proposed_value: number;
  proposed_citation: string;
  rationale: string;
  status: "open" | "resolved" | "rejected";
  resolution_note: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Sagittal Metrics Registry (Session 3, L2-SAGITTAL-INFRA-02,
// ADR-SAGITTAL-METRICS-REGISTRY)
// ---------------------------------------------------------------------------

export interface SagittalMetricRegistryEntry {
  key_name: string;
  display_label: string;
  unit: string;
  description: string;
  exercise_applicability: Array<"squat" | "bench" | "deadlift">;
  computed_yet: boolean;
  in_scoring: boolean;
}

export interface SagittalMetricRegistryResponse {
  entries: SagittalMetricRegistryEntry[];
}

export async function getSagittalMetricsRegistry(): Promise<SagittalMetricRegistryResponse> {
  return expertFetch<SagittalMetricRegistryResponse>(
    "/api/v1/expert/sagittal-metrics-registry",
  );
}

export async function getThresholdListing(): Promise<ThresholdListing> {
  return expertFetch<ThresholdListing>("/api/v1/expert/thresholds");
}

export async function createThresholdFlag(
  payload: ThresholdFlagCreate,
): Promise<ThresholdFlagResponse> {
  return expertFetch<ThresholdFlagResponse>("/api/v1/expert/thresholds/flags", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listMyThresholdFlags(
  limit = 20,
  offset = 0,
): Promise<ThresholdFlagResponse[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return expertFetch<ThresholdFlagResponse[]>(
    `/api/v1/expert/thresholds/flags?${params}`,
  );
}
