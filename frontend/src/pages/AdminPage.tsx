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
import { Link, Navigate } from "react-router";
import { supabase } from "@/lib/supabase";
import {
  listAdminUsers,
  deleteAdminUser,
  disableAdminUser,
  listAdminAnalyses,
  getAdminHealth,
  listRagDocuments,
  deleteRagDocument,
  reEmbedRagDocument,
  listExpertQueue,
  getExpertQueueStats,
  listCoachBrainEntries,
  updateCoachBrainEntry,
  deleteCoachBrainEntry,
  listBetaRequests,
  getBetaRequestStats,
  approveBetaRequest,
  rejectBetaRequest,
  type AdminUser,
  type AdminAnalysis,
  type AdminHealth,
  type RagDocument,
  type AdminExpertQueueItem,
  type AdminExpertQueueStats,
  type CoachBrainEntry,
  type AdminBetaRequest,
  type AdminBetaRequestStats,
} from "@/api/admin";

// Valid status values per SRS Section 5.2a (7 total — quality_gate_passed is NOT valid)
const ANALYSIS_STATUSES = [
  "queued",
  "quality_gate_pending",
  "quality_gate_rejected",
  "processing",
  "coaching",
  "completed",
  "failed",
] as const;

type AnalysisStatusValue = typeof ANALYSIS_STATUSES[number];

/**
 * User-facing labels per SRS Appendix B.
 * Raw status strings must never appear in user-visible UI.
 */
const STATUS_LABELS: Record<AnalysisStatusValue, string> = {
  queued: "Queued",
  quality_gate_pending: "Preparing to analyse\u2026",
  quality_gate_rejected: "Video could not be processed",
  processing: "Processing",
  coaching: "Generating coaching\u2026",
  completed: "Completed",
  failed: "Failed",
};

/**
 * Returns the user-facing label for a status value.
 * Unknown values are displayed as the raw string with a "?" warning indicator
 * so the UI never crashes on unexpected API values.
 */
function formatStatus(status: string): string {
  if (status in STATUS_LABELS) {
    return STATUS_LABELS[status as AnalysisStatusValue];
  }
  return `${status} ?`;
}

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
                              : analysis.status === "processing" ||
                                  analysis.status === "coaching"
                                ? "bg-blue-100 text-blue-700"
                                : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {formatStatus(analysis.status)}
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

// ---------------------------------------------------------------------------
// RAG Corpus Panel (P2-035, FR-ADMN-06)
// ---------------------------------------------------------------------------

const PAGE_SIZE_RAG = 50;

