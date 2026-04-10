/**
 * Shared API configuration.
 * Single source of truth for the backend base URL — import from here,
 * never inline import.meta.env.VITE_API_URL directly in components or API modules.
 */

export const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ??
  "http://localhost:8000";
