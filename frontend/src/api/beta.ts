/**
 * Centralized API calls for the landing-page beta-request endpoint.
 * Anonymous — no auth token attached.
 */

import { API_BASE } from "@/api/config";
import { buildApiError } from "@/api/errors";

export type BetaRequestSource = "hero" | "final_cta" | "reddit" | "dm" | "other";

export interface BetaRequestInput {
  email: string;
  source: BetaRequestSource;
  consented: boolean;
}

export interface BetaRequestResponse {
  id: string;
  status: string;
  created_at: string;
}

export async function getBetaCount(): Promise<{ count: number }> {
  const resp = await fetch(`${API_BASE}/api/v1/beta/count`);
  if (!resp.ok) throw new Error("Failed to fetch beta count");
  return resp.json() as Promise<{ count: number }>;
}

export async function requestBetaAccess(
  input: BetaRequestInput,
): Promise<BetaRequestResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/beta/requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: input.email.trim().toLowerCase(),
      source: input.source,
      consented_to_beta_terms: input.consented,
    }),
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw buildApiError(resp.status, body);
  }

  return resp.json() as Promise<BetaRequestResponse>;
}
