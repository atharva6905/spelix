import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ExpertThresholdsPage from "@/pages/ExpertThresholdsPage";

const mocks = vi.hoisted(() => ({
  getThresholdListing: vi.fn().mockResolvedValue({
    version: "v1",
    sections: {
      squat: [
        {
          section: "squat",
          key: "knee_valgus_caution_deg",
          value: 5,
          unit: "degrees",
          provenance_citation: "Myer et al. 2010",
          last_modified_by: "expert_reviewer",
        },
      ],
      bench: [],
      deadlift: [],
      control: [],
    },
  }),
  listMyThresholdFlags: vi.fn().mockResolvedValue([]),
  createThresholdFlag: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: {
          session: {
            access_token: "tok",
            user: { app_metadata: { role: "expert_reviewer" } },
          },
        },
      }),
    },
  },
}));

vi.mock("@/api/expert", async () => {
  const actual = await vi.importActual<typeof import("@/api/expert")>(
    "@/api/expert",
  );
  return {
    ...actual,
    getThresholdListing: mocks.getThresholdListing,
    listMyThresholdFlags: mocks.listMyThresholdFlags,
    createThresholdFlag: mocks.createThresholdFlag,
  };
});

describe("ExpertThresholdsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Re-apply default mock return values after clearAllMocks
    mocks.getThresholdListing.mockResolvedValue({
      version: "v1",
      sections: {
        squat: [
          {
            section: "squat",
            key: "knee_valgus_caution_deg",
            value: 5,
            unit: "degrees",
            provenance_citation: "Myer et al. 2010",
            last_modified_by: "expert_reviewer",
          },
        ],
        bench: [],
        deadlift: [],
        control: [],
      },
    });
    mocks.listMyThresholdFlags.mockResolvedValue([]);
    mocks.createThresholdFlag.mockResolvedValue(undefined);
  });

  it("renders sections and threshold rows", async () => {
    render(
      <MemoryRouter>
        <ExpertThresholdsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("knee_valgus_caution_deg")).toBeTruthy();
    });
    expect(screen.getByText(/Myer et al. 2010/)).toBeTruthy();
    expect(screen.getByText(/Config version: v1/i)).toBeTruthy();
  });

  it("shows the My Flags tab with empty state", async () => {
    render(
      <MemoryRouter>
        <ExpertThresholdsPage />
      </MemoryRouter>,
    );
    const myFlagsBtn = await screen.findByRole("button", { name: /my flags/i });
    myFlagsBtn.click();

    await waitFor(() => {
      expect(screen.getByText(/No flags submitted yet/i)).toBeTruthy();
    });
  });

  it("does not call loadFlags on initial thresholds tab load", async () => {
    render(
      <MemoryRouter>
        <ExpertThresholdsPage />
      </MemoryRouter>,
    );

    // Wait for the thresholds tab to load data
    await waitFor(() => {
      expect(screen.getByText("knee_valgus_caution_deg")).toBeTruthy();
    });

    // loadFlags (listMyThresholdFlags) should NOT have been called while on thresholds tab
    expect(mocks.listMyThresholdFlags).not.toHaveBeenCalled();
  });

  it("switches to My Flags tab and calls loadFlags after flag submission", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ExpertThresholdsPage />
      </MemoryRouter>,
    );

    // Wait for thresholds tab to load
    await waitFor(() => {
      expect(screen.getByText("knee_valgus_caution_deg")).toBeTruthy();
    });

    // Click the Flag button to open the modal
    const flagBtn = screen.getByRole("button", { name: /^flag$/i });
    await user.click(flagBtn);

    // Fill in required fields so canSubmit becomes true
    const proposedValueInput = screen.getByRole("spinbutton");
    await user.type(proposedValueInput, "10");

    const [citationInput, rationaleInput] = screen.getAllByRole("textbox");
    await user.type(citationInput, "Smith 2020 study");
    await user.type(
      rationaleInput,
      "Current threshold is inconsistent with evidence.",
    );

    // Submit the modal
    const submitBtn = screen.getByRole("button", { name: /submit flag/i });
    await user.click(submitBtn);

    // createThresholdFlag must be called
    await waitFor(() => {
      expect(mocks.createThresholdFlag).toHaveBeenCalled();
    });

    // The my_flags effect fires after tab switch and calls listMyThresholdFlags
    await waitFor(() => {
      expect(mocks.listMyThresholdFlags).toHaveBeenCalled();
    });

    // The "No flags submitted yet" empty state should be visible (flags array is empty mock)
    await waitFor(() => {
      expect(screen.getByText(/No flags submitted yet/i)).toBeTruthy();
    });
  });
});
