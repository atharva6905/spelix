import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import BetaTermsPage from "@/pages/BetaTermsPage";

const BETA_TERMS_MARKDOWN = `# Spelix Private Beta Terms

**Last updated: 2026-04-15**

## Beta status and purpose

Spelix is currently in a private beta.
`;

describe("BetaTermsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches /beta-terms.md and renders the h1 heading", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve(BETA_TERMS_MARKDOWN),
    } as unknown as Response);

    render(<BetaTermsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", {
          level: 1,
          name: /spelix private beta terms/i,
        }),
      ).toBeInTheDocument();
    });
  });

  it("shows 'Could not load beta terms' error on fetch failure", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("Network error"));

    render(<BetaTermsPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Could not load beta terms",
      );
    });
  });

  it("shows error when response is not ok (non-200 status)", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve("Not found"),
    } as unknown as Response);

    render(<BetaTermsPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Could not load beta terms",
      );
    });
  });

  it("shows loading state initially", () => {
    // Delay the fetch response indefinitely
    globalThis.fetch = vi.fn().mockReturnValue(new Promise(() => {}));

    render(<BetaTermsPage />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
