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

  const nodes: TraceFlowNode[] = events.map((ev, i) => ({
    id: `node-${i}`,
    position: { x: 0, y: i * NODE_VERTICAL_SPACING },
    data: {
      label: labelForNode(ev.node),
      rawNode: ev.node,
      durationMs: ev.duration_ms,
      outputKeys: ev.output_keys ?? [],
      error: ev.error,
      hasError: ev.error !== null && ev.error !== undefined,
      startedAt: ev.started_at,
      index: i,
    },
  }));

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
