/**
 * Custom hook: useAnalysisStatus
 *
 * Subscribes to Supabase Realtime postgres_changes on the `analyses` table
 * for a given analysis ID. Falls back to polling GET /analyses/{id}/status
 * every 10 seconds when the Realtime channel disconnects.
 *
 * Requirements: FR-RESL-13, NFR-RELI-06
 */

import { useEffect, useRef, useState } from "react";
import { supabase } from "@/lib/supabase";
import {
  getAnalysisStatus,
  type AnalysisStatus,
  type DetectionResult,
  type QualityGateResult,
} from "@/api/analyses";

export const STATUS_LABELS: Record<AnalysisStatus, string> = {
  queued: "Preparing to analyse…",
  quality_gate_pending: "Preparing to analyse…",
  quality_gate_rejected: "Video could not be processed",
  processing: "Analysing your form…",
  coaching: "Generating coaching feedback…",
  completed: "Analysis complete",
  failed: "Analysis failed",
};

const TERMINAL_STATUSES: AnalysisStatus[] = [
  "quality_gate_rejected",
  "completed",
  "failed",
];

const POLL_INTERVAL_MS = 10_000;

export interface UseAnalysisStatusResult {
  status: AnalysisStatus | null;
  statusLabel: string | null;
  isLoading: boolean;
  error: string | null;
  detectionResult: DetectionResult | null;
  qualityGateResult: QualityGateResult | null;
  retryCount: number;
  isReconnecting: boolean;
}

export function useAnalysisStatus(
  analysisId: string,
): UseAnalysisStatusResult {
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [detectionResult, setDetectionResult] =
    useState<DetectionResult | null>(null);
  const [qualityGateResult, setQualityGateResult] =
    useState<QualityGateResult | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, _setError] = useState<string | null>(null);
  const [isReconnecting, setIsReconnecting] = useState(false);

  // Refs to keep stable references without triggering re-renders
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const channelRef = useRef<ReturnType<typeof supabase.channel> | null>(null);
  // Set to true right before we call channel.unsubscribe() on a terminal
  // status, so the subsequent CLOSED callback doesn't flip on the
  // "reconnecting" banner when there's nothing to reconnect to (D-028).
  const intentionalUnsubscribeRef = useRef(false);

  function applyUpdate(row: {
    status: AnalysisStatus;
    detection_result?: DetectionResult | null;
    quality_gate_result?: QualityGateResult | null;
    retry_count?: number;
  }) {
    setStatus(row.status);
    if (row.detection_result !== undefined) {
      setDetectionResult(row.detection_result);
    }
    setQualityGateResult(row.quality_gate_result ?? null);
    setRetryCount(row.retry_count ?? 0);
    setIsLoading(false);
  }

  function stopPolling() {
    if (pollIntervalRef.current !== null) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }

  function startPolling() {
    stopPolling();
    pollIntervalRef.current = setInterval(async () => {
      try {
        const data = await getAnalysisStatus(analysisId);
        applyUpdate(data as Parameters<typeof applyUpdate>[0]);
        if (TERMINAL_STATUSES.includes(data.status)) {
          stopPolling();
        }
      } catch (err) {
        console.error("[useAnalysisStatus] poll error:", err);
      }
    }, POLL_INTERVAL_MS);
  }

  useEffect(() => {
    if (!analysisId) return;

    intentionalUnsubscribeRef.current = false;
    const channelName = `analysis:${analysisId}`;

    const channel = supabase
      .channel(channelName)
      .on(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        "postgres_changes" as any,
        {
          event: "UPDATE",
          schema: "public",
          table: "analyses",
          filter: `id=eq.${analysisId}`,
        },
        (payload: { new: Parameters<typeof applyUpdate>[0] }) => {
          setIsReconnecting(false);
          stopPolling();
          applyUpdate(payload.new);
          if (TERMINAL_STATUSES.includes(payload.new.status)) {
            intentionalUnsubscribeRef.current = true;
            channel.unsubscribe();
          }
        },
      )
      .subscribe((subscribeStatus: string) => {
        if (subscribeStatus === "SUBSCRIBED") {
          setIsReconnecting(false);
          stopPolling();
        } else if (
          subscribeStatus === "CHANNEL_ERROR" ||
          subscribeStatus === "TIMED_OUT" ||
          subscribeStatus === "CLOSED"
        ) {
          if (intentionalUnsubscribeRef.current) return;
          setIsReconnecting(true);
          startPolling();
        }
      });

    channelRef.current = channel;

    // Fetch current state immediately — Realtime only delivers future UPDATEs,
    // so if the status changed before the subscription was established we'd
    // stay on "Loading…" forever.
    getAnalysisStatus(analysisId)
      .then((data) => {
        applyUpdate(data as Parameters<typeof applyUpdate>[0]);
        if (TERMINAL_STATUSES.includes(data.status)) {
          intentionalUnsubscribeRef.current = true;
          channel.unsubscribe();
        }
      })
      .catch((err) => {
        console.error("[useAnalysisStatus] initial fetch error:", err);
      });

    return () => {
      stopPolling();
      supabase.removeChannel(channel);
    };
    // startPolling and stopPolling are stable (defined in the same scope) — disable exhaustive-deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisId]);

  const statusLabel = status !== null ? STATUS_LABELS[status] : null;

  return {
    status,
    statusLabel,
    isLoading,
    error,
    detectionResult,
    qualityGateResult,
    retryCount,
    isReconnecting,
  };
}
