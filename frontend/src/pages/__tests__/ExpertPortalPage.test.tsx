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
import { render, screen, waitFor, fireEvent, within, act } from "@testing-library/react";
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
  listExpertPapers: vi.fn().mockResolvedValue([]),
  reviewPaper: vi.fn(),
  updatePaperMetadata: vi.fn(),
  // Mirror the real guard's name + status duck-type (issue #235) so the page's
  // approve catch can distinguish a real ExpertApiError throw from a legacy
  // object literal.
  isExpertApiError: (e: unknown): boolean =>
    typeof e === "object" &&
    e !== null &&
    (e as { name?: unknown }).name === "ExpertApiError" &&
    typeof (e as { status?: unknown }).status === "number",
  // Real const re-declared here: vi.mock replaces the whole module, and the
  // page imports these options alongside the mocked API functions.
  SEX_APPLICABILITY_OPTIONS: [
    { value: "male", label: "Male" },
    { value: "female", label: "Female" },
    { value: "both", label: "Both" },
  ],
}));

// Import after mocks
import ExpertPortalPage from "@/pages/ExpertPortalPage";
import { supabase } from "@/lib/supabase";
import {
  getExpertQueue,
  listExpertPapers,
  reviewPaper,
  updatePaperMetadata,
  type RagDocumentResponse,
} from "@/api/expert";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Full RagDocumentResponse fixture for the My Papers tab (FR-EXPV-02). */
function makePaper(overrides: Partial<RagDocumentResponse> = {}): RagDocumentResponse {
  return {
    id: "bbbbbbbb-1111-2222-3333-444444444444",
    title: "Squat Depth Study",
    source_url: null,
    document_type: "research_paper",
    exercise_tags: ["squat"],
    chunk_count: 4,
    authors: ["Smith J"],
    year: 2023,
    doi: null,
    study_design: "rct",
    quality_tier: "L2",
    quality_score: null,
    review_status: "pending",
    reviewer_id: null,
    reviewed_at: null,
    sex_applicability: "both",
    created_at: "2026-04-20T10:00:00Z",
    updated_at: "2026-04-20T10:00:00Z",
    ...overrides,
  };
}

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

    // Default papers response
    vi.mocked(listExpertPapers).mockResolvedValue([]);
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

  // --- My Papers tab — DOI column (FR-EXPV-02, FR-RAGK-08) ---

  it("renders a DOI column linking to doi.org", async () => {
    vi.mocked(listExpertPapers).mockResolvedValue([
      makePaper({ doi: "10.1234/squat" }),
    ]);

    renderExpertPortalPage();
    await waitFor(() => {
      expect(screen.getByText("Expert Reviewer Portal")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "My Papers" }));

    await waitFor(() => {
      expect(screen.getByText("Squat Depth Study")).toBeInTheDocument();
    });

    expect(screen.getByText("DOI")).toBeInTheDocument();
    const doiLink = screen.getByRole("link", { name: "10.1234/squat" });
    expect(doiLink).toHaveAttribute("href", "https://doi.org/10.1234/squat");
  });

  it("renders an em dash for papers without a DOI", async () => {
    vi.mocked(listExpertPapers).mockResolvedValue([makePaper({ doi: null })]);

    renderExpertPortalPage();
    await waitFor(() => {
      expect(screen.getByText("Expert Reviewer Portal")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "My Papers" }));

    await waitFor(() => {
      expect(screen.getByText("Squat Depth Study")).toBeInTheDocument();
    });

    const row = screen.getByText("Squat Depth Study").closest("tr");
    expect(row).not.toBeNull();
    expect(
      within(row as HTMLTableRowElement).getByTestId("doi-empty"),
    ).toHaveTextContent("—");
  });

  // --- My Papers tab — Applicable population (issue #223, FR-RAGK-05 ext.) ---

  async function openMyPapersTab() {
    renderExpertPortalPage();
    await waitFor(() => {
      expect(screen.getByText("Expert Reviewer Portal")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "My Papers" }));
    await waitFor(() => {
      expect(screen.getByText("Squat Depth Study")).toBeInTheDocument();
    });
  }

  it("renders an Applicable population column with the current value selected", async () => {
    vi.mocked(listExpertPapers).mockResolvedValue([
      makePaper({ sex_applicability: "female" }),
    ]);

    await openMyPapersTab();

    expect(screen.getByText("Applicable population")).toBeInTheDocument();
    const select = screen.getByLabelText(
      /applicable population for squat depth study/i,
    ) as HTMLSelectElement;
    expect(select.value).toBe("female");
    const options = Array.from(select.options).map((o) => o.textContent);
    expect(options).toEqual(["Male", "Female", "Both"]);
  });

  it("PATCHes paper metadata when the Applicable population select changes", async () => {
    vi.mocked(listExpertPapers).mockResolvedValue([makePaper()]);
    vi.mocked(updatePaperMetadata).mockResolvedValue({
      id: "bbbbbbbb-1111-2222-3333-444444444444",
      sex_applicability: "female",
    });

    await openMyPapersTab();

    const select = screen.getByLabelText(
      /applicable population for squat depth study/i,
    ) as HTMLSelectElement;
    expect(select.value).toBe("both");

    fireEvent.change(select, { target: { value: "female" } });

    await waitFor(() =>
      expect(updatePaperMetadata).toHaveBeenCalledWith(
        "bbbbbbbb-1111-2222-3333-444444444444",
        { sex_applicability: "female" },
      ),
    );
    await waitFor(() => expect(select.value).toBe("female"));
  });

  it("disables the select while the metadata PATCH is in flight", async () => {
    vi.mocked(listExpertPapers).mockResolvedValue([makePaper()]);
    let resolvePatch!: (v: { id: string; sex_applicability: string }) => void;
    vi.mocked(updatePaperMetadata).mockImplementation(
      () =>
        new Promise((res) => {
          resolvePatch = res;
        }),
    );

    await openMyPapersTab();

    const select = screen.getByLabelText(
      /applicable population for squat depth study/i,
    ) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "female" } });

    // Busy while the PATCH promise is unresolved (mirrors the approving pattern)
    await waitFor(() => expect(select).toBeDisabled());

    await act(async () => {
      resolvePatch({
        id: "bbbbbbbb-1111-2222-3333-444444444444",
        sex_applicability: "female",
      });
    });

    await waitFor(() => expect(select).not.toBeDisabled());
    expect(select.value).toBe("female");
  });

  // --- Paper review 409 DUPLICATE_DOI (issue #260, FR-EXPV-06) ---

  it("surfaces the DUPLICATE_DOI message when paper approval returns 409 (legacy throw shape)", async () => {
    // Back-compat: a hand-rolled `{ status, error: {...} }` rejection still
    // works via the catch's `legacy` fallback path.
    vi.mocked(listExpertPapers).mockResolvedValue([makePaper()]);
    vi.mocked(reviewPaper).mockRejectedValue({
      status: 409,
      error: {
        code: "DUPLICATE_DOI",
        message: "A paper with this DOI already exists.",
      },
    });

    await openMyPapersTab();

    fireEvent.click(screen.getByRole("button", { name: "Approve & Ingest" }));

    await waitFor(() =>
      expect(
        screen.getByText("A paper with this DOI already exists."),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByText(/failed to approve paper/i),
    ).not.toBeInTheDocument();
  });

  it("surfaces the DUPLICATE_DOI message when approval throws a typed ExpertApiError", async () => {
    // Issue #235: reviewPaper -> expertFetch now throws a real ExpertApiError
    // that exposes code/message at the TOP level (no `.error` nesting). This
    // pins the page's catch to the actual transport shape — it would fail
    // against the pre-#235 `apiErr.error?.code` read (regression guard for the
    // shared-throw-shape migration that left this consumer behind).
    const apiErr = Object.assign(
      new Error("A paper with this DOI already exists."),
      { name: "ExpertApiError", status: 409, code: "DUPLICATE_DOI" },
    );
    vi.mocked(listExpertPapers).mockResolvedValue([makePaper()]);
    vi.mocked(reviewPaper).mockRejectedValue(apiErr);

    await openMyPapersTab();

    fireEvent.click(screen.getByRole("button", { name: "Approve & Ingest" }));

    await waitFor(() =>
      expect(
        screen.getByText("A paper with this DOI already exists."),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByText(/failed to approve paper/i),
    ).not.toBeInTheDocument();
  });

  it("shows an error and keeps the old value when the metadata PATCH fails", async () => {
    vi.mocked(listExpertPapers).mockResolvedValue([makePaper()]);
    vi.mocked(updatePaperMetadata).mockRejectedValue({
      status: 500,
      error: { code: "INTERNAL", message: "boom" },
    });

    await openMyPapersTab();

    const select = screen.getByLabelText(
      /applicable population for squat depth study/i,
    ) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "male" } });

    await waitFor(() =>
      expect(
        screen.getByText(/failed to update applicable population/i),
      ).toBeInTheDocument(),
    );
    expect(select.value).toBe("both");
  });
});
