/**
 * Hook: useConsent
 *
 * Manages consent state for the three-tier consent system (FR-BRAIN-11).
 * Fetches current consent status on mount and exposes grant/withdraw actions.
 */

import { useEffect, useState, useCallback } from "react";
import {
  getConsents,
  grantConsent,
  withdrawConsent,
  type ConsentType,
  type ConsentStatusItem,
} from "@/api/consent";

export interface UseConsentResult {
  consents: ConsentStatusItem[];
  isLoading: boolean;
  error: string | null;
  grant: (type: ConsentType, version: string) => Promise<void>;
  withdraw: (type: ConsentType) => Promise<void>;
}

export function useConsent(): UseConsentResult {
  const [consents, setConsents] = useState<ConsentStatusItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchConsents() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getConsents();
        if (!cancelled) {
          setConsents(data);
        }
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : "Failed to load consent status";
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchConsents();

    return () => {
      cancelled = true;
    };
  }, []);

  const grant = useCallback(
    async (type: ConsentType, version: string) => {
      setError(null);
      await grantConsent(type, version);
      // Refresh full consent state after grant
      const updated = await getConsents();
      setConsents(updated);
    },
    [],
  );

  const withdraw = useCallback(
    async (type: ConsentType) => {
      setError(null);
      await withdrawConsent(type);
      // Refresh full consent state after withdrawal
      const updated = await getConsents();
      setConsents(updated);
    },
    [],
  );

  return { consents, isLoading, error, grant, withdraw };
}