function RagCorpusPanel() {
  const [docs, setDocs] = useState<RagDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [reviewFilter, setReviewFilter] = useState("");
  const [exerciseFilter, setExerciseFilter] = useState("");

  const loadDocs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: Record<string, string> = {};
      if (reviewFilter) filters.review_status = reviewFilter;
      if (exerciseFilter) filters.exercise_tag = exerciseFilter;
      const data = await listRagDocuments(PAGE_SIZE_RAG, offset, filters);
      setDocs(data);
    } catch {
      setError("Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [offset, reviewFilter, exerciseFilter]);

  useEffect(() => { loadDocs(); }, [loadDocs]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this document and its Qdrant points?")) return;
    try {
      await deleteRagDocument(id);
      loadDocs();
    } catch {
      setError("Failed to delete document");
    }
  };

  const handleReEmbed = async (id: string) => {
    try {
      await reEmbedRagDocument(id);
      alert("Re-embed queued");
    } catch {
      setError("Failed to queue re-embed");
    }
  };

  const statusBadge = (s: string) => {
    const colors: Record<string, string> = {
      pending: "bg-yellow-100 text-yellow-800",
      needs_revision: "bg-orange-100 text-orange-800",
      reviewed_approved: "bg-green-100 text-green-800",
      reviewed_rejected: "bg-red-100 text-red-800",
    };
    return (
      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${colors[s] ?? "bg-gray-100 text-gray-800"}`}>
        {s.replace(/_/g, " ")}
      </span>
    );
  };

  return (
    <section className="rounded-lg bg-white p-6 shadow">
      <h2 className="mb-4 text-lg font-semibold text-gray-900">RAG Corpus Management</h2>

      <div className="mb-4 flex gap-3">
        <select
          value={reviewFilter}
          onChange={(e) => { setReviewFilter(e.target.value); setOffset(0); }}
          className="rounded border px-2 py-1 text-sm"
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="needs_revision">Needs Revision</option>
          <option value="reviewed_approved">Approved</option>
          <option value="reviewed_rejected">Rejected</option>
        </select>
        <select
          value={exerciseFilter}
          onChange={(e) => { setExerciseFilter(e.target.value); setOffset(0); }}
          className="rounded border px-2 py-1 text-sm"
        >
          <option value="">All exercises</option>
          <option value="squat">Squat</option>
          <option value="bench">Bench</option>
          <option value="deadlift">Deadlift</option>
        </select>
      </div>

      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs font-medium uppercase text-gray-500">
                <th className="px-3 py-2">Title</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Quality</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Chunks</th>
                <th className="px-3 py-2">Year</th>
                <th className="px-3 py-2">DOI</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id} className="border-b hover:bg-gray-50">
                  <td className="max-w-xs truncate px-3 py-2" title={d.title}>{d.title}</td>
                  <td className="px-3 py-2">{d.document_type.replace(/_/g, " ")}</td>
                  <td className="px-3 py-2">{d.quality_tier?.replace("_", " ") ?? "—"}</td>
                  <td className="px-3 py-2">{statusBadge(d.review_status)}</td>
                  <td className="px-3 py-2">{d.chunk_count}</td>
                  <td className="px-3 py-2">{d.year ?? "—"}</td>
                  <td className="px-3 py-2">
                    {d.doi ? (
                      <a
                        href={`https://doi.org/${d.doi}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-xs text-indigo-600 hover:underline"
                      >
                        {d.doi}
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex gap-2">
                      <button onClick={() => handleDelete(d.id)} className="text-xs text-red-600 hover:underline">Delete</button>
                      {d.review_status === "reviewed_approved" && (
                        <button onClick={() => handleReEmbed(d.id)} className="text-xs text-blue-600 hover:underline">Re-embed</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {docs.length === 0 && (
                <tr><td colSpan={8} className="px-3 py-4 text-center text-gray-400">No documents found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-3 flex justify-between">
        <button
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE_RAG))}
          className="rounded bg-gray-100 px-3 py-1 text-sm disabled:opacity-50"
        >Previous</button>
        <button
          disabled={docs.length < PAGE_SIZE_RAG}
          onClick={() => setOffset(offset + PAGE_SIZE_RAG)}
          className="rounded bg-gray-100 px-3 py-1 text-sm disabled:opacity-50"
        >Next</button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Expert Reviewer Queue Panel (P2-036, FR-ADMN-07)
// ---------------------------------------------------------------------------

function ExpertQueuePanel() {
  const [items, setItems] = useState<AdminExpertQueueItem[]>([]);
  const [stats, setStats] = useState<AdminExpertQueueStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, s] = await Promise.all([
        listExpertQueue(PAGE_SIZE_RAG, offset),
        getExpertQueueStats(),
      ]);
      setItems(data);
      setStats(s);
    } catch {
      setError("Failed to load expert queue");
    } finally {
      setLoading(false);
    }
  }, [offset]);

  useEffect(() => { load(); }, [load]);

  return (
    <section className="rounded-lg bg-white p-6 shadow">
      <h2 className="mb-4 text-lg font-semibold text-gray-900">Expert Reviewer Queue</h2>

      {stats && (
        <div className="mb-4 flex gap-6 text-sm">
          <span>Flagged: <strong>{stats.total_flagged}</strong></span>
          <span>Annotated: <strong>{stats.total_annotated}</strong></span>
          <span>Golden Dataset: <strong>{stats.golden_dataset_count}</strong></span>
        </div>
      )}

      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs font-medium uppercase text-gray-500">
                <th className="px-3 py-2">Analysis</th>
                <th className="px-3 py-2">Exercise</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Annotations</th>
                <th className="px-3 py-2">Created</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.analysis_id} className="border-b hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono text-xs">{item.analysis_id.slice(0, 8)}</td>
                  <td className="px-3 py-2">{item.exercise_type}{item.exercise_variant ? ` (${item.exercise_variant})` : ""}</td>
                  <td className="px-3 py-2">
                    {item.confidence_score != null
                      ? item.confidence_score >= 0.80 ? "High"
                        : item.confidence_score >= 0.65 ? "Moderate"
                        : item.confidence_score >= 0.50 ? "Low"
                        : "Very Low"
                      : "—"}
                  </td>
                  <td className="px-3 py-2">{item.annotation_count}</td>
                  <td className="px-3 py-2">{formatDate(item.created_at)}</td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={5} className="px-3 py-4 text-center text-gray-400">No flagged analyses</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-3 flex justify-between">
        <button
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE_RAG))}
          className="rounded bg-gray-100 px-3 py-1 text-sm disabled:opacity-50"
        >Previous</button>
        <button
          disabled={items.length < PAGE_SIZE_RAG}
          onClick={() => setOffset(offset + PAGE_SIZE_RAG)}
          className="rounded bg-gray-100 px-3 py-1 text-sm disabled:opacity-50"
        >Next</button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Coach Brain Panel (P2-037, FR-ADMN-10)
