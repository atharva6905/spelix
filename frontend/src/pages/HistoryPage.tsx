/**
 * HistoryPage
 *
 * Displays a reverse-chronological list of the user's analyses with status
 * badges, exercise type/variant, confidence label, and date. Clicking an item
 * navigates to /analysis/{id}. Includes per-exercise and global insights panels.
 *
 * Requirements: FR-HIST-01, FR-HIST-02, FR-HIST-03, FR-HIST-06
 */

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import {
  listAnalyses,
  type AnalysisListItem,
  type AnalysisStatus,
} from "@/api/analyses";
import {
  getExerciseInsights,
  getGlobalInsights,
  type ExerciseInsights,
  type GlobalInsights,
} from "@/api/insights";
import InsightsPanel from "@/components/InsightsPanel";
import {
  getConfidenceCategory,
  type ConfidenceCategory,
} from "@/lib/confidence";

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<AnalysisStatus, string> = {
  queued: "Queued",
  quality_gate_pending: "Checking Video",
  quality_gate_rejected: "Rejected",
  processing: "Processing",
  coaching: "Generating Feedback",
  completed: "Completed",
  failed: "Failed",
};

const STATUS_BADGE_STYLES: Record<AnalysisStatus, string> = {
  queued: "bg-gray-100 text-gray-600",
  quality_gate_pending: "bg-blue-100 text-blue-700",
  quality_gate_rejected: "bg-red-100 text-red-700",
  processing: "bg-yellow-100 text-yellow-700",
  coaching: "bg-purple-100 text-purple-700",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const EXERCISE_TYPE_LABELS: Record<string, string> = {
  squat: "Squat",
  bench: "Bench Press",
  deadlift: "Deadlift",
};

const EXERCISE_VARIANT_LABELS: Record<string, string> = {
  high_bar: "High Bar",
  low_bar: "Low Bar",
  flat: "Flat",
  incline: "Incline",
  decline: "Decline",
  conventional: "Conventional",
  sumo: "Sumo",
  romanian: "Romanian",
};

const CONFIDENCE_STYLES: Record<ConfidenceCategory, string> = {
  High: "bg-green-100 text-green-800",
  Moderate: "bg-blue-100 text-blue-800",
  Low: "bg-yellow-100 text-yellow-800",
  "Very Low": "bg-red-100 text-red-800",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function LoadingSpinner() {
  return (
    <div
      role="status"
      aria-label="Loading history"
      className="flex flex-col items-center gap-4 py-16"
    >
      <svg
        className="h-8 w-8 animate-spin text-blue-600"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
      <p className="text-gray-500 text-sm">Loading your history…</p>
    </div>
  );
}

interface AnalysisRowProps {
  item: AnalysisListItem;
}

function AnalysisRow({ item }: AnalysisRowProps) {
  const navigate = useNavigate();
  const statusLabel = STATUS_LABELS[item.status] ?? item.status;
  const statusStyle =
    STATUS_BADGE_STYLES[item.status] ?? "bg-gray-100 text-gray-600";

  const typeLabel =
    EXERCISE_TYPE_LABELS[item.exercise_type] ?? item.exercise_type;
  const variantLabel =
    EXERCISE_VARIANT_LABELS[item.exercise_variant] ?? item.exercise_variant;

  const confidenceCategory =
    item.confidence_score !== null
      ? getConfidenceCategory(item.confidence_score)
      : null;

  function handleClick() {
    void navigate(`/analysis/${item.id}`);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      void navigate(`/analysis/${item.id}`);
    }
  }

  return (
    <li
      role="button"
      tabIndex={0}
      aria-label={`${typeLabel} ${variantLabel} — ${statusLabel}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className="flex cursor-pointer items-center justify-between gap-4 rounded-lg border border-gray-100 bg-white px-5 py-4 shadow-sm transition-colors hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
      data-testid="analysis-row"
    >
      {/* Left: exercise + date */}
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-gray-900">
          {typeLabel}{" "}
          <span className="font-normal text-gray-500">— {variantLabel}</span>
        </p>
        <p className="mt-0.5 text-xs text-gray-400">{formatDate(item.created_at)}</p>
      </div>

      {/* Right: confidence + status badges */}
      <div className="flex flex-shrink-0 items-center gap-2">
        {confidenceCategory !== null && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${CONFIDENCE_STYLES[confidenceCategory]}`}
            data-testid="confidence-label"
          >
            {confidenceCategory}
          </span>
        )}
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusStyle}`}
          data-testid="status-badge"
        >
          {statusLabel}
        </span>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function HistoryPage() {
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [exerciseInsights, setExerciseInsights] = useState<
    ExerciseInsights | undefined
  >(undefined);
  const [globalInsights, setGlobalInsights] = useState<
    GlobalInsights | undefined
  >(undefined);

  // Fetch analysis list
  useEffect(() => {
    let cancelled = false;

    async function fetchHistory() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await listAnalyses();
        if (!cancelled) {
          setItems(data);
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : "Failed to load history";
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchHistory();
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch insights — silently handle 404 (B-031 not yet implemented)
  useEffect(() => {
    let cancelled = false;

    async function fetchInsights() {
      // Global insights
      try {
        const global = await getGlobalInsights();
        if (!cancelled) setGlobalInsights(global);
      } catch {
        // Endpoint not yet implemented — leave undefined → placeholder shown
      }

      // Per-exercise insights: use most recent completed analysis exercise
    }

    void fetchInsights();
    return () => {
      cancelled = true;
    };
  }, []);

  // Once items are loaded, fetch per-exercise insights for the most recent exercise
  useEffect(() => {
    if (items.length === 0) return;

    const recent = items.find((item) => item.status === "completed");
    if (!recent) return;

    let cancelled = false;

    async function fetchExerciseInsights() {
      if (!recent) return;
      try {
        const data = await getExerciseInsights(
          recent.exercise_type,
          recent.exercise_variant,
        );
        if (!cancelled) setExerciseInsights(data);
      } catch {
        // Endpoint not yet implemented — leave undefined → placeholder shown
      }
    }

    void fetchExerciseInsights();
    return () => {
      cancelled = true;
    };
  }, [items]);

  // Build exercise label from most recent completed item
  const recentCompleted = items.find((item) => item.status === "completed");
  const exerciseLabel = recentCompleted
    ? `${EXERCISE_TYPE_LABELS[recentCompleted.exercise_type] ?? recentCompleted.exercise_type} — ${EXERCISE_VARIANT_LABELS[recentCompleted.exercise_variant] ?? recentCompleted.exercise_variant}`
    : "Exercise";

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="mx-auto max-w-4xl space-y-8">

        {/* Page header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">History</h1>
          <Link
            to="/upload"
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            New Analysis
          </Link>
        </div>

        {/* Analysis list */}
        <section aria-label="Analysis history">
          {isLoading && <LoadingSpinner />}

          {!isLoading && error && (
            <div
              role="alert"
              className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              {error}
            </div>
          )}

          {!isLoading && !error && items.length === 0 && (
            <div
              className="flex flex-col items-center gap-4 rounded-lg border-2 border-dashed border-gray-200 bg-white py-16 text-center"
              data-testid="empty-state"
            >
              <p className="text-gray-500">No analyses yet.</p>
              <Link
                to="/upload"
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Upload your first video
              </Link>
            </div>
          )}

          {!isLoading && !error && items.length > 0 && (
            <ul className="space-y-3" data-testid="analysis-list">
              {items.map((item) => (
                <AnalysisRow key={item.id} item={item} />
              ))}
            </ul>
          )}
        </section>

        {/* Insights panel */}
        {!isLoading && !error && (
          <InsightsPanel
            exerciseInsights={exerciseInsights}
            globalInsights={globalInsights}
            exerciseLabel={exerciseLabel}
          />
        )}
      </div>
    </div>
  );
}
