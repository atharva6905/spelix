/**
 * Tests for agentTraceLabels — plain-English node-name mapping (NFR-USAB-05).
 */

import { describe, it, expect } from "vitest";
import {
  labelForNode,
  labelForOutputKey,
  labelForRetrievalSource,
  labelForToolCall,
  formatDuration,
} from "@/lib/agentTraceLabels";
import type { AgentRetrievalSource } from "@/api/analyses";

describe("labelForNode", () => {
  it("maps every deterministic-graph node to a plain-English label", () => {
    const deterministicNodes = [
      "get_rep_metrics",
      "retrieve_papers",
      "retrieve_coach_brain",
      "flag_form_deviation",
      "compare_to_user_history",
      "generate_correction_plan",
      "validate_output",
      "cove_verify",
      "safety_filter",
      "faithfulness_gate",
    ];
    for (const raw of deterministicNodes) {
      const label = labelForNode(raw);
      // No raw snake_case ever surfaced (NFR-USAB-05)
      expect(label).not.toContain("_");
      expect(label).not.toBe(raw);
      // Labels are sentence-case, not technical jargon
      expect(label.length).toBeGreaterThan(3);
    }
  });

  it("maps the adaptive-graph reasoner node", () => {
    expect(labelForNode("reasoner")).toBe("Chose the next step");
  });

  it("falls back to a safe humanization for unknown node names", () => {
    // The distillation graph or a future extension might emit a node we
    // do not yet have a label for; instead of leaking raw 'snake_case',
    // format it as "Snake case".
    expect(labelForNode("some_new_node")).toBe("Some new node");
  });
});

describe("labelForRetrievalSource", () => {
  it("maps each known retrieval source to plain English", () => {
    expect(labelForRetrievalSource("coach_brain_primary")).toBe(
      "Coach Brain (expert-curated cues)",
    );
    expect(labelForRetrievalSource("hybrid_brain_supplementary")).toBe(
      "Coach Brain + research papers",
    );
    expect(labelForRetrievalSource("papers_only_fallback")).toBe(
      "Research papers only",
    );
  });

  it("returns 'Not retrieved' for null", () => {
    expect(labelForRetrievalSource(null)).toBe("Not retrieved");
  });

  it("humanizes unknown retrieval sources instead of leaking raw snake_case", () => {
    // AgentRetrievalSource is a closed union today, but if the backend adds a
    // new source (e.g. a future dual-collection-fallback variant), the fallback
    // must not surface raw "dual_collection_fallback" to users (NFR-USAB-05).
    const unknownSrc = "dual_collection_fallback" as unknown as AgentRetrievalSource;
    expect(labelForRetrievalSource(unknownSrc)).toBe("Dual collection fallback");
  });
});

describe("labelForOutputKey", () => {
  it("maps known AgentState keys to plain English", () => {
    expect(labelForOutputKey("rep_metrics")).toBe("Rep measurements");
    expect(labelForOutputKey("papers_contexts")).toBe("Research paper excerpts");
    expect(labelForOutputKey("brain_contexts")).toBe("Expert coaching entries");
    expect(labelForOutputKey("coaching_output")).toBe("Coaching feedback");
    expect(labelForOutputKey("cove_verified")).toBe("Verification result");
    expect(labelForOutputKey("eval_scores")).toBe("Quality scores");
  });

  it("humanizes unknown output keys instead of leaking raw snake_case", () => {
    expect(labelForOutputKey("some_future_key")).toBe("Some future key");
  });

  it("never returns a label containing underscores (NFR-USAB-05)", () => {
    const knownKeys = [
      "rep_metrics",
      "papers_contexts",
      "brain_contexts",
      "retrieval_source",
      "flagged_deviations",
      "user_history_summary",
      "coaching_output",
      "cove_verified",
      "eval_scores",
      "degraded_mode",
      "messages",
      "trace",
    ];
    for (const key of knownKeys) {
      expect(labelForOutputKey(key)).not.toContain("_");
    }
  });
});

// ---------------------------------------------------------------------------
// FR-AICP-19 / FR-RESL-07 / NFR-USAB-05: labelForToolCall
// ---------------------------------------------------------------------------

describe("labelForToolCall", () => {
  it("maps known tool names to the same plain-English labels as labelForNode", () => {
    // Tools in adaptive mode share names with deterministic-graph nodes
    expect(labelForToolCall("get_rep_metrics")).toBe("Looked up your rep data");
    expect(labelForToolCall("retrieve_papers")).toBe("Searched research papers");
    expect(labelForToolCall("retrieve_coach_brain")).toBe(
      "Consulted the expert coaching library",
    );
    expect(labelForToolCall("generate_correction_plan")).toBe(
      "Generated your coaching feedback",
    );
  });

  it("falls back to a safe humanization for unknown tool names (NFR-USAB-05)", () => {
    // Unknown tool names must never leak raw snake_case to the user
    expect(labelForToolCall("some_future_tool")).toBe("Some future tool");
  });

  it("never returns a label containing underscores (NFR-USAB-05)", () => {
    const knownTools = [
      "get_rep_metrics",
      "retrieve_papers",
      "retrieve_coach_brain",
      "flag_form_deviation",
      "compare_to_user_history",
      "generate_correction_plan",
    ];
    for (const tool of knownTools) {
      expect(labelForToolCall(tool)).not.toContain("_");
    }
  });
});

describe("formatDuration", () => {
  it("formats sub-second durations as 'Xms'", () => {
    expect(formatDuration(12)).toBe("12ms");
    expect(formatDuration(999)).toBe("999ms");
  });

  it("formats multi-second durations as 'X.Ys'", () => {
    expect(formatDuration(1200)).toBe("1.2s");
    expect(formatDuration(3450)).toBe("3.5s");
  });

  it("handles zero", () => {
    expect(formatDuration(0)).toBe("0ms");
  });
});
