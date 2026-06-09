/**
 * Builds xyflow {nodes, edges} from an AgentTracePayload for the P3-007
 * "How AI Reasoned" sidebar.
 *
 * Layout: vertical top-to-bottom, uniform y-spacing. The deterministic
 * graph is a strict 10-node chain and the adaptive graph is
 * reasoner-centric with repeats — both render correctly as a simple
 * sequential chain without xyflow layout plugins.
 *
 * Edges are inferred from execution order (nodes_executed[i] →
 * nodes_executed[i+1]). The trace does not carry input_keys, so true
 * data-dependency edges can't be derived; execution-order edges are
 * accurate for the deterministic graph and a useful approximation for
 * the adaptive reasoner loop.
 */

import { labelForNode } from "@/lib/agentTraceLabels";
import type { AgentTracePayload } from "@/api/analyses";

export interface TraceFlowNodeData {
  label: string;
  rawNode: string;
  durationMs: number;
  outputKeys: string[];
  error: string | null;
  hasError: boolean;
  startedAt: string;
  index: number;
  /** 1-based pass number within the adaptive reasoner loop (adaptive mode only,
   *  undefined for all other nodes and for deterministic-mode traces).
   *  FR-AICP-19 / FR-RESL-07. */
  iterationIndex?: number;
  /** Tool names invoked during this reasoner LLM turn (adaptive mode only).
   *  Null when the LLM issued no tool calls; undefined for non-reasoner nodes.
   *  FR-AICP-19 / FR-RESL-07. */
  toolCallsInvoked?: string[] | null;
}

export interface TraceFlowNode {
  id: string;
  position: { x: number; y: number };
  data: TraceFlowNodeData;
  type?: string;
}

export interface TraceFlowEdge {
  id: string;
  source: string;
  target: string;
  animated?: boolean;
}

export interface TraceGraph {
  nodes: TraceFlowNode[];
  edges: TraceFlowEdge[];
}

const NODE_VERTICAL_SPACING = 96;

export function buildTraceGraph(trace: AgentTracePayload): TraceGraph {
  const events = trace.nodes_executed ?? [];
  const isAdaptive = trace.mode === "adaptive";

  // Pre-compute iteration indices for reasoner nodes (adaptive mode only).
  // iterationCounts[i] is the 1-based pass number for events[i] if it is a
  // "reasoner" node in adaptive mode, otherwise undefined.
  const iterationCountByIndex: (number | undefined)[] = [];
  let reasonerCount = 0;
  for (const ev of events) {
    if (isAdaptive && ev.node === "reasoner") {
      reasonerCount += 1;
      iterationCountByIndex.push(reasonerCount);
    } else {
      iterationCountByIndex.push(undefined);
    }
  }
  // totalReasonerPasses: the sidebar derives total from nodes by finding
  // the highest iterationIndex among the built nodes — no need to pass it
  // separately. The count variable above drives node-level iterationIndex only.

  const nodes: TraceFlowNode[] = events.map((ev, i) => {
    const iterIdx = iterationCountByIndex[i];
    const data: TraceFlowNodeData = {
      label: labelForNode(ev.node),
      rawNode: ev.node,
      durationMs: ev.duration_ms,
      outputKeys: ev.output_keys ?? [],
      error: ev.error,
      hasError: ev.error !== null && ev.error !== undefined,
      startedAt: ev.started_at,
      index: i,
    };
    if (iterIdx !== undefined) {
      data.iterationIndex = iterIdx;
    }
    // Propagate tool_calls_invoked for any event that carries it (including
    // null — null means the LLM turn issued no tools). Undefined means the
    // field was not sent by the backend (deterministic-mode events).
    if ("tool_calls_invoked" in ev) {
      data.toolCallsInvoked = ev.tool_calls_invoked ?? null;
    }
    return {
      id: `node-${i}`,
      position: { x: 0, y: i * NODE_VERTICAL_SPACING },
      data,
    };
  });

  const edges: TraceFlowEdge[] = [];
  for (let i = 0; i < events.length - 1; i++) {
    edges.push({
      id: `edge-${i}`,
      source: `node-${i}`,
      target: `node-${i + 1}`,
    });
  }

  return { nodes, edges };
}
