/**
 * Custom hook: useAnalysisDetail
 *
 * Fetches full analysis detail from GET /api/v1/analyses/{id}.
 * Includes coaching result, rep metrics, and artifact paths.
 *
 * Requirements: FR-RESL-01a–05, FR-RESL-08, FR-RESL-10–11, FR-SCOR-09–10
 */

import { useEffect, useState } from "react";
import { getAnalysisDetail, type AnalysisDetail } from "@/api/analyses";

export interface UseAnalysisDetailResult {
  analysis: AnalysisDetail | null;
  isLoading: boolean;
  error: string | null;
}

export function useAnalysisDetail(id: string): UseAnalysisDetailResult {
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    let cancelled = false;

    async function fetchDetail() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getAnalysisDetail(id);
        if (!cancelled) {
          setAnalysis(data);
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : "Failed to load analysis";
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchDetail();

    return () => {
      cancelled = true;
    };
  }, [id]);

  return { analysis, isLoading, error };
}
