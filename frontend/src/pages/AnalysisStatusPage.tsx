/**
 * AnalysisStatusPage
 *
 * Displays the real-time status of a video analysis using Supabase Realtime
 * with polling fallback. Maps internal status values to user-facing labels
 * per SRS Appendix B — internal status strings are NEVER shown to users.
 *
 * Requirements: FR-RESL-13, NFR-RELI-06
 */

import { Link, useNavigate, useParams } from "react-router";
import { useEffect } from "react";
import { useAnalysisStatus } from "@/hooks/useAnalysisStatus";

export default function AnalysisStatusPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const {
    status,
    statusLabel,
    isLoading,
    error,
    qualityGateResult,
    retryCount,
    isReconnecting,
  } = useAnalysisStatus(id ?? "");

  // Navigate to results when complete
  useEffect(() => {
    if (status === "completed" && id) {
      // Don't auto-navigate; let the user click the results link
      // so they can see the "Analysis complete" confirmation.
    }
  }, [status, id, navigate]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6">
      <div className="w-full max-w-md rounded-lg bg-white p-8 shadow-md">
        <h1 className="mb-6 text-2xl font-bold text-gray-900">
          Analysis Status
        </h1>

        {/* Reconnecting indicator */}
        {isReconnecting && (
          <div className="mb-4 rounded-md bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
            Connection lost — reconnecting…
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        )}

        {/* Loading spinner */}
        {isLoading && (
          <div
            role="status"
            aria-label="Loading analysis status"
            className="flex flex-col items-center gap-4 py-8"
          >
            <svg
              className="h-10 w-10 animate-spin text-blue-600"
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
            <p className="text-gray-600">Loading…</p>
          </div>
        )}

        {/* Status display — only shown after first status arrives */}
        {!isLoading && statusLabel && (
          <div className="space-y-6">
            {/* User-facing status label */}
            <p className="text-lg font-medium text-gray-800">{statusLabel}</p>

            {/* In-progress statuses: show spinner */}
            {status !== null &&
              !["quality_gate_rejected", "completed", "failed"].includes(
                status,
              ) && (
                <div className="flex items-center gap-3">
                  <svg
                    className="h-6 w-6 animate-spin text-blue-500"
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
                  <span className="text-sm text-gray-500">
                    This may take a minute…
                  </span>
                </div>
              )}

            {/* Quality gate rejection */}
            {status === "quality_gate_rejected" && (
              <div className="space-y-4">
                <div className="rounded-md bg-orange-50 p-4">
                  <h2 className="mb-2 font-semibold text-orange-800">
                    What to check:
                  </h2>
                  {qualityGateResult?.checks
                    ?.filter((c) => !c.passed)
                    .map((check) => (
                      <p
                        key={check.name}
                        className="text-sm text-orange-700"
                      >
                        {check.user_message}
                      </p>
                    ))}
                </div>
                <Link
                  to="/upload"
                  className="inline-block rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Upload a new video
                </Link>
              </div>
            )}

            {/* Completed state */}
            {status === "completed" && (
              <div className="space-y-4">
                <div className="rounded-md bg-green-50 p-4 text-green-800">
                  Your analysis is ready.
                </div>
                <Link
                  to={`/results/${id}`}
                  className="inline-block rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  View results
                </Link>
              </div>
            )}

            {/* Failed state */}
            {status === "failed" && (
              <div className="space-y-4">
                <div className="rounded-md bg-red-50 p-4 text-red-800">
                  Something went wrong during analysis. Please try again.
                </div>
                {retryCount < 3 && (
                  <button
                    type="button"
                    onClick={() => navigate(`/upload`)}
                    className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                  >
                    Retry
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
