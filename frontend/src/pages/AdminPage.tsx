/**
 * AdminPage — admin dashboard with user management, analysis log, and system health.
 *
 * Requirements: FR-ADMN-01 through FR-ADMN-05
 *
 * - FR-ADMN-01: User management table with delete / disable actions.
 * - FR-ADMN-02: Analysis log table with status filter and pagination.
 * - FR-ADMN-03: ARQ queue depth display.
 * - FR-ADMN-04: Worker heartbeat status indicator.
 * - FR-ADMN-05: Database connectivity status.
 *
 * Admin role check: reads `app_metadata.role` from the Supabase JWT.
 * Non-admins see an access-denied message and are redirected to home.
 */

import { useState, useEffect, useCallback } from "react";
import { Navigate } from "react-router";
import { supabase } from "@/lib/supabase";
import {
  listAdminUsers,
  deleteAdminUser,
  disableAdminUser,
  listAdminAnalyses,
  getAdminHealth,
  type AdminUser,
  type AdminAnalysis,
  type AdminHealth,
} from "@/api/admin";

const ANALYSIS_STATUSES = [
  "queued",
  "quality_gate_pending",
  "quality_gate_passed",
  "quality_gate_rejected",
  "processing",
  "completed",
  "failed",
];

const PAGE_SIZE = 50;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function shortId(id: string): string {
  return id.slice(0, 8) + "…";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface DeleteDialogProps {
  userId: string;
  onConfirm: () => void;
  onCancel: () => void;
}

function DeleteDialog({ userId, onConfirm, onCancel }: DeleteDialogProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Confirm user deletion"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    >
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-lg">
        <h2 className="mb-2 text-lg font-semibold text-gray-900">Delete user?</h2>
        <p className="mb-6 text-sm text-gray-600">
          This will permanently delete all data for user{" "}
          <span className="font-mono text-xs">{shortId(userId)}</span>. This action cannot be
          undone.
        </p>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panels
// ---------------------------------------------------------------------------

function UserManagementPanel() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [disableMessage, setDisableMessage] = useState<string | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAdminUsers(PAGE_SIZE, offset);
      setUsers(data);
    } catch (err) {
      console.error("Failed to load users", err);
      setError("Failed to load users. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [offset]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  async function handleDeleteConfirm() {
    if (!pendingDelete) return;
    try {
      await deleteAdminUser(pendingDelete);
      setUsers((prev) => prev.filter((u) => u.user_id !== pendingDelete));
    } catch (err) {
      console.error("Failed to delete user", err);
      setDeleteError("Failed to delete user. Please try again.");
    } finally {
      setPendingDelete(null);
    }
  }

  async function handleDisable(userId: string) {
    try {
      const result = await disableAdminUser(userId);
      setDisableMessage(result.message);
    } catch (err) {
      console.error("Failed to disable user", err);
      setDisableMessage("Failed to disable user. Please try again.");
    }
  }

  return (
    <section aria-labelledby="user-management-heading" className="rounded-lg bg-white p-6 shadow-sm">
      <h2 id="user-management-heading" className="mb-4 text-lg font-semibold text-gray-900">
        User Management
      </h2>

      {disableMessage && (
        <div
          role="status"
          className="mb-4 rounded-md bg-blue-50 px-4 py-3 text-sm text-blue-700"
        >
          {disableMessage}
          <button
            type="button"
            onClick={() => setDisableMessage(null)}
            className="ml-2 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {deleteError && (
        <div className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          {deleteError}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">Loading users...</p>
      ) : error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  <th className="pb-3 pr-4">User ID</th>
                  <th className="pb-3 pr-4">Height</th>
                  <th className="pb-3 pr-4">Weight</th>
                  <th className="pb-3 pr-4">Age</th>
                  <th className="pb-3 pr-4">Experience</th>
                  <th className="pb-3 pr-4">Analyses</th>
                  <th className="pb-3 pr-4">Joined</th>
                  <th className="pb-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr
                    key={user.user_id}
                    className="border-b border-gray-100 last:border-0"
                  >
                    <td className="py-3 pr-4 font-mono text-xs text-gray-600">
                      {shortId(user.user_id)}
                    </td>
                    <td className="py-3 pr-4 text-gray-700">
                      {user.height_cm != null ? `${user.height_cm} cm` : "—"}
                    </td>
                    <td className="py-3 pr-4 text-gray-700">
                      {user.weight_kg != null ? `${user.weight_kg} kg` : "—"}
                    </td>
                    <td className="py-3 pr-4 text-gray-700">
                      {user.age ?? "—"}
                    </td>
                    <td className="py-3 pr-4 capitalize text-gray-700">
                      {user.experience_level ?? "—"}
                    </td>
                    <td className="py-3 pr-4 text-gray-700">{user.analysis_count}</td>
                    <td className="py-3 pr-4 text-gray-700">{formatDate(user.created_at)}</td>
                    <td className="py-3">
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setPendingDelete(user.user_id)}
                          className="rounded bg-red-50 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
                          aria-label={`Delete user ${shortId(user.user_id)}`}
                        >
                          Delete
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDisable(user.user_id)}
                          className="rounded bg-gray-50 px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100"
                          aria-label={`Disable user ${shortId(user.user_id)}`}
                        >
                          Disable
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-6 text-center text-sm text-gray-400">
                      No users found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={offset === 0}
              className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-600 disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-xs text-gray-400">
              Showing {offset + 1}–{offset + users.length}
            </span>
            <button
              type="button"
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={users.length < PAGE_SIZE}
              className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-600 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </>
      )}

      {pendingDelete && (
        <DeleteDialog
          userId={pendingDelete}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </section>
  );
}

