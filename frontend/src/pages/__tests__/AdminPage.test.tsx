import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import AdminPage from "@/pages/AdminPage";
import type { AdminUser, AdminAnalysis, AdminHealth } from "@/api/admin";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/api/admin", () => ({
  listAdminUsers: vi.fn(),
  deleteAdminUser: vi.fn(),
  disableAdminUser: vi.fn(),
  listAdminAnalyses: vi.fn(),
  getAdminHealth: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
    },
  },
}));

import {
  listAdminUsers,
  deleteAdminUser,
  disableAdminUser,
  listAdminAnalyses,
  getAdminHealth,
} from "@/api/admin";
import { supabase } from "@/lib/supabase";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_ADMIN_SESSION = {
  data: {
    session: {
      access_token: "test-token",
      user: {
        id: "admin-user-id",
        app_metadata: { role: "admin" },
        user_metadata: {},
      },
    },
  },
};

const MOCK_NON_ADMIN_SESSION = {
  data: {
    session: {
      access_token: "test-token",
      user: {
        id: "regular-user-id",
        app_metadata: { role: "user" },
        user_metadata: {},
      },
    },
  },
};

const MOCK_USERS: AdminUser[] = [
  {
    user_id: "aaaaaaaa-0000-0000-0000-000000000001",
    height_cm: 178,
    weight_kg: 80,
    age: 28,
    experience_level: "intermediate",
    analysis_count: 5,
    created_at: "2024-01-15T10:00:00Z",
    updated_at: "2024-01-15T10:00:00Z",
  },
  {
    user_id: "bbbbbbbb-0000-0000-0000-000000000002",
    height_cm: null,
    weight_kg: null,
    age: null,
    experience_level: null,
    analysis_count: 0,
    created_at: "2024-02-01T08:00:00Z",
    updated_at: "2024-02-01T08:00:00Z",
  },
];

const MOCK_ANALYSES: AdminAnalysis[] = [
  {
    id: "cccccccc-0000-0000-0000-000000000003",
    user_id: "aaaaaaaa-0000-0000-0000-000000000001",
    status: "completed",
    exercise_type: "squat",
    exercise_variant: "high-bar",
    confidence_score: 0.87,
    created_at: "2024-03-01T12:00:00Z",
    updated_at: "2024-03-01T12:05:00Z",
  },
  {
    id: "dddddddd-0000-0000-0000-000000000004",
    user_id: "bbbbbbbb-0000-0000-0000-000000000002",
    status: "failed",
    exercise_type: "deadlift",
    exercise_variant: "conventional",
    confidence_score: null,
    created_at: "2024-03-02T09:00:00Z",
    updated_at: "2024-03-02T09:01:00Z",
  },
];

const MOCK_HEALTH: AdminHealth = {
  queue_depth: 3,
  worker_heartbeat: true,
  db_ok: true,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminPage />
    </MemoryRouter>,
  );
}

