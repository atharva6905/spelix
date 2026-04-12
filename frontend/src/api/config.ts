/**
 * Shared API configuration.
 * Single source of truth for the backend base URL — import from here,
 * never inline import.meta.env.VITE_API_URL directly in components or API modules.
 *
 * VITE_API_URL must use https:// in production (set in Vercel env vars).
 */

export const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ??
  "http://localhost:8000";

/** API config version — bumped to bust CDN cache after env var rename. */
export const API_CONFIG_VERSION = 2;