function AnalysisLogPanel() {
  const [analyses, setAnalyses] = useState<AdminAnalysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");

  const fetchAnalyses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAdminAnalyses(PAGE_SIZE, offset, statusFilter || undefined);
      setAnalyses(data);
    } catch (err) {
      console.error("Failed to load analyses", err);
      setError("Failed to load analyses. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [offset, statusFilter]);

  useEffect(() => {
    fetchAnalyses();
  }, [fetchAnalyses]);

  function handleStatusChange(value: string) {
    setStatusFilter(value);
    setOffset(0);
  }

  return (
    <section aria-labelledby="analysis-log-heading" className="rounded-lg bg-white p-6 shadow-sm">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 id="analysis-log-heading" className="text-lg font-semibold text-gray-900">
          Analysis Log
        </h2>
        <div className="flex items-center gap-2">
          <label htmlFor="status-filter" className="text-sm text-gray-600">
            Filter by status:
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1 text-sm text-gray-700"
          >
            <option value="">All</option>
            {ANALYSIS_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-gray-500">Loading analyses...</p>
      ) : error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  <th className="pb-3 pr-4">ID</th>
                  <th className="pb-3 pr-4">User ID</th>
                  <th className="pb-3 pr-4">Status</th>
                  <th className="pb-3 pr-4">Exercise</th>
                  <th className="pb-3 pr-4">Variant</th>
                  <th className="pb-3 pr-4">Confidence</th>
                  <th className="pb-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {analyses.map((analysis) => (
                  <tr
                    key={analysis.id}
                    className="border-b border-gray-100 last:border-0"
                  >
                    <td className="py-3 pr-4 font-mono text-xs text-gray-600">
                      {shortId(analysis.id)}
                    </td>
                    <td className="py-3 pr-4 font-mono text-xs text-gray-600">
                      {shortId(analysis.user_id)}
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                          analysis.status === "completed"
                            ? "bg-green-100 text-green-700"
                            : analysis.status === "failed" ||
                                analysis.status === "quality_gate_rejected"
                              ? "bg-red-100 text-red-700"
                              : analysis.status === "processing"
                                ? "bg-blue-100 text-blue-700"
                                : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {analysis.status}
                      </span>
                    </td>
                    <td className="py-3 pr-4 capitalize text-gray-700">
                      {analysis.exercise_type}
                    </td>
                    <td className="py-3 pr-4 capitalize text-gray-700">
                      {analysis.exercise_variant}
                    </td>
                    <td className="py-3 pr-4 text-gray-700">
                      {analysis.confidence_score != null
                        ? analysis.confidence_score.toFixed(2)
                        : "—"}
                    </td>
                    <td className="py-3 text-gray-700">{formatDate(analysis.created_at)}</td>
                  </tr>
                ))}
                {analyses.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-sm text-gray-400">
                      No analyses found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={offset === 0}
              className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-600 disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-xs text-gray-400">
              Showing {offset + 1}–{offset + analyses.length}
            </span>
            <button
              type="button"
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={analyses.length < PAGE_SIZE}
              className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-600 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function SystemHealthPanel() {
  const [health, setHealth] = useState<AdminHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAdminHealth()
      .then(setHealth)
      .catch((err) => {
        console.error("Failed to load health", err);
        setError("Failed to load system health. Please try again.");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <section
      aria-labelledby="system-health-heading"
      className="rounded-lg bg-white p-6 shadow-sm"
    >
      <h2 id="system-health-heading" className="mb-4 text-lg font-semibold text-gray-900">
        System Health
      </h2>

      {loading ? (
        <p className="text-sm text-gray-500">Loading health status...</p>
      ) : error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : health ? (
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-md bg-gray-50 p-4">
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
              ARQ Queue Depth
            </dt>
            <dd className="mt-1 text-2xl font-bold text-gray-900">{health.queue_depth}</dd>
          </div>

          <div className="rounded-md bg-gray-50 p-4">
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Worker Heartbeat
            </dt>
            <dd className="mt-1 flex items-center gap-2">
              <span
                aria-label={health.worker_heartbeat ? "Online" : "Offline"}
                className={`inline-block h-3 w-3 rounded-full ${
                  health.worker_heartbeat ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <span className="text-sm font-medium text-gray-700">
                {health.worker_heartbeat ? "Online" : "Offline"}
              </span>
            </dd>
          </div>

          <div className="rounded-md bg-gray-50 p-4">
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Database
            </dt>
            <dd className="mt-1 flex items-center gap-2">
              <span
                aria-label={health.db_ok ? "Connected" : "Disconnected"}
                className={`inline-block h-3 w-3 rounded-full ${
                  health.db_ok ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <span className="text-sm font-medium text-gray-700">
                {health.db_ok ? "Connected" : "Disconnected"}
              </span>
            </dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function AdminPage() {
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const session = data.session;
      if (!session) {
        setIsAdmin(false);
        return;
      }
      // Admin role is stored in app_metadata.role on the JWT payload
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const payload = session.user as any;
      const role =
        payload?.app_metadata?.role ?? payload?.user_metadata?.role ?? null;
      setIsAdmin(role === "admin");
    });
  }, []);

  if (isAdmin === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-500">Checking permissions...</p>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <h1 className="mb-2 text-2xl font-bold text-gray-900">Access Denied</h1>
          <p className="mb-4 text-sm text-gray-500">
            You do not have permission to view this page.
          </p>
          <Navigate to="/" replace />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-10">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <h1 className="mb-8 text-3xl font-bold text-gray-900">Admin Dashboard</h1>

        <div className="space-y-8">
          <SystemHealthPanel />
          <UserManagementPanel />
          <AnalysisLogPanel />
        </div>
      </div>
    </div>
  );
}