function setupAdminMocks() {
  vi.mocked(supabase.auth.getSession).mockResolvedValue(MOCK_ADMIN_SESSION as never);
  vi.mocked(listAdminUsers).mockResolvedValue(MOCK_USERS);
  vi.mocked(listAdminAnalyses).mockResolvedValue(MOCK_ANALYSES);
  vi.mocked(getAdminHealth).mockResolvedValue(MOCK_HEALTH);
  vi.mocked(deleteAdminUser).mockResolvedValue(undefined);
  vi.mocked(disableAdminUser).mockResolvedValue({
    message: "User aaaaaaaa-0000-0000-0000-000000000001 disable is a Phase 1 feature (Supabase Admin API).",
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AdminPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // 4. Admin role gate — non-admin sees access denied
  it("shows access denied for non-admin users", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValue(
      MOCK_NON_ADMIN_SESSION as never,
    );
    vi.mocked(listAdminUsers).mockResolvedValue([]);
    vi.mocked(listAdminAnalyses).mockResolvedValue([]);
    vi.mocked(getAdminHealth).mockResolvedValue(MOCK_HEALTH);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/access denied/i)).toBeInTheDocument();
    });
  });

  it("shows access denied when user has no session", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: { session: null },
    } as never);
    vi.mocked(listAdminUsers).mockResolvedValue([]);
    vi.mocked(listAdminAnalyses).mockResolvedValue([]);
    vi.mocked(getAdminHealth).mockResolvedValue(MOCK_HEALTH);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/access denied/i)).toBeInTheDocument();
    });
  });

  // 1. User list table renders with mock data
  it("renders user list table with user data", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      // Check heading
      expect(screen.getByText("User Management")).toBeInTheDocument();
    });

    // Check user data appears (using truncated IDs)
    await waitFor(() => {
      expect(screen.getByText("178 cm")).toBeInTheDocument();
      expect(screen.getByText("80 kg")).toBeInTheDocument();
      expect(screen.getByText("28")).toBeInTheDocument();
      expect(screen.getByText("intermediate")).toBeInTheDocument();
      expect(screen.getByText("5")).toBeInTheDocument();
    });
  });

  it("renders null profile values as em-dash in user table", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      // Second user has all nulls — should show em-dash placeholders
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThan(0);
    });
  });

  // 2. Analysis log table renders with mock data
  it("renders analysis log table with analysis data", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Analysis Log")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("squat")).toBeInTheDocument();
      expect(screen.getByText("high-bar")).toBeInTheDocument();
      expect(screen.getByText("deadlift")).toBeInTheDocument();
      expect(screen.getByText("conventional")).toBeInTheDocument();
      // Status badges — use getAllByText because the status filter dropdown
      // also contains these strings as <option> values
      const completedEls = screen.getAllByText("completed");
      expect(completedEls.length).toBeGreaterThanOrEqual(2); // option + badge
      const failedEls = screen.getAllByText("failed");
      expect(failedEls.length).toBeGreaterThanOrEqual(2);
    });
  });

  // 3. System health panel shows queue depth, heartbeat status, db status
  it("renders system health panel with queue depth", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("System Health")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("ARQ Queue Depth")).toBeInTheDocument();
      expect(screen.getByText("3")).toBeInTheDocument();
    });
  });

  it("renders system health panel with worker heartbeat status (green = online)", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      // There should be two "Online" labels — one for heartbeat, one for db
      const onlineLabels = screen.getAllByText("Online");
      expect(onlineLabels.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders system health panel with db connectivity status", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Database")).toBeInTheDocument();
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
  });

  it("shows offline status when worker heartbeat is false", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValue(MOCK_ADMIN_SESSION as never);
    vi.mocked(listAdminUsers).mockResolvedValue([]);
    vi.mocked(listAdminAnalyses).mockResolvedValue([]);
    vi.mocked(getAdminHealth).mockResolvedValue({
      queue_depth: 0,
      worker_heartbeat: false,
      db_ok: false,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Offline")).toBeInTheDocument();
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
  });

  // 5. Delete user confirmation dialog
  it("shows delete confirmation dialog when delete button is clicked", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("178 cm")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByRole("button", { name: /delete user/i });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(screen.getByRole("dialog", { name: /confirm user deletion/i })).toBeInTheDocument();
      expect(screen.getByText(/delete user\?/i)).toBeInTheDocument();
    });
  });

  it("dismisses delete dialog on cancel", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("178 cm")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByRole("button", { name: /delete user/i });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("calls deleteAdminUser and removes user from list on confirm", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("178 cm")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByRole("button", { name: /delete user/i });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /^delete$/i }));

    await waitFor(() => {
      expect(deleteAdminUser).toHaveBeenCalledWith(MOCK_USERS[0].user_id);
      // User should be removed from list
      expect(screen.queryByText("178 cm")).not.toBeInTheDocument();
    });
  });

  // 6. Status filter on analysis log
  it("filters analysis log by status", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/filter by status/i)).toBeInTheDocument();
    });

    const statusSelect = screen.getByLabelText(/filter by status/i);
    fireEvent.change(statusSelect, { target: { value: "completed" } });

    await waitFor(() => {
      expect(listAdminAnalyses).toHaveBeenCalledWith(50, 0, "completed");
    });
  });

  it("resets to first page when status filter changes", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/filter by status/i)).toBeInTheDocument();
    });

    const statusSelect = screen.getByLabelText(/filter by status/i);
    fireEvent.change(statusSelect, { target: { value: "failed" } });

    await waitFor(() => {
      expect(listAdminAnalyses).toHaveBeenCalledWith(50, 0, "failed");
    });
  });

  // 7. Loading and error states
  it("shows loading state while fetching users", () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValue(MOCK_ADMIN_SESSION as never);
    // Return a promise that never resolves (simulating loading)
    vi.mocked(listAdminUsers).mockReturnValue(new Promise(() => {}));
    vi.mocked(listAdminAnalyses).mockResolvedValue([]);
    vi.mocked(getAdminHealth).mockResolvedValue(MOCK_HEALTH);

    renderPage();

    // Initially shows "Checking permissions..."
    expect(screen.getByText(/checking permissions/i)).toBeInTheDocument();
  });

  it("shows loading state for users panel after auth resolves", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValue(MOCK_ADMIN_SESSION as never);
    vi.mocked(listAdminUsers).mockReturnValue(new Promise(() => {}));
    vi.mocked(listAdminAnalyses).mockResolvedValue([]);
    vi.mocked(getAdminHealth).mockResolvedValue(MOCK_HEALTH);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/loading users/i)).toBeInTheDocument();
    });
  });

  it("shows error state when user fetch fails", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValue(MOCK_ADMIN_SESSION as never);
    vi.mocked(listAdminUsers).mockRejectedValue({ status: 500, message: "Server error" });
    vi.mocked(listAdminAnalyses).mockResolvedValue([]);
    vi.mocked(getAdminHealth).mockResolvedValue(MOCK_HEALTH);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/failed to load users/i)).toBeInTheDocument();
    });
  });

  it("shows error state when analysis fetch fails", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValue(MOCK_ADMIN_SESSION as never);
    vi.mocked(listAdminUsers).mockResolvedValue([]);
    vi.mocked(listAdminAnalyses).mockRejectedValue({ status: 500 });
    vi.mocked(getAdminHealth).mockResolvedValue(MOCK_HEALTH);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/failed to load analyses/i)).toBeInTheDocument();
    });
  });

  it("shows error state when health fetch fails", async () => {
    vi.mocked(supabase.auth.getSession).mockResolvedValue(MOCK_ADMIN_SESSION as never);
    vi.mocked(listAdminUsers).mockResolvedValue([]);
    vi.mocked(listAdminAnalyses).mockResolvedValue([]);
    vi.mocked(getAdminHealth).mockRejectedValue({ status: 503 });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/failed to load system health/i)).toBeInTheDocument();
    });
  });

  // Disable user — Phase 1 stub
  it("shows Phase 1 feature message when disable is clicked", async () => {
    setupAdminMocks();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("178 cm")).toBeInTheDocument();
    });

    const disableButtons = screen.getAllByRole("button", { name: /disable user/i });
    fireEvent.click(disableButtons[0]);

    await waitFor(() => {
      expect(disableAdminUser).toHaveBeenCalledWith(MOCK_USERS[0].user_id);
    });

    await waitFor(() => {
      expect(screen.getByText(/phase 1 feature/i)).toBeInTheDocument();
    });
  });
});
