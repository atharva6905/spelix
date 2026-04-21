/**
 * AdminCoachBrainCandidatesPage - expert review queue for distilled
 * Coach Brain candidates (P3-006, FR-ADMN-12, FR-BRAIN-07).
 *
 * Single-screen card view; one candidate rendered at a time. Approve /
 * Reject / Edit + keyboard shortcuts (a/r/e/s) drive the under-30-second
 * review loop. The approve path INSERTs a new coach_brain_entries row and
 * upserts a Qdrant point atomically on the backend (ADR-BRAIN-REVIEW-01).
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import {
  approveCoachBrainCandidate,
  getCoachBrainCandidateSimilar,
  getCoachBrainCandidateStats,
  listCoachBrainCandidates,
  rejectCoachBrainCandidate,
  type CoachBrainCandidate,
  type SimilarEntry,
} from "@/api/admin";

const PAGE_SIZE = 25;

export default function AdminCoachBrainCandidatesPage() {
  const [queue, setQueue] = useState<CoachBrainCandidate[]>([]);
  const [cursor, setCursor] = useState(0);
  const [totalPending, setTotalPending] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rows, stats] = await Promise.all([
        listCoachBrainCandidates(PAGE_SIZE, 0),
        getCoachBrainCandidateStats(),
      ]);
      setQueue(rows);
      setCursor(0);
      setTotalPending(stats.total_pending);
    } catch {
      setError("Failed to load candidates. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const current = queue[cursor] ?? null;

  const advance = useCallback(() => {
    setCursor((c) => c + 1);
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 py-10">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <Link
              to="/admin"
              className="text-sm text-blue-600 hover:underline"
            >
              &larr; Admin Dashboard
            </Link>
            <h1 className="mt-2 text-2xl font-bold text-gray-900">
              Coach Brain Review Queue
            </h1>
            <p className="mt-1 text-sm text-gray-600">
              {totalPending} pending
            </p>
          </div>
        </div>

        {loading ? (
          <p className="text-sm text-gray-500">Loading candidates...</p>
        ) : error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : current ? (
          <CandidateCard
            candidate={current}
            onAdvance={advance}
            onRefresh={load}
          />
        ) : (
          <div className="rounded-lg bg-white p-8 text-center shadow">
            <p className="text-lg font-medium text-gray-900">
              No candidates to review
            </p>
            <p className="mt-2 text-sm text-gray-500">
              Fresh candidates appear here when the distillation pipeline
              produces new insights.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

interface CandidateCardProps {
  candidate: CoachBrainCandidate;
  onAdvance: () => void;
  onRefresh: () => void;
}

function CandidateCard({ candidate, onAdvance, onRefresh }: CandidateCardProps) {
  const [mode, setMode] = useState<"view" | "edit" | "reject">("view");
  const [draft, setDraft] = useState(candidate.content);
  const [rejectReason, setRejectReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    setMode("view");
    setDraft(candidate.content);
    setRejectReason("");
    setActionError(null);
  }, [candidate.id, candidate.content]);

  const handleApprove = useCallback(
    async (withOverride: boolean) => {
      setSubmitting(true);
      setActionError(null);
      try {
        const override = withOverride ? draft.trim() : undefined;
        await approveCoachBrainCandidate(candidate.id, override);
        onAdvance();
        onRefresh();
      } catch {
        setActionError("Approve failed. Please retry.");
      } finally {
        setSubmitting(false);
      }
    },
    [candidate.id, draft, onAdvance, onRefresh],
  );

  async function handleReject() {
    const trimmed = rejectReason.trim();
    if (!trimmed) return;
    setSubmitting(true);
    setActionError(null);
    try {
      await rejectCoachBrainCandidate(candidate.id, trimmed);
      onAdvance();
      onRefresh();
    } catch {
      setActionError("Reject failed. Please retry.");
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (mode !== "view") return;
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      if (e.key === "a") {
        e.preventDefault();
        void handleApprove(false);
      } else if (e.key === "r") {
        e.preventDefault();
        setMode("reject");
      } else if (e.key === "e") {
        e.preventDefault();
        setMode("edit");
      } else if (e.key === "s") {
        e.preventDefault();
        onAdvance();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode, onAdvance, handleApprove]);

  return (
    <article className="rounded-lg bg-white p-6 shadow">
      {candidate.requires_technical_review && (
        <div className="mb-4 rounded-md border border-orange-300 bg-orange-50 p-3 text-sm text-orange-900">
          <p className="font-semibold">
            Compensation entry - biomechanics reviewer required
          </p>
          <p className="mt-1 text-xs">
            FR-ADMN-12: compensation entries encode multi-step causal chains
            and must be reviewed by a biomechanics-qualified reviewer before
            promotion.
          </p>
        </div>
      )}

      <header className="mb-4 flex flex-wrap gap-2">
        <Badge tone="blue">{candidate.exercise}</Badge>
        {candidate.phase && <Badge tone="gray">{candidate.phase}</Badge>}
        <Badge tone="purple">{candidate.entry_type}</Badge>
        <Badge tone="amber">{candidate.lifecycle_decision}</Badge>
      </header>

      <p className="mb-3 text-xs text-gray-500">
        Shortcuts: <kbd className="rounded border px-1">a</kbd> approve
        &middot; <kbd className="rounded border px-1">r</kbd> reject &middot;{" "}
        <kbd className="rounded border px-1">e</kbd> edit &middot;{" "}
        <kbd className="rounded border px-1">s</kbd> skip
      </p>

      {mode === "view" && (
        <p className="mb-4 whitespace-pre-wrap rounded-md bg-gray-50 p-4 text-base text-gray-900">
          {candidate.content}
        </p>
      )}

      {mode === "edit" && (
        <div className="mb-4">
          <label
            htmlFor="candidate-content"
            className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500"
          >
            Content
          </label>
          <textarea
            id="candidate-content"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={4}
            className="w-full rounded-md border border-gray-300 p-2 text-sm"
          />
        </div>
      )}

      {mode === "reject" && (
        <div className="mb-4">
          <label
            htmlFor="reject-reason"
            className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500"
          >
            Reason
          </label>
          <input
            id="reject-reason"
            type="text"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            className="w-full rounded-md border border-gray-300 p-2 text-sm"
            placeholder="e.g. off-topic, contradicts existing entry..."
          />
        </div>
      )}

      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <EvalScoreCard scores={candidate.eval_scores} />
        <CoveCard
          verified={candidate.cove_verified}
          explanation={candidate.cove_explanation}
        />
      </div>

      <SimilarEntriesList candidateId={candidate.id} />

      {candidate.source_analysis_ids.length > 0 && (
        <p className="mb-2 text-xs text-gray-500">
          Source analyses:{" "}
          {candidate.source_analysis_ids.map((aid, idx) => (
            <span key={aid}>
              {idx > 0 && ", "}
              <a
                href={`/analysis/${aid}`}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-blue-600 hover:underline"
              >
                {aid.slice(0, 8)}
              </a>
            </span>
          ))}
        </p>
      )}

      {candidate.trigger_tags.length > 0 && (
        <p className="mb-4 text-xs text-gray-500">
          Tags: {candidate.trigger_tags.join(", ")}
        </p>
      )}

      {actionError && (
        <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {actionError}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {mode === "view" && (
          <>
            <button
              type="button"
              onClick={() => handleApprove(false)}
              disabled={submitting}
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              type="button"
              onClick={() => setMode("edit")}
              disabled={submitting}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Edit
            </button>
            <button
              type="button"
              onClick={() => setMode("reject")}
              disabled={submitting}
              className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
            >
              Reject
            </button>
          </>
        )}
        {mode === "edit" && (
          <>
            <button
              type="button"
              onClick={() => handleApprove(true)}
              disabled={submitting || draft.trim().length === 0}
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              Approve edited
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("view");
                setDraft(candidate.content);
              }}
              disabled={submitting}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel edit
            </button>
          </>
        )}
        {mode === "reject" && (
          <>
            <button
              type="button"
              onClick={handleReject}
              disabled={submitting || rejectReason.trim().length === 0}
              className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              Confirm Reject
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("view");
                setRejectReason("");
              }}
              disabled={submitting}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          </>
        )}
      </div>
    </article>
  );
}

type Tone = "blue" | "gray" | "purple" | "amber" | "red" | "green";

function Badge({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  const toneClasses: Record<Tone, string> = {
    blue: "bg-blue-100 text-blue-800",
    gray: "bg-gray-100 text-gray-800",
    purple: "bg-purple-100 text-purple-800",
    amber: "bg-amber-100 text-amber-800",
    red: "bg-red-100 text-red-800",
    green: "bg-green-100 text-green-800",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}

function EvalScoreCard({ scores }: { scores: Record<string, number> }) {
  // FR-ADMN-12: deepeval scorecard shows faithfulness / correctness /
  // relevance / overall with color coding. Any dim not populated by
  // Phase 2 faithfulness-only eval is hidden rather than shown as "—".
  const dims: { key: string; label: string }[] = [
    { key: "overall", label: "Overall" },
    { key: "faithfulness", label: "Faithfulness" },
    { key: "correctness", label: "Correctness" },
    { key: "relevance", label: "Relevance" },
  ];
  function toneFor(score: number): string {
    if (score >= 0.85) return "text-green-700";
    if (score >= 0.6) return "text-amber-700";
    return "text-red-700";
  }
  return (
    <div className="rounded-md border border-gray-200 p-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Eval scores
      </p>
      <dl className="space-y-1 text-sm">
        {dims.map(({ key, label }) => {
          const score = scores[key];
          if (score === undefined) return null;
          return (
            <div key={key} className="flex justify-between">
              <dt className="text-gray-600">{label}</dt>
              <dd className={`font-mono ${toneFor(score)}`}>{score.toFixed(2)}</dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

function SimilarEntriesList({ candidateId }: { candidateId: string }) {
  const [items, setItems] = useState<SimilarEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getCoachBrainCandidateSimilar(candidateId, 2)
      .then((resp) => {
        if (!cancelled) setItems(resp.items);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  if (loading) {
    return (
      <p className="mb-2 text-xs text-gray-500">Loading similar entries...</p>
    );
  }
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="mb-3">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Similar existing entries
      </p>
      <ul className="space-y-2">
        {items.map((e) => (
          <li
            key={e.id}
            className="rounded-md border border-gray-200 bg-gray-50 p-2 text-xs text-gray-800"
          >
            <p className="mb-1 line-clamp-2">{e.content}</p>
            <p className="font-mono text-[10px] text-gray-500">
              {e.exercise}
              {e.phase ? ` • ${e.phase}` : ""} • {e.entry_type} • cosine{" "}
              {e.cosine_sim.toFixed(3)}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CoveCard({
  verified,
  explanation,
}: {
  verified: boolean | null;
  explanation: string | null;
}) {
  if (verified === true) {
    return (
      <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
        <p className="font-semibold">CoVe verified</p>
        {explanation && <p className="mt-1 text-xs">{explanation}</p>}
      </div>
    );
  }
  if (verified === false) {
    return (
      <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
        <p className="font-semibold">
          CoVe verification failed - review manually
        </p>
        {explanation && <p className="mt-1 text-xs">{explanation}</p>}
      </div>
    );
  }
  return (
    <div className="rounded-md border border-gray-200 p-3 text-sm text-gray-600">
      CoVe not run
    </div>
  );
}
