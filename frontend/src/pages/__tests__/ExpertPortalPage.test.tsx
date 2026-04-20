/**
 * Tests for ExpertPortalPage.
 *
 * Requirements: FR-EXPV-01 (role check), FR-EXPV-02 (review queue)
 *
 * TDD gates:
 *   1. Renders queue heading for authorized expert
 *   2. Displays queue items with exercise type
 *   3. Shows confidence as categorical label, never decimal (NFR-USAB-03)
 *   4. Has links to detail pages
 *   5. Redirects non-expert users
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";

// ---------------------------------------------------------------------------
// Mocks — must be declared before imports that use them
// ---------------------------------------------------------------------------

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: {
          session: {
            user: {
              id: "test-expert-id",
              user_metadata: { role: "expert_reviewer" },
            },
            access_token: "fake-token",
          },
        },
        error: null,
      }),
    },
  },
}));

vi.mock("@/api/expert", () => ({
  getExpertQueue: vi.fn().mockResolvedValue([
    {
      analysis_id: "aaaaaaaa-1111-2222-3333-444444444444",
      exercise_type: "squat",
      exercise_variant: "high_bar",
      confidence_score: 0.85,
      form_score_overall: 7.5,
      flagged_for_review: false,
      created_at: "2026-04-20T10:00:00Z",
      annotation_count: 0,
    },
  ]),
}));

// Import after mocks
import ExpertPortalPage from "@/pages/ExpertPortalPage";
import { supabase } from "@/lib/supabase";
import { getExpertQueue } from "@/api/expert";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderExpertPortalPage() {
  return render(
    <MemoryRouter initialEntries={["/expert"]}>
      <Routes>
        <Route path="/expert" element={<ExpertPortalPage />} />
        <Route path="/expert/analyses/:id" element={<div>Analysis Detail</div>} />
        <Route path="/expert/papers/upload" element={<div>Upload Paper</div>} />
        <Route path="/" element={<div>Home</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ExpertPortalPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default: authorized expert_reviewer
    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: {
        session: {
          user: {
            id: "test-expert-id",
            user_metadata: { role: "expert_reviewer" },
          },
          access_token: "fake-token",
        },
      },
      error: null,
    } as any);  // eslint-disable-line @typescript-eslint/no-explicit-any

    // Default queue response
    vi.mocked(getExpertQueue).mockResolvedValue([
      {
        analysis_id: "aaaaaaaa-1111-2222-3333-444444444444",
        exercise_type: "squat",
        exercise_variant: "high_bar",
        confidence_score: 0.85,
        form_score_overall: 7.5,
        flagged_for_review: false,
        created_at: "2026-04-20T10:00:00Z",
        annotation_count: 0,
      },
    ]);
  });

  it("renders queue heading for authorized expert reviewer", async () => {
    renderExpertPortalPage();

    await waitFor(() => {
      expect(screen.getByText("Expert Reviewer Portal")).toBeInTheDocument();
    });
  });

  it("displays queue item exercise type after loading", async () => {
    renderExpertPortalPage();

    await waitFor(() => {
      // exercise_type "squat" is displayed capitalized in the table
      expect(screen.getByText("squat")).toBeInTheDocument();
    });
  });

  it("shows confidence as categorical label, never decimal (NFR-USAB-03)", async () => {
    renderExpertPortalPage();

    await waitFor(() => {
      // confidence_score 0.85 → "High" (≥0.80 threshold)
      expect(screen.getByText("High")).toBeInTheDocument();
    });

    // Verify that the raw decimal "0.85" is not rendered anywhere in the document
    expect(screen.queryByText("0.85")).not.toBeInTheDocument();
  });

  it("has a Review link pointing to the detail page for each queue item", async () => {
    renderExpertPortalPage();

    await waitFor(() => {
      const reviewLink = screen.getByRole("link", { name: /review/i });
      expect(reviewLink).toBeInTheDocument();
      expect(reviewLink).toHaveAttribute(
        "href",
        "/expert/analyses/aaaaaaaa-1111-2222-3333-444444444444",
      );
    });
  });

  it("shows access denied and redirects non-expert users", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: {
        session: {
          user: {
            id: "regular-user-id",
            user_metadata: { role: "user" },
          },
          access_token: "fake-token",
        },
      },
      error: null,
    } as any);  // eslint-disable-line @typescript-eslint/no-explicit-any

    renderExpertPortalPage();

    await waitFor(() => {
      expect(screen.getByText("Access Denied")).toBeInTheDocument();
    });
  });
});
