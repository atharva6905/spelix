/**
 * Plain-English labels for agent trace nodes (NFR-USAB-05).
 *
 * NFR-USAB-05: "Agent reasoning sidebar uses plain English; no raw JSON
 * or technical trace format exposed to users."
 *
 * When backend adds a new node, add its plain-English label here. If a
 * node label is missing we fall back to a safe humanisation — better to
 * ship a slightly generic label than to surface raw snake_case.
 */

import type { AgentRetrievalSource } from "@/api/analyses";

const NODE_LABELS: Record<string, string> = {
  // Deterministic graph (FR-AICP-18)
  get_rep_metrics: "Looked up your rep data",
  retrieve_papers: "Searched research papers",
  retrieve_coach_brain: "Consulted the expert coaching library",
  flag_form_deviation: "Checked your form for deviations",
  compare_to_user_history: "Compared to your past sessions",
  generate_correction_plan: "Generated your coaching feedback",
  validate_output: "Validated the coaching output",
  cove_verify: "Double-checked claims against sources",
  safety_filter: "Applied the safety filter",
  faithfulness_gate: "Verified faithfulness to sources",
  // Adaptive graph (FR-AICP-19)
  reasoner: "Chose the next step",
};

export function labelForNode(rawNodeName: string): string {
  const known = NODE_LABELS[rawNodeName];
  if (known) return known;
  // Safe fallback: sentence-case the snake_case name.
  const humanized = rawNodeName.replace(/_/g, " ");
  return humanized.charAt(0).toUpperCase() + humanized.slice(1);
}

const RETRIEVAL_SOURCE_LABELS: Record<string, string> = {
  coach_brain_primary: "Coach Brain (expert-curated cues)",
  hybrid_brain_supplementary: "Coach Brain + research papers",
  papers_only_fallback: "Research papers only",
};

export function labelForRetrievalSource(src: AgentRetrievalSource): string {
  if (src === null || src === undefined) return "Not retrieved";
  return RETRIEVAL_SOURCE_LABELS[src] ?? src;
}

export function formatDuration(durationMs: number): string {
  if (durationMs < 1000) {
    return `${Math.round(durationMs)}ms`;
  }
  return `${(durationMs / 1000).toFixed(1)}s`;
}
