/**
 * ExpertThresholdsPage — FR-EXPV-08 threshold validation portal.
 *
 * Read-only view of angle thresholds from config/thresholds_v1.json.
 * Reviewers flag thresholds that conflict with literature; admins
 * resolve flags via PR (FR-SCOR-11). Values are never edited here.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router";

import ThresholdFlagModal from "@/components/ThresholdFlagModal";
import {
  createThresholdFlag,
  getThresholdListing,
  listMyThresholdFlags,
  type ThresholdFlagCreate,
  type ThresholdFlagResponse,
  type ThresholdListing,
  type ThresholdRow,
} from "@/api/expert";
import { supabase } from "@/lib/supabase";

type Tab = "thresholds" | "my_flags";

const SECTION_LABELS: Record<ThresholdRow["section"], string> = {
  squat: "Squat",
  bench: "Bench",
  deadlift: "Deadlift",
  control: "Control",
};

export default function ExpertThresholdsPage() {
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [tab, setTab] = useState<Tab>("thresholds");
  const [listing, setListing] = useState<ThresholdListing | null>(null);
  const [flags, setFlags] = useState<ThresholdFlagResponse[]>([]);
  const [modalRow, setModalRow] = useState<ThresholdRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const session = data.session;
      if (!session) {
        setAuthorized(false);
        return;
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const payload = session.user as any;
      const role =
        payload?.app_metadata?.role ?? payload?.user_metadata?.role ?? null;
      setAuthorized(role === "expert_reviewer" || role === "admin");
    });
  }, []);

  const loadListing = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getThresholdListing();
      setListing(data);
    } catch {
      setError("Failed to load thresholds.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadFlags = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listMyThresholdFlags(50, 0);
      setFlags(data);
    } catch {
      setError("Failed to load flags.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authorized !== true) return;
    if (tab === "thresholds") {
      if (!listing) void loadListing();
    } else {
      void loadFlags();
    }
  }, [authorized, tab, listing, loadListing, loadFlags]);

  async function handleFlagSubmit(payload: ThresholdFlagCreate) {
    await createThresholdFlag(payload);
    setModalRow(null);
    void loadFlags();
  }

  const sections = useMemo(() => {
    if (!listing) return [];
    return (Object.keys(SECTION_LABELS) as ThresholdRow["section"][]).map(
      (section) => ({
        section,
        label: SECTION_LABELS[section],
        rows: listing.sections[section] ?? [],
      }),
    );
  }, [listing]);

  if (authorized === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-500">Checking permissions…</p>
      </div>
    );
  }

  if (!authorized) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen bg-gray-50 py-10">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900">Threshold Validation</h1>
          <Link
            to="/expert"
            className="text-sm text-indigo-600 underline"
          >
            Back to portal
          </Link>
        </div>
        <p className="mb-6 text-sm text-gray-600">
          Thresholds are defined in <code>config/thresholds_v1.json</code> and
          changed via PR review (FR-SCOR-11). Flag any value that conflicts
          with current literature; an admin will review and, if appropriate,
          open a PR updating the config.
        </p>

        <div className="mb-6 flex gap-4 border-b border-gray-200">
          <button
            type="button"
            onClick={() => setTab("thresholds")}
            className={`-mb-px border-b-2 pb-2 text-sm font-medium ${
              tab === "thresholds"
                ? "border-indigo-500 text-indigo-600"
                : "border-transparent text-gray-500"
            }`}
          >
            Current thresholds
          </button>
          <button
            type="button"
            onClick={() => setTab("my_flags")}
            className={`-mb-px border-b-2 pb-2 text-sm font-medium ${
              tab === "my_flags"
                ? "border-indigo-500 text-indigo-600"
                : "border-transparent text-gray-500"
            }`}
          >
            My flags
          </button>
        </div>

        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        {tab === "thresholds" && listing && (
          <>
            <p className="mb-4 text-xs text-gray-500">
              Config version: {listing.version}
            </p>
            {sections.map(({ section, label, rows }) => (
              <section key={section} className="mb-8 rounded-lg bg-white p-4 shadow-sm">
                <h2 className="mb-3 text-lg font-semibold text-gray-900">
                  {label}
                </h2>
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                      <th className="pb-2 pr-4">Key</th>
                      <th className="pb-2 pr-4">Value</th>
                      <th className="pb-2 pr-4">Unit</th>
                      <th className="pb-2 pr-4">Citation</th>
                      <th className="pb-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr
                        key={row.key}
                        className="border-b border-gray-100 last:border-0"
                      >
                        <td className="py-2 pr-4 font-mono text-xs text-gray-700">
                          {row.key}
                        </td>
                        <td className="py-2 pr-4 text-gray-900">{row.value}</td>
                        <td className="py-2 pr-4 text-gray-500">{row.unit}</td>
                        <td className="py-2 pr-4 text-xs text-gray-600">
                          {row.provenance_citation ?? "—"}
                        </td>
                        <td className="py-2">
                          <button
                            type="button"
                            onClick={() => setModalRow(row)}
                            className="rounded bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                          >
                            Flag
                          </button>
                        </td>
                      </tr>
                    ))}
                    {rows.length === 0 && (
                      <tr>
                        <td colSpan={5} className="py-4 text-center text-xs text-gray-400">
                          No thresholds in this section.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </section>
            ))}
          </>
        )}

        {tab === "my_flags" && (
          <section className="rounded-lg bg-white p-4 shadow-sm">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                  <th className="pb-2 pr-4">Section</th>
                  <th className="pb-2 pr-4">Key</th>
                  <th className="pb-2 pr-4">Current</th>
                  <th className="pb-2 pr-4">Proposed</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2">Submitted</th>
                </tr>
              </thead>
              <tbody>
                {flags.map((f) => (
                  <tr key={f.id} className="border-b border-gray-100 last:border-0">
                    <td className="py-2 pr-4 capitalize">{f.section}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{f.key}</td>
                    <td className="py-2 pr-4">{f.current_value}</td>
                    <td className="py-2 pr-4">{f.proposed_value}</td>
                    <td className="py-2 pr-4 capitalize">{f.status}</td>
                    <td className="py-2 text-xs text-gray-500">
                      {new Date(f.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
                {flags.length === 0 && !loading && (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-sm text-gray-400">
                      No flags submitted yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>
        )}

        <ThresholdFlagModal
          row={modalRow}
          onClose={() => setModalRow(null)}
          onSubmit={handleFlagSubmit}
        />
      </div>
    </div>
  );
}
