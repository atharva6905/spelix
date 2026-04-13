/**
 * ExpertPortalPage — Expert reviewer queue dashboard.
 *
 * Requirements: FR-EXPV-01 (role check), FR-EXPV-02 (review queue)
 *
 * - FR-EXPV-01: Only expert_reviewer or admin roles may access.
 * - FR-EXPV-02: Paginated queue of analyses awaiting expert annotation,
 *   filterable by queue_type (flagged, low_quality, first_run, papers).
 */

import { useState, useEffect, useCallback } from "react";
import { Link, Navigate } from "react-router";
import { supabase } from "@/lib/supabase";
import {
  getExpertQueue,
  type ExpertQueueItem,
} from "@/api/expert";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type QueueType = "all" | "flagged" | "low_quality" | "first_run" | "papers_pending";

const PAGE_SIZE = 20;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function shortId(id: string): string {
  return id.slice(0, 8) + "\u2026";
}

/**
 * Confidence category label — never shows raw decimal (NFR-USAB-03).
 * Thresholds per SRS: High ≥0.80, Moderate 0.65–0.79, Low 0.50–0.64, Very Low <0.50.
 */
function confidenceCategory(score: number | null): string {
  if (score === null) return "Unknown";
  if (score >= 0.8) return "High";
  if (score >= 0.65) return "Moderate";
  if (score >= 0.5) return "Low";
  return "Very Low";
}

const CONFIDENCE_BADGE_STYLES: Record<string, string> = {
  High: "bg-green-100 text-green-700",
  Moderate: "bg-blue-100 text-blue-700",
  Low: "bg-yellow-100 text-yellow-700",
  "Very Low": "bg-red-100 text-red-700",
  Unknown: "bg-gray-100 text-gray-500",
};

// ---------------------------------------------------------------------------
// Tab configuration
// ---------------------------------------------------------------------------

interface Tab {
  label: string;
  queueType: QueueType;
}

const TABS: Tab[] = [
  { label: "Flagged", queueType: "flagged" },
  { label: "Low Quality", queueType: "low_quality" },
  { label: "First Run", queueType: "first_run" },
  { label: "Papers Pending", queueType: "papers_pending" },
];

// ---------------------------------------------------------------------------
// Queue table component
// ---------------------------------------------------------------------------

interface QueueTableProps {
  items: ExpertQueueItem[];
  loading: boolean;
  error: string | null;
  offset: number;
  onPrevious: () => void;
  onNext: () => void;
}

function QueueTable({ items, loading, error, offset, onPrevious, onNext }: QueueTableProps) {
  if (loading) {
    return <p className="py-8 text-center text-sm text-gray-500">Loading queue...</p>;
  }

  if (error) {
    return <p className="py-4 text-sm text-red-600">{error}</p>;
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
              <th className="pb-3 pr-4">Analysis ID</th>
              <th className="pb-3 pr-4">Exercise</th>
              <th className="pb-3 pr-4">Variant</th>
              <th className="pb-3 pr-4">Confidence</th>
              <th className="pb-3 pr-4">Flagged</th>
              <th className="pb-3 pr-4">Annotations</th>
              <th className="pb-3 pr-4">Created</th>
              <th className="pb-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const category = confidenceCategory(item.confidence_score);
              return (
                <tr
                  key={item.analysis_id}
                  className="border-b border-gray-100 last:border-0"
                >
                  <td className="py-3 pr-4 font-mono text-xs text-gray-500">
                    {shortId(item.analysis_id)}
                  </td>
                  <td className="py-3 pr-4 capitalize text-gray-700">
                    {item.exercise_type}
                  </td>
                  <td className="py-3 pr-4 capitalize text-gray-700">
                    {item.exercise_variant ?? "—"}
                  </td>
                  <td className="py-3 pr-4">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${CONFIDENCE_BADGE_STYLES[category]}`}
                    >
                      {category}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    {item.flagged_for_review ? (
                      <span className="inline-flex items-center rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700">
                        Flagged
                      </span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="py-3 pr-4 text-gray-700">
                    {item.annotation_count}
                  </td>
                  <td className="py-3 pr-4 text-gray-700">
                    {formatDate(item.created_at)}
                  </td>
                  <td className="py-3">
                    <Link
                      to={`/expert/analyses/${item.analysis_id}`}
                      className="rounded bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                    >
                      Review
                    </Link>
                  </td>
                </tr>
              );
            })}
            {items.length === 0 && (
              <tr>
                <td colSpan={8} className="py-8 text-center text-sm text-gray-400">
                  No analyses in this queue.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <button
          type="button"
          onClick={onPrevious}
          disabled={offset === 0}
          className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-600 disabled:opacity-40"
        >
          Previous
        </button>
        <span className="text-xs text-gray-400">
          Showing {offset + 1}–{offset + items.length}
        </span>
        <button
          type="button"
          onClick={onNext}
          disabled={items.length < PAGE_SIZE}
          className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-600 disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ExpertPortalPage() {
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);
  const [activeTab, setActiveTab] = useState<QueueType>("flagged");
  const [items, setItems] = useState<ExpertQueueItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  // Role check — FR-EXPV-01
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const session = data.session;
      if (!session) {
        setIsAuthorized(false);
        return;
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const payload = session.user as any;
      const role =
        payload?.app_metadata?.role ?? payload?.user_metadata?.role ?? null;
      setIsAuthorized(role === "expert_reviewer" || role === "admin");
    });
  }, []);

  const fetchQueue = useCallback(async () => {
    if (activeTab === "papers_pending") return;
    setLoading(true);
    setError(null);
    try {
      const data = await getExpertQueue(PAGE_SIZE, offset, activeTab);
      setItems(data);
    } catch (err) {
      console.error("Failed to load expert queue", err);
      setError("Failed to load queue. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [activeTab, offset]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  // Reset offset when switching tabs
  function handleTabChange(tab: QueueType) {
    setActiveTab(tab);
    setOffset(0);
    setItems([]);
    setError(null);
  }

  if (isAuthorized === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-500">Checking permissions...</p>
      </div>
    );
  }

  if (!isAuthorized) {
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
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900">Expert Reviewer Portal</h1>
          <Link
            to="/expert/papers/upload"
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Upload Paper
          </Link>
        </div>

        {/* Tab navigation */}
        <div className="mb-6 border-b border-gray-200">
          <nav className="-mb-px flex gap-6" aria-label="Queue tabs">
            {TABS.map((tab) => (
              <button
                key={tab.queueType}
                type="button"
                onClick={() => handleTabChange(tab.queueType)}
                className={`whitespace-nowrap border-b-2 pb-3 text-sm font-medium transition-colors ${
                  activeTab === tab.queueType
                    ? "border-indigo-500 text-indigo-600"
                    : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab content */}
        <section className="rounded-lg bg-white p-6 shadow-sm">
          {activeTab === "papers_pending" ? (
            <div className="py-8 text-center">
              <p className="text-sm text-gray-500">
                Paper review queue coming soon. Use the{" "}
                <Link to="/expert/papers/upload" className="text-indigo-600 underline">
                  Upload Paper
                </Link>{" "}
                page to submit research documents.
              </p>
            </div>
          ) : (
            <QueueTable
              items={items}
              loading={loading}
              error={error}
              offset={offset}
              onPrevious={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              onNext={() => setOffset(offset + PAGE_SIZE)}
            />
          )}
        </section>
      </div>
    </div>
  );
}
