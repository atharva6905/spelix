import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ThresholdFlagModal from "@/components/ThresholdFlagModal";

const baseRow = {
  section: "squat" as const,
  key: "knee_valgus_caution_deg",
  value: 5,
  unit: "degrees",
  provenance_citation: "Myer et al. 2010",
  last_modified_by: "expert_reviewer",
};

describe("ThresholdFlagModal", () => {
  it("is hidden when row is null", () => {
    render(
      <ThresholdFlagModal row={null} onClose={() => {}} onSubmit={async () => {}} />,
    );
    expect(screen.queryByText(/Flag threshold/i)).toBeNull();
  });

  it("disables submit until rationale is 20+ chars and citation is 5+", () => {
    render(
      <ThresholdFlagModal row={baseRow} onClose={() => {}} onSubmit={async () => {}} />,
    );
    const submit = screen.getByRole("button", { name: /submit flag/i });
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/proposed value/i), {
      target: { value: "8" },
    });
    fireEvent.change(screen.getByLabelText(/proposed citation/i), {
      target: { value: "Krosshaug 2016" },
    });
    fireEvent.change(screen.getByLabelText(/rationale/i), {
      target: { value: "An adequate-length rationale explaining why." },
    });
    expect(submit).not.toBeDisabled();
  });

  it("calls onSubmit with the form payload", async () => {
    const handleSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ThresholdFlagModal
        row={baseRow}
        onClose={() => {}}
        onSubmit={handleSubmit}
      />,
    );

    fireEvent.change(screen.getByLabelText(/proposed value/i), {
      target: { value: "8" },
    });
    fireEvent.change(screen.getByLabelText(/proposed citation/i), {
      target: { value: "Krosshaug 2016" },
    });
    fireEvent.change(screen.getByLabelText(/rationale/i), {
      target: {
        value: "An adequate-length rationale explaining why.",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: /submit flag/i }));

    await vi.waitFor(() => {
      expect(handleSubmit).toHaveBeenCalledTimes(1);
    });
    expect(handleSubmit.mock.calls[0][0]).toMatchObject({
      section: "squat",
      key: "knee_valgus_caution_deg",
      proposed_value: 8,
      proposed_citation: "Krosshaug 2016",
      rationale: "An adequate-length rationale explaining why.",
    });
  });

  // -------------------------------------------------------------------------
  // Session 3 (ADR-SAGITTAL-METRICS-REGISTRY): the modal accepts the new
  // section='unvalidated_metrics' produced by UnvalidatedMetricsPanel.
  // -------------------------------------------------------------------------

  it("renders the modal and submits a flag with section='unvalidated_metrics'", async () => {
    const handleSubmit = vi.fn().mockResolvedValue(undefined);
    const unvalidatedRow = {
      section: "unvalidated_metrics" as const,
      key: "ankle_dorsiflexion_deg",
      value: 12.3,
      unit: "deg",
      provenance_citation: null,
      last_modified_by: null,
    };
    render(
      <ThresholdFlagModal
        row={unvalidatedRow}
        onClose={() => {}}
        onSubmit={handleSubmit}
      />,
    );

    // Header still renders the section + key.
    expect(screen.getByText("unvalidated_metrics")).toBeInTheDocument();
    expect(screen.getByText("ankle_dorsiflexion_deg")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/proposed value/i), {
      target: { value: "15.0" },
    });
    fireEvent.change(screen.getByLabelText(/proposed citation/i), {
      target: { value: "Smith 2023" },
    });
    fireEvent.change(screen.getByLabelText(/rationale/i), {
      target: {
        value:
          "Current threshold absent; literature suggests 15 deg minimum.",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: /submit flag/i }));

    await vi.waitFor(() => {
      expect(handleSubmit).toHaveBeenCalledTimes(1);
    });
    const payload = handleSubmit.mock.calls[0][0];
    expect(payload).toMatchObject({
      section: "unvalidated_metrics",
      key: "ankle_dorsiflexion_deg",
      proposed_value: 15.0,
    });
    expect(payload.proposed_citation.length).toBeGreaterThanOrEqual(5);
    expect(payload.rationale.length).toBeGreaterThanOrEqual(20);
  });
});
