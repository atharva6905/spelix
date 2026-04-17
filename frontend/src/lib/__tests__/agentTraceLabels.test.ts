/**
 * Tests for agentTraceLabels — plain-English node-name mapping (NFR-USAB-05).
 */

import { describe, it, expect } from "vitest";
import {
  labelForNode,
  labelForRetrievalSource,
  formatDuration,
} from "@/lib/agentTraceLabels";

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
