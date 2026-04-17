/**
 * AgentReasoningSidebar — P3-007 "How AI Reasoned" drawer.
 *
 * Renders coaching_results.agent_trace_json as:
 *   - summary header (mode, retrieval source, degraded banner, CoVe
 *     status, faithfulness score),
 *   - xyflow graph of executed nodes (vertical chain, clickable),
 *   - detail pane for the selected node (duration, output keys, error).
 *
 * Plain-English labels throughout (NFR-USAB-05). No raw JSON surfaced.
 *
 * FR-RESL-07, NFR-USAB-05.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node as FlowNode,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import {
  formatDuration,
  labelForOutputKey,
  labelForRetrievalSource,
} from "@/lib/agentTraceLabels";
import {
  buildTraceGraph,
  type TraceFlowNodeData,
} from "@/lib/agentTraceGraph";
import type { AgentTracePayload } from "@/api/analyses";

interface AgentReasoningSidebarProps {
  isOpen: boolean;
  trace: AgentTracePayload | null;
  onClose: () => void;
}

export function AgentReasoningSidebar({
  isOpen,
  trace,
  onClose,
}: AgentReasoningSidebarProps) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  // Reset selection whenever the trace changes OR drawer closes.
  useEffect(() => {
    if (!isOpen) setSelectedIndex(null);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  // Move initial focus to the close button on open (a11y — dialog pattern).
  useEffect(() => {
    if (isOpen) closeButtonRef.current?.focus();
  }, [isOpen]);

  const graph = useMemo(
    () => (trace ? buildTraceGraph(trace) : { nodes: [], edges: [] }),
    [trace],
  );

  const handleNodeClick = useCallback(
    (_e: MouseEvent, node: FlowNode) => {
      const data = node.data as unknown as TraceFlowNodeData;
      setSelectedIndex(data.index);
    },
    [],
  );

  if (!isOpen || !trace) return null;

  const nodesExecuted = trace.nodes_executed ?? [];
  const selectedEvent =
    selectedIndex !== null ? nodesExecuted[selectedIndex] : null;
  const selectedData =
    selectedIndex !== null ? graph.nodes[selectedIndex]?.data : null;

  const coveVerified = Boolean(trace.eval_scores?.cove_verified);
  const faithfulness =
    typeof trace.eval_scores?.faithfulness === "number"
      ? (trace.eval_scores.faithfulness as number)
      : null;

  return (
    <>
      {/* Scrim */}
      <div
        aria-hidden="true"
        className="fixed inset-0 z-40 bg-black/20"
        onClick={onClose}
      />
      {/* Drawer */}
      <div
        data-testid="agent-reasoning-sidebar"
        role="dialog"
        aria-modal="true"
        aria-labelledby="agent-reasoning-sidebar-title"
        className="fixed right-0 top-0 z-50 flex h-screen w-full max-w-2xl flex-col bg-white shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h2
              id="agent-reasoning-sidebar-title"
              className="text-lg font-semibold text-gray-900"
            >
              How AI Reasoned
            </h2>
            <p className="mt-0.5 text-xs text-gray-500">
              A step-by-step look at how your coaching was produced.
            </p>
          </div>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.8}
              stroke="currentColor"
              className="h-5 w-5"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Summary */}
        <div className="space-y-3 border-b border-gray-200 px-6 py-4">
          {trace.degraded_mode && (
            <div
              data-testid="agent-trace-degraded-banner"
              className="rounded-md border-l-4 border-yellow-400 bg-yellow-50 px-3 py-2 text-xs text-yellow-800"
            >
              Research retrieval was unavailable for this analysis — coaching
              was produced without paper citations.
            </div>
          )}

          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <div>
              <dt className="font-medium uppercase tracking-wide text-gray-500">
                Sources
              </dt>
              <dd className="mt-0.5 text-gray-800">
                {labelForRetrievalSource(trace.retrieval_source ?? null)}
              </dd>
            </div>
            <div>
              <dt className="font-medium uppercase tracking-wide text-gray-500">
                Verification
              </dt>
              <dd
                data-testid="cove-status"
                className={`mt-0.5 ${
                  coveVerified ? "text-green-700" : "text-amber-700"
                }`}
              >
                {coveVerified
                  ? "Claims verified against sources"
                  : "Claims not verified — review manually"}
              </dd>
            </div>
            {faithfulness !== null && (
              <div>
                <dt className="font-medium uppercase tracking-wide text-gray-500">
                  Faithfulness
                </dt>
                <dd className="mt-0.5 text-gray-800">
                  {(faithfulness * 100).toFixed(0)}%
                </dd>
              </div>
            )}
            <div>
              <dt className="font-medium uppercase tracking-wide text-gray-500">
                Steps executed
              </dt>
              <dd className="mt-0.5 text-gray-800">
                {nodesExecuted.length}
              </dd>
            </div>
          </dl>
        </div>

        {/* Graph */}
        <div className="flex-1 overflow-hidden">
          {graph.nodes.length === 0 ? (
            <div
              data-testid="agent-trace-empty"
              className="flex h-full items-center justify-center px-6 text-center text-sm text-gray-500"
            >
              No steps were recorded for this analysis.
            </div>
          ) : (
            <div className="h-full w-full">
              <ReactFlow
                nodes={graph.nodes as unknown as FlowNode[]}
                edges={graph.edges}
                onNodeClick={handleNodeClick}
                fitView
                proOptions={{ hideAttribution: true }}
                nodesDraggable={false}
                nodesConnectable={false}
              >
                <Background />
                <Controls showInteractive={false} />
              </ReactFlow>
            </div>
          )}
        </div>

        {/* Detail pane */}
        {selectedEvent && selectedData && (
          <div
            data-testid="agent-trace-node-detail"
            className="border-t border-gray-200 bg-gray-50 px-6 py-4"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-sm font-semibold text-gray-900">
                  {selectedData.label}
                </h3>
                <p className="mt-0.5 text-xs text-gray-500">
                  Took {formatDuration(selectedData.durationMs)}
                </p>
              </div>
              <button
                onClick={() => setSelectedIndex(null)}
                aria-label="Close step details"
                className="rounded-md p-1 text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </div>
            {selectedData.outputKeys.length > 0 && (
              <div className="mt-3">
                <div className="text-xs font-medium uppercase tracking-wide text-gray-500">
                  Produced
                </div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {selectedData.outputKeys.map((k) => (
                    <span
                      key={k}
                      className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-700 ring-1 ring-inset ring-gray-200"
                    >
                      {labelForOutputKey(k)}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {selectedData.error && (
              <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-800">
                <span className="font-medium">Error:</span> {selectedData.error}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

export default AgentReasoningSidebar;
