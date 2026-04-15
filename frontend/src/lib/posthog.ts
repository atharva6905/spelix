import posthog from "posthog-js";

let initialised = false;

export function initPostHog(): void {
  if (initialised) return;
  const key = import.meta.env.VITE_POSTHOG_KEY;
  if (!key) return;
  posthog.init(key, {
    api_host: import.meta.env.VITE_POSTHOG_HOST ?? "https://eu.i.posthog.com",
    // Cookieless / IP-free — avoids GDPR cookie banner (landing-page-plan §12 D-8).
    persistence: "memory",
    disable_session_recording: true,
    autocapture: false,
    ip: false,
    property_blacklist: ["$ip"],
  });
  initialised = true;
}

export function capture(event: string, props?: Record<string, unknown>): void {
  if (!initialised) return;
  posthog.capture(event, props);
}

// Exported for testing only.
export function _resetForTests() {
  initialised = false;
}
