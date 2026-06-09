/**
 * Centralized API calls for the analyses resource.
 * Requirements: FR-UPLD-01 through FR-UPLD-09, FR-XDET-01, FR-RESL-13, NFR-RELI-06
 */

import { supabase } from "@/lib/supabase";
import { API_BASE } from "@/api/config";

/**
 * Convention: strings thrown from fetch functions below are surfaced directly
 * to users by useAnalysisDetail's catch branch (no wrapping). If a fetch
 * function throws a bare string, it MUST be user-safe — never an internal
 * backend detail (e.g., raw 4xx/5xx bodies, RLS violation text, stack traces).
 * Wrap anything user-unsafe in `new Error(userSafeMessage)` so the hook
 * still displays a readable fallback.
 */

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

export interface DetectionResult {
  detected_type: ExerciseType;
  detected_variant: string;
  confidence: number;
  method: "heuristic" | "vision_fallback";
  details?: Record<string, unknown> | null;
}

export interface AnalysisStatusResponse {
  id: string;
  status: AnalysisStatus;
  updated_at: string;
  detection_result?: DetectionResult | null;
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
  citation_indices?: number[];
}

export interface Citation {
  title: string;
  authors: string[];
  year: number;
  doi?: string | null;
}

export interface CoachingOutput {
  summary: string;
  strengths: string[];
  issues: CoachingIssue[];
  correction_plan: string[];
  disclaimer: string;
  // Phase 1 extended fields (FR-AICP-03, FR-AICP-06)
  recommended_cues?: string[];
  citations?: Citation[];
  confidence_level?: string;
  safety_warnings?: string[];
  dimension_addressed?: string;
  // Phase 2 fields (P2-019)
  degraded_mode?: boolean;
}

// ---------------------------------------------------------------------------
// Types — Agent trace (P3-007, FR-RESL-07, NFR-USAB-05)
//
// Shape produced by backend/app/agents/graph.py::run_coaching_graph and
// persisted to coaching_results.agent_trace_json JSONB.
//
// IMPORTANT — two producers write this column:
//   1. Phase 3 graph path (analysis_worker.py:~802) writes the FULL shape:
//      mode / nodes_executed / eval_scores / cove_iterations / converged
//      / retrieval_source / degraded_mode. Emitted when
//      SPELIX_PHASE3_AGENT_ENABLED=1 (prod since session 32).
//   2. Phase 2 imperative path (analysis_worker.py:~483) writes a PARTIAL
//      shape: only { cove_iterations, converged }. Fired when the agent
//      flag is off.
//
// Legacy Phase 1 / earlier analyses carry null.
//
// Every field is therefore optional — the sidebar guards access via
// optional chaining and the "How AI Reasoned" button only renders when
// nodes_executed.length > 0, which distinguishes Phase 3 writes from
// Phase 2 partials and from legacy nulls in one check.
// ---------------------------------------------------------------------------

export interface AgentNodeEvent {
  node: string;
  started_at: string; // ISO-8601 UTC
  duration_ms: number;
  output_keys: string[];
  error: string | null;
  /** Tool names called during this LLM turn (adaptive reasoner nodes only).
   *  Null for deterministic-mode events and reasoner turns with no tool calls.
   *  FR-AICP-19 / FR-RESL-07. */
  tool_calls_invoked?: string[] | null;
}

export interface AgentEvalScores {
  faithfulness?: number;
  cove_verified?: boolean;
  // open-ended: Phase 4 eval metrics land here (groundedness, etc.)
  [key: string]: unknown;
}

export type AgentRetrievalSource =
  | "coach_brain_primary"
  | "hybrid_brain_supplementary"
  | "papers_only_fallback"
  | null;

export interface AgentTracePayload {
  mode?: "deterministic" | "adaptive";
  nodes_executed?: AgentNodeEvent[];
  eval_scores?: AgentEvalScores;
  cove_iterations?: unknown[];
  converged?: boolean;
  retrieval_source?: AgentRetrievalSource;
  degraded_mode?: boolean;
  /** FR-AICP-20 / P3-007: LangSmith root-run id. Present only when LangSmith
   *  tracing was enabled for the run. Used by admin-only "View in LangSmith"
   *  link in AgentReasoningSidebar. */
  langsmith_run_id?: string | null;
}

export interface CoachingResultDetail {
  structured_output_json: CoachingOutput | null;
  agent_trace_json: AgentTracePayload | null;
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
  // Phase 1 form scores (FR-SCOR-01 through FR-SCOR-05)
  form_score_safety?: number | null;
  form_score_technique?: number | null;
  form_score_path_balance?: number | null;
  form_score_control?: number | null;
  form_score_overall?: number | null;
  detection_result?: DetectionResult | null;
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
 * Used as polling fallback when Supabase Realtime is unavailable, and for initial state fetch.
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
    const raw = body.error?.message ?? body.detail;
    const message =
      typeof raw === "string" ? raw : "Failed to fetch status";
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
    const raw = body.error?.message ?? body.detail;
    const message =
      typeof raw === "string" ? raw : "Failed to fetch analysis";
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
    const raw = body.error?.message ?? body.detail;
    const message =
      typeof raw === "string" ? raw : "Failed to fetch analyses";
    throw new Error(message);
  }

  return resp.json() as Promise<AnalysisListResponse>;
}

// ---------------------------------------------------------------------------
// Types — Chat (P2-022, FR-RESL-09, FR-AICP-17)
// ---------------------------------------------------------------------------

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ChatHistoryResponse {
  messages: ChatMessage[];
}

// ---------------------------------------------------------------------------
// API — Chat
// ---------------------------------------------------------------------------

export async function getChatHistory(
  analysisId: string,
): Promise<ChatHistoryResponse> {
  const token = await getAuthToken();
  const resp = await fetch(
    `${API_BASE}/api/v1/analyses/${analysisId}/chat`,
    { headers: { Authorization: `Bearer ${token}` } },
  );

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail ?? "Failed to fetch chat history");
  }

  return resp.json() as Promise<ChatHistoryResponse>;
}

export async function sendChatMessage(
  analysisId: string,
  content: string,
): Promise<ChatMessage> {
  const token = await getAuthToken();
  const resp = await fetch(
    `${API_BASE}/api/v1/analyses/${analysisId}/chat`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content }),
    },
  );

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail ?? "Failed to send message");
  }

  return resp.json() as Promise<ChatMessage>;
}
