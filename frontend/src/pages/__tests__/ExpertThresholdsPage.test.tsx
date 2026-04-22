import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ExpertThresholdsPage from "@/pages/ExpertThresholdsPage";

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
    createThresholdFlag: vi.fn(),
  };
});

describe("ExpertThresholdsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
});
