/**
 * ConsentPage — Three-tier consent management UI.
 * Requirements: FR-BRAIN-11, NFR-PRIV-01
 *
 * Tier 1 (analytics):                 service analytics consent
 * Tier 2 (health_data_processing):    explicit health data consent, separate interaction
 * Tier 3 (coach_brain_contribution):  optional toggle, service works without it
 */

import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { useConsent } from "@/hooks/useConsent";
import type { ConsentType, ConsentStatusItem } from "@/api/consent";

// Current consent policy version — bump when terms change
const CONSENT_VERSION = "1.0";

interface TierConfig {
  type: ConsentType;
  tier: number;
  title: string;
  description: string;
  required: boolean;
  details: string;
}

const TIER_CONFIG: TierConfig[] = [
  {
    type: "analytics",
    tier: 1,
    title: "Service Analytics",
    description:
      "Allows Spelix to collect anonymised usage data to improve the service.",
    required: true,
    details:
      "We collect page views and feature usage patterns using anonymised identifiers. No personally identifiable information is included. Required for service operation.",
  },
  {
    type: "health_data_processing",
    tier: 2,
    title: "Health Data Processing",
    description:
      "Allows Spelix to process your video and movement data to generate coaching feedback.",
    required: true,
    details:
      "Your video is processed by computer vision and AI models to extract joint angles, rep timing, and movement quality metrics. This constitutes processing of health-related data under GDPR Article 9. This consent is required to use the analysis features.",
  },
  {
    type: "coach_brain_contribution",
    tier: 3,
    title: "Coach Brain Contribution",
    description:
      "Optionally contribute your anonymised movement patterns to improve AI coaching for all users.",
    required: false,
    details:
      "Aggregated, anonymised movement patterns from your analyses may be used to improve the Coach Brain model. Your data is never shared individually and is always grouped with at least 20 other users before any pattern extraction. You can withdraw this at any time — the service works fully without it.",
  },
];

function getConsentForType(
  consents: ConsentStatusItem[],
  type: ConsentType,
): ConsentStatusItem | undefined {
  return consents.find((c) => c.consent_type === type);
}

interface ConsentTierCardProps {
  config: TierConfig;
  status: ConsentStatusItem | undefined;
  onGrant: (type: ConsentType) => Promise<void>;
  onWithdraw: (type: ConsentType) => Promise<void>;
}

function ConsentTierCard({
  config,
  status,
  onGrant,
  onWithdraw,
}: ConsentTierCardProps) {
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const isGranted = status?.granted === true;

  async function handleGrant() {
    setBusy(true);
    setLocalError(null);
    try {
      await onGrant(config.type);
    } catch (err) {
      setLocalError(
        err instanceof Error ? err.message : "Action failed. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleWithdraw() {
    setBusy(true);
    setLocalError(null);
    try {
      await onWithdraw(config.type);
    } catch (err) {
      setLocalError(
        err instanceof Error ? err.message : "Action failed. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
      data-testid={`consent-tier-${config.tier}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
              Tier {config.tier}
            </span>
            {!config.required && (
              <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                Optional
              </span>
            )}
          </div>
          <h2 className="mt-1 text-base font-semibold text-gray-900">
            {config.title}
          </h2>
          <p className="mt-1 text-sm text-gray-600">{config.description}</p>
        </div>

        {/* Status badge */}
        <div className="flex-shrink-0">
          {isGranted ? (
            <span
              className="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-800"
              aria-label={`${config.title} consent granted`}
            >
              Granted
            </span>
          ) : (
            <span
              className="inline-flex items-center rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-800"
              aria-label={`${config.title} consent not granted`}
            >
              Not granted
            </span>
          )}
        </div>
      </div>

      {/* Expandable details */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="mt-3 text-xs font-medium text-indigo-600 hover:text-indigo-800 focus:outline-none focus:underline"
      >
        {expanded ? "Hide details" : "Show details"}
      </button>

      {expanded && (
        <p className="mt-2 rounded-md bg-gray-50 p-3 text-xs text-gray-600">
          {config.details}
        </p>
      )}

      {/* Error */}
      {localError && (
        <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700" role="alert">
          {localError}
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex gap-3">
        {!isGranted && (
          <button
            type="button"
            onClick={handleGrant}
            disabled={busy}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50"
          >
            {busy ? "Saving..." : "Grant consent"}
          </button>
        )}
        {isGranted && (
          <button
            type="button"
            onClick={handleWithdraw}
            disabled={busy}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50"
          >
            {busy ? "Saving..." : "Withdraw consent"}
          </button>
        )}
      </div>
    </div>
  );
}

export default function ConsentPage() {
  const { consents, isLoading, error, grant, withdraw } = useConsent();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  async function handleGrant(type: ConsentType) {
    await grant(type, CONSENT_VERSION);
    if (type === "health_data_processing") {
      const redirect = searchParams.get("redirect");
      if (redirect) {
        navigate(redirect);
      }
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-500">Loading consent status...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen justify-center bg-gray-50 py-12">
      <div className="w-full max-w-2xl px-4">
        <h1 className="mb-2 text-2xl font-bold text-gray-900">
          Data & Privacy Consent
        </h1>
        <p className="mb-2 text-sm text-gray-600">
          Spelix processes your movement data to provide coaching feedback. Review
          and manage your consent preferences below.
        </p>
        <p className="mb-8 text-xs text-gray-400">
          Consent policy version {CONSENT_VERSION} — last updated April 2026.
        </p>

        {error && (
          <div className="mb-6 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
            {error}
          </div>
        )}

        <div className="space-y-4" data-testid="consent-tiers">
          {TIER_CONFIG.map((config) => (
            <ConsentTierCard
              key={config.type}
              config={config}
              status={getConsentForType(consents, config.type)}
              onGrant={handleGrant}
              onWithdraw={withdraw}
            />
          ))}
        </div>

        <p className="mt-8 text-xs text-gray-400">
          For questions about data processing, contact privacy@spelix.app. You
          may exercise your rights under GDPR Article 7 (right to withdraw
          consent) at any time using the controls above.
        </p>
      </div>
    </div>
  );
}
