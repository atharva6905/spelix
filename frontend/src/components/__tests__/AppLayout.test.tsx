import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router";

// Mock supabase before importing the component
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      signOut: vi.fn(),
    },
    channel: vi.fn().mockReturnValue({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn(),
      unsubscribe: vi.fn(),
    }),
    removeChannel: vi.fn(),
  },
}));

import { supabase } from "@/lib/supabase";
import AppLayout from "@/components/AppLayout";

const mockGetSession = supabase.auth.getSession as ReturnType<typeof vi.fn>;
const mockSignOut = supabase.auth.signOut as ReturnType<typeof vi.fn>;

function renderAppLayout(pathname = "/upload") {
  return render(
    <MemoryRouter initialEntries={[pathname]}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/upload" element={<div>Upload Page</div>} />
          <Route path="/history" element={<div>History Page</div>} />
          <Route path="/profile" element={<div>Profile Page</div>} />
          <Route path="/admin" element={<div>Admin Page</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("AppLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: non-admin session
    mockGetSession.mockResolvedValue({
      data: {
        session: {
          user: {
            id: "user-1",
            email: "user@example.com",
            app_metadata: { role: "user" },
          },
          access_token: "tok",
        },
      },
      error: null,
    });
  });

  it("renders the Spelix brand link", () => {
    renderAppLayout();
    expect(screen.getByRole("link", { name: /spelix/i })).toBeInTheDocument();
  });

  it("renders Upload nav link", () => {
    renderAppLayout();
    expect(screen.getByRole("link", { name: /upload/i })).toBeInTheDocument();
  });

  it("renders History nav link", () => {
    renderAppLayout();
    expect(screen.getByRole("link", { name: /history/i })).toBeInTheDocument();
  });

  it("renders Profile nav link", () => {
    renderAppLayout();
    expect(screen.getByRole("link", { name: /profile/i })).toBeInTheDocument();
  });

  it("renders Sign out button", () => {
    renderAppLayout();
    expect(
      screen.getByRole("button", { name: /sign out/i }),
    ).toBeInTheDocument();
  });

  it("renders children via Outlet", () => {
    renderAppLayout("/upload");
    expect(screen.getByText("Upload Page")).toBeInTheDocument();
  });

  it("does NOT render Admin link for non-admin user", async () => {
    renderAppLayout();
    // Wait for session check to complete
    await waitFor(() => {
      expect(screen.queryByRole("link", { name: /admin/i })).not.toBeInTheDocument();
    });
  });

  it("renders Admin link for admin user", async () => {
    mockGetSession.mockResolvedValue({
      data: {
        session: {
          user: {
            id: "admin-1",
            email: "admin@spelix.app",
            app_metadata: { role: "admin" },
          },
          access_token: "tok",
        },
      },
      error: null,
    });

    renderAppLayout();

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /admin/i })).toBeInTheDocument();
    });
  });

  it("applies active style to the current nav item", () => {
    renderAppLayout("/upload");
    const uploadLink = screen.getByRole("link", { name: /^upload$/i });
    expect(uploadLink.className).toContain("text-blue-700");
  });

  it("does not apply active style to non-current nav items", () => {
    renderAppLayout("/upload");
    const historyLink = screen.getByRole("link", { name: /^history$/i });
    expect(historyLink.className).not.toContain("text-blue-700");
  });

  it("calls supabase.auth.signOut when Sign out is clicked", async () => {
    const user = userEvent.setup({ delay: null });
    mockSignOut.mockResolvedValue({ error: null });

    // jsdom does not support window.location.href assignment — stub it
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "" },
      writable: true,
    });

    renderAppLayout();

    await user.click(screen.getByRole("button", { name: /sign out/i }));

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalledTimes(1);
    });

    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
    });
  });
});
