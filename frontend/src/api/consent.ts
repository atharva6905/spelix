/**
 * Centralized API calls for the consent resource.
 * Requirements: FR-BRAIN-11, NFR-PRIV-01
 *
 * Three consent types (from migration 004 CHECK constraint):
 *   analytics              — Tier 1: service analytics
 *   health_data_processing — Tier 2: explicit health data consent
 *   coach_brain_contribution — Tier 3: optional Coach Brain contribution
 */

import { supabase } from "@/lib/supabase";
import { API_BASE } from "@/api/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ConsentType =
  | "analytics"
  | "health_data_processing"
  | "coach_brain_contribution";

export interface ConsentRecord {
  id: string;
  user_id: string;
  consent_type: ConsentType;
  granted: boolean;
  granted_at: string | null;
  withdrawn_at: string | null;
  consent_version: string;
  created_at: string;
}

export interface ConsentStatusItem {
  consent_type: ConsentType;
  granted: boolean;
  granted_at: string | null;
  withdrawn_at: string | null;
  consent_version: string;
}

export type ConsentStatusResponse = ConsentStatusItem[];

export interface GrantConsentRequest {
  consent_type: ConsentType;
  consent_version: string;
}

export interface WithdrawConsentRequest {
  consent_type: ConsentType;
}

// ---------------------------------------------------------------------------
// Auth helper (mirrors analyses.ts pattern)
// ---------------------------------------------------------------------------

async function getAuthToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    throw new Error("Not authenticated");
  }
  return token;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/**
 * GET /api/v1/consent
 * Returns the latest consent state per type for the authenticated user.
 */
export async function getConsents(): Promise<ConsentStatusResponse> {
  const token = await getAuthToken();
  const resp = await fetch(`${API_BASE}/api/v1/consent`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const message =
      body.error?.message ?? body.detail ?? "Failed to fetch consent status";
    throw new Error(message);
  }

  return resp.json() as Promise<ConsentStatusResponse>;
}

/**
 * POST /api/v1/consent
 * Grants consent for the given type. Inserts a new row with granted=true.
 */
export async function grantConsent(
  consent_type: ConsentType,
  consent_version: string,
): Promise<ConsentRecord> {
  const token = await getAuthToken();
  const body: GrantConsentRequest = { consent_type, consent_version };
  const resp = await fetch(`${API_BASE}/api/v1/consent`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const errBody = await resp.json().catch(() => ({}));
    const message =
      errBody.error?.message ?? errBody.detail ?? "Failed to grant consent";
    throw new Error(message);
  }

  return resp.json() as Promise<ConsentRecord>;
}

/**
 * POST /api/v1/consent/withdraw
 * Withdraws consent for the given type. Inserts a new row with granted=false.
 */
export async function withdrawConsent(
  consent_type: ConsentType,
): Promise<ConsentRecord> {
  const token = await getAuthToken();
  const body: WithdrawConsentRequest = { consent_type };
  const resp = await fetch(`${API_BASE}/api/v1/consent/withdraw`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const errBody = await resp.json().catch(() => ({}));
    const message =
      errBody.error?.message ?? errBody.detail ?? "Failed to withdraw consent";
    throw new Error(message);
  }

  return resp.json() as Promise<ConsentRecord>;
}
