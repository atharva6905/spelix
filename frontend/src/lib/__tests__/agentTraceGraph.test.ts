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

  it("treats undefined error as no error (hasError=false)", () => {
    const trace = makeTrace(["get_rep_metrics"]);
    // Explicitly set error to undefined (not null)
    trace.nodes_executed![0].error = undefined as unknown as null;
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[0].data.hasError).toBe(false);
    expect(nodes[0].data.error).toBeUndefined();
  });

  it("handles missing nodes_executed by treating as empty array", () => {
    const trace = makeTrace([]);
    // Simulate missing nodes_executed field
    const traceWithout = { ...trace, nodes_executed: undefined } as unknown as AgentTracePayload;
    const { nodes, edges } = buildTraceGraph(traceWithout);
    expect(nodes).toEqual([]);
    expect(edges).toEqual([]);
  });

  it("sets default empty array for missing output_keys", () => {
    const trace = makeTrace(["get_rep_metrics"]);
    // Remove output_keys to test ?? [] fallback
    trace.nodes_executed![0].output_keys = undefined as unknown as string[];
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[0].data.outputKeys).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// FR-AICP-19 / FR-RESL-07: iterationIndex and toolCallsInvoked fields
// ---------------------------------------------------------------------------

describe("buildTraceGraph — adaptive-mode fields", () => {
  function makeAdaptiveTrace(nodeNames: string[]): AgentTracePayload {
    return {
      mode: "adaptive",
      nodes_executed: nodeNames.map((name, i) => ({
        node: name,
        started_at: `2026-04-17T10:00:${String(i).padStart(2, "0")}Z`,
        duration_ms: 10 + i,
        output_keys: [],
        error: null,
        tool_calls_invoked: name === "reasoner" ? ["get_rep_metrics"] : null,
      })),
      eval_scores: {},
      cove_iterations: [],
      converged: true,
      retrieval_source: null,
      degraded_mode: false,
    };
  }

  it("assigns iterationIndex=1 to the first reasoner node", () => {
    const trace = makeAdaptiveTrace(["reasoner", "validate_output"]);
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[0].data.iterationIndex).toBe(1);
  });

  it("assigns iterationIndex=2 to the second reasoner node", () => {
    const trace = makeAdaptiveTrace(["reasoner", "reasoner", "validate_output"]);
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[0].data.iterationIndex).toBe(1);
    expect(nodes[1].data.iterationIndex).toBe(2);
  });

  it("does not assign iterationIndex to non-reasoner nodes", () => {
    const trace = makeAdaptiveTrace(["reasoner", "validate_output"]);
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[1].data.iterationIndex).toBeUndefined();
  });

  it("propagates toolCallsInvoked from the event to node data", () => {
    const trace = makeAdaptiveTrace(["reasoner"]);
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[0].data.toolCallsInvoked).toEqual(["get_rep_metrics"]);
  });

  it("sets toolCallsInvoked=null for non-reasoner nodes and reasoner turns with no tools", () => {
    const trace: AgentTracePayload = {
      mode: "adaptive",
      nodes_executed: [
        {
          node: "reasoner",
          started_at: "2026-04-17T10:00:00Z",
          duration_ms: 10,
          output_keys: [],
          error: null,
          tool_calls_invoked: null,
        },
        {
          node: "validate_output",
          started_at: "2026-04-17T10:00:01Z",
          duration_ms: 5,
          output_keys: [],
          error: null,
          tool_calls_invoked: null,
        },
      ],
      eval_scores: {},
      cove_iterations: [],
      converged: true,
      retrieval_source: null,
      degraded_mode: false,
    };
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[0].data.toolCallsInvoked).toBeNull();
    expect(nodes[1].data.toolCallsInvoked).toBeNull();
  });

  it("deterministic-mode nodes have no iterationIndex even if named 'reasoner'", () => {
    // deterministic traces should never have iterationIndex set
    const trace = makeTrace(["get_rep_metrics", "retrieve_papers"]);
    const { nodes } = buildTraceGraph(trace);
    expect(nodes[0].data.iterationIndex).toBeUndefined();
    expect(nodes[1].data.iterationIndex).toBeUndefined();
  });
});