// ---------------------------------------------------------------------------

function CoachBrainPanel() {
  const [entries, setEntries] = useState<CoachBrainEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [exerciseFilter, setExerciseFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: Record<string, string> = {};
      if (exerciseFilter) filters.exercise = exerciseFilter;
      if (statusFilter) filters.status = statusFilter;
      if (typeFilter) filters.entry_type = typeFilter;
      const data = await listCoachBrainEntries(PAGE_SIZE_RAG, offset, filters);
      setEntries(data);
    } catch {
      setError("Failed to load Coach Brain entries");
    } finally {
      setLoading(false);
    }
  }, [offset, exerciseFilter, statusFilter, typeFilter]);

  useEffect(() => { load(); }, [load]);

  const handleStatusChange = async (id: string, newStatus: string) => {
    try {
      await updateCoachBrainEntry(id, { status: newStatus });
      load();
    } catch {
      setError("Failed to update status");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this Coach Brain entry?")) return;
    try {
      await deleteCoachBrainEntry(id);
      load();
    } catch {
      setError("Failed to delete entry");
    }
  };

  const statusBadge = (s: string) => {
    const colors: Record<string, string> = {
      seed: "bg-blue-100 text-blue-800",
      active: "bg-green-100 text-green-800",
      deprecated: "bg-gray-100 text-gray-800",
    };
    return (
      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${colors[s] ?? "bg-gray-100 text-gray-800"}`}>
        {s}
      </span>
    );
  };

  return (
    <section className="rounded-lg bg-white p-6 shadow">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Coach Brain Management</h2>
        <Link
          to="/admin/coach-brain/candidates"
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          Review candidates &rarr;
        </Link>
      </div>

      <div className="mb-4 flex gap-3">
        <select value={exerciseFilter} onChange={(e) => { setExerciseFilter(e.target.value); setOffset(0); }} className="rounded border px-2 py-1 text-sm">
          <option value="">All exercises</option>
          <option value="squat">Squat</option>
          <option value="bench">Bench</option>
          <option value="deadlift">Deadlift</option>
        </select>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setOffset(0); }} className="rounded border px-2 py-1 text-sm">
          <option value="">All statuses</option>
          <option value="seed">Seed</option>
          <option value="active">Active</option>
          <option value="deprecated">Deprecated</option>
        </select>
        <select value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setOffset(0); }} className="rounded border px-2 py-1 text-sm">
          <option value="">All types</option>
          <option value="cue">Cue</option>
          <option value="correction">Correction</option>
          <option value="principle">Principle</option>
          <option value="drill">Drill</option>
        </select>
      </div>

      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs font-medium uppercase text-gray-500">
                <th className="px-3 py-2">Content</th>
                <th className="px-3 py-2">Exercise</th>
                <th className="px-3 py-2">Phase</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Confirms</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-b hover:bg-gray-50">
                  <td className="max-w-xs truncate px-3 py-2" title={e.content}>{e.content.slice(0, 80)}{e.content.length > 80 ? "..." : ""}</td>
                  <td className="px-3 py-2">{e.exercise}</td>
                  <td className="px-3 py-2">{e.phase}</td>
                  <td className="px-3 py-2">{e.entry_type}</td>
                  <td className="px-3 py-2">{statusBadge(e.status)}</td>
                  <td className="px-3 py-2">{e.confirmation_count}</td>
                  <td className="px-3 py-2">
                    <div className="flex gap-2">
                      {e.status === "seed" && (
                        <button onClick={() => handleStatusChange(e.id, "active")} className="text-xs text-green-600 hover:underline">Approve</button>
                      )}
                      {e.status !== "deprecated" && (
                        <button onClick={() => handleStatusChange(e.id, "deprecated")} className="text-xs text-yellow-600 hover:underline">Deprecate</button>
                      )}
                      <button onClick={() => handleDelete(e.id)} className="text-xs text-red-600 hover:underline">Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr><td colSpan={7} className="px-3 py-4 text-center text-gray-400">No entries found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-3 flex justify-between">
        <button
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE_RAG))}
          className="rounded bg-gray-100 px-3 py-1 text-sm disabled:opacity-50"
        >Previous</button>
        <button
          disabled={entries.length < PAGE_SIZE_RAG}
          onClick={() => setOffset(offset + PAGE_SIZE_RAG)}
          className="rounded bg-gray-100 px-3 py-1 text-sm disabled:opacity-50"
        >Next</button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Beta Requests Panel (admin ops)
// ---------------------------------------------------------------------------

const PAGE_SIZE_BETA = 50;

function BetaRequestsPanel() {
  const [requests, setRequests] = useState<AdminBetaRequest[]>([]);
  const [stats, setStats] = useState<AdminBetaRequestStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, s] = await Promise.all([
        listBetaRequests(PAGE_SIZE_BETA, offset, statusFilter || undefined),
        getBetaRequestStats(),
      ]);
      setRequests(data);
      setStats(s);
    } catch {
      setError("Failed to load beta requests");
    } finally {
      setLoading(false);
    }
  }, [offset, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleApprove = async (id: string) => {
    try {
      await approveBetaRequest(id);
      load();
    } catch {
      setError("Failed to approve request");
    }
  };

  const handleReject = async (id: string) => {
    try {
      await rejectBetaRequest(id);
      load();
    } catch {
      setError("Failed to reject request");
    }
  };

  const statusBadge = (s: string) => {
    const colors: Record<string, string> = {
      pending: "bg-yellow-100 text-yellow-800",
      approved: "bg-green-100 text-green-800",
      rejected: "bg-red-100 text-red-800",
    };
    return (
      <span
        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${colors[s] ?? "bg-gray-100 text-gray-800"}`}
      >
        {s}
      </span>
    );
  };

  return (
    <section className="rounded-lg bg-white p-6 shadow" aria-labelledby="beta-requests-heading">
      <h2 id="beta-requests-heading" className="mb-4 text-lg font-semibold text-gray-900">
        Beta Requests
      </h2>

      {stats && (
        <div className="mb-4 flex gap-6 text-sm">
          <span>
            Pending: <strong>{stats.pending}</strong>
          </span>
          <span>
            Approved: <strong>{stats.approved}</strong>
          </span>
          <span>
            Rejected: <strong>{stats.rejected}</strong>
          </span>
          <span>
            Total: <strong>{stats.total}</strong>
          </span>
        </div>
      )}

      <div className="mb-4">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setOffset(0);
          }}
          className="rounded border px-2 py-1 text-sm"
          aria-label="Filter beta requests by status"
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
      {loading ? (
        <p className="text-sm text-gray-500">Loading...</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs font-medium uppercase text-gray-500">
                <th className="px-3 py-2">Email</th>
                <th className="px-3 py-2">Source</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Submitted</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                <tr key={r.id} className="border-b hover:bg-gray-50">
                  <td className="px-3 py-2">{r.email}</td>
                  <td className="px-3 py-2">{r.source}</td>
                  <td className="px-3 py-2">{statusBadge(r.status)}</td>
                  <td className="px-3 py-2">{formatDate(r.created_at)}</td>
                  <td className="px-3 py-2">
                    {r.status === "pending" && (
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => handleApprove(r.id)}
                          className="text-xs text-green-600 hover:underline"
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          onClick={() => handleReject(r.id)}
                          className="text-xs text-red-600 hover:underline"
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {requests.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-4 text-center text-gray-400">
                    No beta requests found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-3 flex justify-between">
        <button
          type="button"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE_BETA))}
          className="rounded bg-gray-100 px-3 py-1 text-sm disabled:opacity-50"
        >
          Previous
        </button>
        <button
          type="button"
          disabled={requests.length < PAGE_SIZE_BETA}
          onClick={() => setOffset(offset + PAGE_SIZE_BETA)}
          className="rounded bg-gray-100 px-3 py-1 text-sm disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main Page
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
          <RagCorpusPanel />
          <ExpertQueuePanel />
          <CoachBrainPanel />
          <BetaRequestsPanel />
        </div>
      </div>
    </div>
  );
}
