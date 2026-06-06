/**
 * Tests for AgentReasoningSidebar — P3-007 "How AI Reasoned" drawer.
 *
 * NFR-USAB-05: plain English only, no raw node names surfaced.
 * FR-RESL-07: renders LangGraph agent trace.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AgentReasoningSidebar } from "@/components/AgentReasoningSidebar";
import type { AgentTracePayload } from "@/api/analyses";

// xyflow renders its own SVG + DOM; we don't need to assert against it
// to verify the component's responsibilities. Instead we verify that
// nodes are passed through and our component's own chrome (header,
// detail pane, summary) render correctly.
interface MockFlowNode {
  id: string;
  data: { label: string; rawNode: string };
}

vi.mock("@xyflow/react", () => ({
  ReactFlow: ({
    nodes,
    onNodeClick,
  }: {
    nodes: MockFlowNode[];
    onNodeClick?: (event: unknown, node: MockFlowNode) => void;
  }) => (
    <div data-testid="reactflow-canvas">
      {nodes.map((n) => (
        <button
          key={n.id}
          data-testid={`flow-node-${n.id}`}
          onClick={(e) => onNodeClick?.(e, n)}
        >
          {n.data.label}
        </button>
      ))}
    </div>
  ),
  Background: () => <div data-testid="reactflow-bg" />,
  Controls: () => <div data-testid="reactflow-controls" />,
}));

// Stub the xyflow stylesheet import so vitest doesn't try to parse CSS.
vi.mock("@xyflow/react/dist/style.css", () => ({}));

function makeTrace(
  overrides: Partial<AgentTracePayload> = {},
): AgentTracePayload {
  return {
    mode: "deterministic",
    nodes_executed: [
      {
        node: "get_rep_metrics",
        started_at: "2026-04-17T10:00:00Z",
        duration_ms: 12.3,
        output_keys: ["rep_metrics"],
        error: null,
      },
      {
        node: "retrieve_papers",
        started_at: "2026-04-17T10:00:01Z",
        duration_ms: 456,
        output_keys: ["papers_contexts"],
        error: null,
      },
      {
        node: "cove_verify",
        started_at: "2026-04-17T10:00:02Z",
        duration_ms: 2100,
        output_keys: ["cove_verified", "eval_scores"],
        error: null,
      },
    ],
    eval_scores: { faithfulness: 0.92, cove_verified: true },
    cove_iterations: [{ pass: 1 }],
    converged: true,
    retrieval_source: "coach_brain_primary",
    degraded_mode: false,
    ...overrides,
  };
}

describe("AgentReasoningSidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when isOpen=false", () => {
    const { container } = render(
      <AgentReasoningSidebar
        isOpen={false}
        trace={makeTrace()}
        onClose={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when trace is null", () => {
    const { container } = render(
      <AgentReasoningSidebar isOpen={true} trace={null} onClose={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the drawer with header, reactflow canvas, and summary when isOpen and trace has nodes", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("agent-reasoning-sidebar")).toBeInTheDocument();
    expect(screen.getByText(/How AI Reasoned/i)).toBeInTheDocument();
    expect(screen.getByTestId("reactflow-canvas")).toBeInTheDocument();
  });

  it("uses plain-English node labels (NFR-USAB-05) — no raw snake_case", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText("Looked up your rep data")).toBeInTheDocument();
    expect(screen.getByText("Searched research papers")).toBeInTheDocument();
    expect(
      screen.getByText("Double-checked claims against sources"),
    ).toBeInTheDocument();
    // Raw names must not appear anywhere in visible DOM
    expect(screen.queryByText(/get_rep_metrics/)).not.toBeInTheDocument();
    expect(screen.queryByText(/cove_verify/)).not.toBeInTheDocument();
  });

  it("shows retrieval source as plain English", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace()}
        onClose={vi.fn()}
      />,
    );
    expect(
      screen.getByText(/Coach Brain \(expert-curated cues\)/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/coach_brain_primary/),
    ).not.toBeInTheDocument();
  });

  it("shows a degraded-mode banner when degraded_mode=true", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace({ degraded_mode: true })}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("agent-trace-degraded-banner")).toBeInTheDocument();
  });

  it("does NOT show the degraded banner when degraded_mode=false", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace({ degraded_mode: false })}
        onClose={vi.fn()}
      />,
    );
    expect(
      screen.queryByTestId("agent-trace-degraded-banner"),
    ).not.toBeInTheDocument();
  });

  it("shows CoVe verification status (green when cove_verified=true)", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace({
          eval_scores: { cove_verified: true, faithfulness: 0.9 },
        })}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("cove-status")).toHaveTextContent(/verified/i);
  });

  it("shows CoVe verification status (warning when cove_verified=false)", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace({
          eval_scores: { cove_verified: false, faithfulness: 0.5 },
        })}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("cove-status")).toHaveTextContent(/not verified/i);
  });

  it("clicking a node opens the detail pane with duration, output keys, and no error", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace()}
        onClose={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("flow-node-node-1"));
    const detail = screen.getByTestId("agent-trace-node-detail");
    expect(detail).toHaveTextContent("Searched research papers");
    expect(detail).toHaveTextContent(/456ms/);
    // NFR-USAB-05: output keys shown with plain-English labels, never raw snake_case
    expect(detail).toHaveTextContent("Research paper excerpts");
    expect(detail).not.toHaveTextContent(/papers_contexts/);
    expect(detail).not.toHaveTextContent(/error/i);
  });

  it("clicking a node with an error shows the error in the detail pane", () => {
    const trace = makeTrace();
    trace.nodes_executed![1].error = "Qdrant timeout";
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={trace}
        onClose={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("flow-node-node-1"));
    const detail = screen.getByTestId("agent-trace-node-detail");
    expect(detail).toHaveTextContent(/Qdrant timeout/);
  });

  it("clicking the close button fires onClose", () => {
    const onClose = vi.fn();
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace()}
        onClose={onClose}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("moves keyboard focus to the Close button when opened (a11y dialog pattern)", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /close/i })).toHaveFocus();
  });

  it("renders the drawer with role=dialog + aria-modal + aria-labelledby (a11y)", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace()}
        onClose={vi.fn()}
      />,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute(
      "aria-labelledby",
      "agent-reasoning-sidebar-title",
    );
    expect(document.getElementById("agent-reasoning-sidebar-title")).toHaveTextContent(
      /How AI Reasoned/i,
    );
  });

  it("Escape key closes the sidebar", () => {
    const onClose = vi.fn();
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace()}
        onClose={onClose}
      />,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("handles empty nodes_executed (renders drawer but no graph + friendly empty message)", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace({ nodes_executed: [] })}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("agent-reasoning-sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("agent-trace-empty")).toBeInTheDocument();
  });

  it("formats durations as human-readable (NFR-USAB-05)", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace()}
        onClose={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("flow-node-node-2"));
    // 2100ms should display as "2.1s", not "2100" or "2100ms"
    expect(screen.getByTestId("agent-trace-node-detail")).toHaveTextContent(
      /2\.1s/,
    );
  });

  it("Tab from the last focusable element wraps focus to the first (focus trap)", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace()}
        onClose={vi.fn()}
      />,
    );
    const drawer = screen.getByTestId("agent-reasoning-sidebar");
    const focusableEnabled = Array.from(
      drawer.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((el) => !(el as HTMLButtonElement).disabled);
    // Place focus on the last focusable element.
    focusableEnabled[focusableEnabled.length - 1].focus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: false });
    expect(focusableEnabled[0]).toHaveFocus();
  });

  it("Shift+Tab from the first focusable element wraps focus to the last (focus trap)", () => {
    render(
      <AgentReasoningSidebar
        isOpen={true}
        trace={makeTrace()}
        onClose={vi.fn()}
      />,
    );
    const drawer = screen.getByTestId("agent-reasoning-sidebar");
    const focusableEnabled = Array.from(
      drawer.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((el) => !(el as HTMLButtonElement).disabled);
    // Place focus on the first focusable element.
    focusableEnabled[0].focus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(focusableEnabled[focusableEnabled.length - 1]).toHaveFocus();
  });
});
