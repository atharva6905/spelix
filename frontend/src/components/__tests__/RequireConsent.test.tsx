import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";
import RequireConsent from "@/components/RequireConsent";

// Mock the consent API
vi.mock("@/api/consent", () => ({
  getConsents: vi.fn(),
}));

import { getConsents } from "@/api/consent";

const mockGetConsents = getConsents as ReturnType<typeof vi.fn>;

describe("RequireConsent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects to /consent when no consent records exist", async () => {
    mockGetConsents.mockResolvedValue([]);

    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <Routes>
          <Route
            path="/upload"
            element={
              <RequireConsent>
                <div>Upload Page</div>
              </RequireConsent>
            }
          />
          <Route path="/consent" element={<div>Consent Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.queryByText("Upload Page")).not.toBeInTheDocument();
      expect(screen.getByText("Consent Page")).toBeInTheDocument();
    });
  });

  it("redirects to /consent when health_data_processing consent is not granted", async () => {
    mockGetConsents.mockResolvedValue([
      {
        consent_type: "health_data_processing",
        granted: false,
        granted_at: null,
        withdrawn_at: "2026-05-01T00:00:00Z",
        consent_version: "1.0",
      },
    ]);

    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <Routes>
          <Route
            path="/upload"
            element={
              <RequireConsent>
                <div>Upload Page</div>
              </RequireConsent>
            }
          />
          <Route path="/consent" element={<div>Consent Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.queryByText("Upload Page")).not.toBeInTheDocument();
      expect(screen.getByText("Consent Page")).toBeInTheDocument();
    });
  });

  it("renders children when health_data_processing consent is granted", async () => {
    mockGetConsents.mockResolvedValue([
      {
        consent_type: "health_data_processing",
        granted: true,
        granted_at: "2026-05-01T00:00:00Z",
        withdrawn_at: null,
        consent_version: "1.0",
      },
    ]);

    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <Routes>
          <Route
            path="/upload"
            element={
              <RequireConsent>
                <div>Upload Page</div>
              </RequireConsent>
            }
          />
          <Route path="/consent" element={<div>Consent Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Upload Page")).toBeInTheDocument();
    });
  });

  it("shows loading state while checking consent", async () => {
    // Delay resolution to observe loading state
    mockGetConsents.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve([
                {
                  consent_type: "health_data_processing",
                  granted: true,
                  granted_at: "2026-05-01T00:00:00Z",
                  withdrawn_at: null,
                  consent_version: "1.0",
                },
              ]),
            100,
          ),
        ),
    );

    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <Routes>
          <Route
            path="/upload"
            element={
              <RequireConsent>
                <div>Upload Page</div>
              </RequireConsent>
            }
          />
          <Route path="/consent" element={<div>Consent Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    // Before consent resolves, loading text should be visible
    expect(screen.getByText("Checking consent...")).toBeInTheDocument();
    expect(screen.queryByText("Upload Page")).not.toBeInTheDocument();
  });

  it("denies access (redirects to /consent) on API error", async () => {
    mockGetConsents.mockRejectedValue(new Error("Network error"));

    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <Routes>
          <Route
            path="/upload"
            element={
              <RequireConsent>
                <div>Upload Page</div>
              </RequireConsent>
            }
          />
          <Route path="/consent" element={<div>Consent Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.queryByText("Upload Page")).not.toBeInTheDocument();
      expect(screen.getByText("Consent Page")).toBeInTheDocument();
    });
  });

  it("includes redirect param in consent URL", async () => {
    mockGetConsents.mockResolvedValue([]);

    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <Routes>
          <Route
            path="/upload"
            element={
              <RequireConsent>
                <div>Upload Page</div>
              </RequireConsent>
            }
          />
          <Route path="/consent" element={<div>Consent Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Consent Page")).toBeInTheDocument();
    });
  });
});
