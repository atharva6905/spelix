/**
 * Centralized API calls for the user profile resource.
 * Requirements: FR-PROF-01 through FR-PROF-05
 */

import { supabase } from "@/lib/supabase";
import { API_BASE } from "@/api/config";
import { buildApiError } from "@/api/errors";

export type Sex = "male" | "female" | "prefer_not_to_say";

export interface ProfileResponse {
  id: string;
  user_id: string;
  height_cm: number | null;
  weight_kg: number | null;
  age: number | null;
  experience_level: string | null;
  arm_span_cm: number | null;
  femur_length_cm: number | null;
  sex: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProfileUpdateRequest {
  height_cm: number;
  weight_kg: number;
  age: number;
  experience_level: "beginner" | "intermediate" | "advanced";
  arm_span_cm?: number | null;
  femur_length_cm?: number | null;
  sex?: Sex | null;
}

async function getAuthToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    throw new Error("Not authenticated");
  }
  return token;
}

export async function getProfile(): Promise<ProfileResponse> {
  const token = await getAuthToken();
  const resp = await fetch(`${API_BASE}/api/v1/profiles/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw buildApiError(resp.status, body);
  }

  return resp.json() as Promise<ProfileResponse>;
}

export async function updateProfile(data: ProfileUpdateRequest): Promise<ProfileResponse> {
  const token = await getAuthToken();
  const resp = await fetch(`${API_BASE}/api/v1/profiles/me`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw buildApiError(resp.status, body);
  }

  return resp.json() as Promise<ProfileResponse>;
}
