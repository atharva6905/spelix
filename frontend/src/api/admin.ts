/**
 * Centralized API calls for admin resource.
 * Requirements: FR-ADMN-01 through FR-ADMN-05
 */

import { supabase } from "@/lib/supabase";
import { API_BASE } from "@/api/config";

export interface AdminUser {
  user_id: string;
  height_cm: number | null;
  weight_kg: number | null;
  age: number | null;
  experience_level: string | null;
  analysis_count: number;
  created_at: string;
  updated_at: string;
}

export interface AdminAnalysis {
  id: string;
  user_id: string;
  status: string;
  exercise_type: string;
  exercise_variant: string;
  confidence_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface AdminHealth {
  queue_depth: number;
  worker_heartbeat: boolean;
  db_ok: boolean;
}

async function getAuthToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    throw new Error("Not authenticated");
  }
  return token;
}

async function adminFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getAuthToken();
  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const err = { status: resp.status, ...(body.detail ?? body) };
    throw err;
  }

  if (resp.status === 204) {
    return undefined as unknown as T;
  }

  return resp.json() as Promise<T>;
}

export async function listAdminUsers(limit = 50, offset = 0): Promise<AdminUser[]> {
  return adminFetch<AdminUser[]>(
    `/api/v1/admin/users?limit=${limit}&offset=${offset}`,
  );
}

export async function deleteAdminUser(userId: string): Promise<void> {
  return adminFetch<void>(`/api/v1/admin/users/${userId}`, { method: "DELETE" });
}

export async function disableAdminUser(userId: string): Promise<{ message: string }> {
  return adminFetch<{ message: string }>(`/api/v1/admin/users/${userId}/disable`, {
    method: "PATCH",
  });
}

export async function listAdminAnalyses(
  limit = 50,
  offset = 0,
  status?: string,
): Promise<AdminAnalysis[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (status) {
    params.set("status", status);
  }
  return adminFetch<AdminAnalysis[]>(`/api/v1/admin/analyses?${params.toString()}`);
}

export async function getAdminHealth(): Promise<AdminHealth> {
  return adminFetch<AdminHealth>("/api/v1/admin/health");
}
