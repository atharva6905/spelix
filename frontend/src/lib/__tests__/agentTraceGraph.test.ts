/**
 * Tests for agentTraceGraph — builds xyflow nodes/edges from AgentTracePayload.
 */

import { describe, it, expect } from "vitest";
import { buildTraceGraph } from "@/lib/agentTraceGraph";
import type { AgentTracePayload } from "@/api/analyses";

function makeTrace(nodeNames: string[]): AgentTracePayload {
  return {
    mode: "deterministic",
    nodes_executed: nodeNames.map((name, i) => ({
      node: name,
      started_at: `2026-04-17T10:00:${String(i).padStart(2, "0")}Z`,
      duration_ms: 10 + i,
      output_keys: [`key_${i}`],
      error: null,
    })),
    eval_scores: {},
    cove_iterations: [],
    converged: true,
    retrieval_source: "coach_brain_primary",
    degraded_mode: false,
  };
}

describe("buildTraceGraph", () => {
  it("produces one xyflow node per trace event", () => {
    const trace = makeTrace(["get_rep_metrics", "retrieve_papers"]);
    const { nodes } = buildTraceGraph(trace);
    expect(nodes).toHaveLength(2);
    expect(nodes[0].id).toBe("node-0");
    expect(nodes[1].id).toBe("node-1");
  });

  it("applies plain-English labels to node data", () => {
    const trace = makeTrace(["get_rep_metrics", "retrieve_papers"]);
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[0].data.label).toBe("Looked up your rep data");
    expect(nodes[1].data.label).toBe("Searched research papers");
  });

  it("preserves raw node name, duration, output_keys, and error in node data", () => {
    const trace = makeTrace(["get_rep_metrics"]);
    trace.nodes_executed![0].error = "boom";
    trace.nodes_executed![0].duration_ms = 123.4;
    trace.nodes_executed![0].output_keys = ["rep_metrics", "foo"];
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[0].data.rawNode).toBe("get_rep_metrics");
    expect(nodes[0].data.durationMs).toBe(123.4);
    expect(nodes[0].data.outputKeys).toEqual(["rep_metrics", "foo"]);
    expect(nodes[0].data.error).toBe("boom");
  });

  it("lays nodes out vertically top-to-bottom", () => {
    const trace = makeTrace(["a", "b", "c"]);
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[0].position).toEqual({ x: 0, y: 0 });
    expect(nodes[1].position.y).toBeGreaterThan(nodes[0].position.y);
    expect(nodes[2].position.y).toBeGreaterThan(nodes[1].position.y);
    expect(nodes.every((n) => n.position.x === 0)).toBe(true);
  });

  it("produces one edge between each sequential pair of nodes", () => {
    const trace = makeTrace(["a", "b", "c"]);
    const { edges } = buildTraceGraph(trace);
    expect(edges).toHaveLength(2);
    expect(edges[0]).toMatchObject({ source: "node-0", target: "node-1" });
    expect(edges[1]).toMatchObject({ source: "node-1", target: "node-2" });
  });

  it("produces zero edges for a single-node trace", () => {
    const trace = makeTrace(["only"]);
    const { edges } = buildTraceGraph(trace);
    expect(edges).toHaveLength(0);
  });

  it("produces empty nodes and edges for an empty trace", () => {
    const trace = makeTrace([]);
    const { nodes, edges } = buildTraceGraph(trace);
    expect(nodes).toEqual([]);
    expect(edges).toEqual([]);
  });

  it("marks error nodes so the component can style them", () => {
    const trace = makeTrace(["get_rep_metrics", "retrieve_papers"]);
    trace.nodes_executed![1].error = "timeout";
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[0].data.hasError).toBe(false);
    expect(nodes[1].data.hasError).toBe(true);
  });

  it("handles adaptive-mode repeated node names with unique IDs", () => {
    // The adaptive reasoner can call the same tool twice. The node IDs
    // must be unique so xyflow doesn't collide.
    const trace = makeTrace(["reasoner", "retrieve_papers", "reasoner"]);
    const { nodes, edges } = buildTraceGraph(trace);
    expect(nodes.map((n) => n.id)).toEqual(["node-0", "node-1", "node-2"]);
    expect(edges.map((e) => `${e.source}->${e.target}`)).toEqual([
      "node-0->node-1",
      "node-1->node-2",
    ]);
  });
});
