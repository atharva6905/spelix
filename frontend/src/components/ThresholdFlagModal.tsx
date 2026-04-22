import { useEffect, useState } from "react";

import type {
  ThresholdFlagCreate,
  ThresholdRow,
} from "@/api/expert";

interface Props {
  row: ThresholdRow | null;
  onClose: () => void;
  onSubmit: (payload: ThresholdFlagCreate) => Promise<void>;
}

const MIN_RATIONALE = 20;
const MIN_CITATION = 5;

export default function ThresholdFlagModal({ row, onClose, onSubmit }: Props) {
  const [proposedValue, setProposedValue] = useState<string>("");
  const [proposedCitation, setProposedCitation] = useState<string>("");
  const [rationale, setRationale] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setProposedValue("");
    setProposedCitation("");
    setRationale("");
    setError(null);
    setSubmitting(false);
  }, [row?.key]);

  if (!row) return null;

  const parsedValue = Number(proposedValue);
  const canSubmit =
    !Number.isNaN(parsedValue) &&
    proposedValue.trim().length > 0 &&
    proposedCitation.trim().length >= MIN_CITATION &&
    rationale.trim().length >= MIN_RATIONALE &&
    !submitting;

  async function handleSubmit() {
    if (!row) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        section: row.section,
        key: row.key,
        proposed_value: parsedValue,
        proposed_citation: proposedCitation.trim(),
        rationale: rationale.trim(),
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit flag");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Flag threshold
        </h2>

        <dl className="mb-4 text-sm text-gray-700">
          <div className="flex justify-between">
            <dt className="font-medium">Section</dt>
            <dd className="capitalize">{row.section}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Key</dt>
            <dd className="font-mono text-xs">{row.key}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Current value</dt>
            <dd>
              {row.value} {row.unit}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Current citation</dt>
            <dd className="text-right text-xs text-gray-500">
              {row.provenance_citation ?? "—"}
            </dd>
          </div>
        </dl>

        <label className="mb-3 block text-sm">
          <span className="mb-1 block font-medium text-gray-700">
            Proposed value ({row.unit})
          </span>
          <input
            type="number"
            step="any"
            value={proposedValue}
            onChange={(e) => setProposedValue(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>

        <label className="mb-3 block text-sm">
          <span className="mb-1 block font-medium text-gray-700">
            Proposed citation (≥ {MIN_CITATION} chars)
          </span>
          <input
            type="text"
            value={proposedCitation}
            onChange={(e) => setProposedCitation(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2"
            placeholder="Author year — finding"
          />
        </label>

        <label className="mb-3 block text-sm">
          <span className="mb-1 block font-medium text-gray-700">
            Rationale (≥ {MIN_RATIONALE} chars)
          </span>
          <textarea
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            rows={4}
            className="w-full rounded border border-gray-300 px-3 py-2"
            placeholder="Explain why the current value conflicts with literature."
          />
        </label>

        {error && (
          <p className="mb-3 text-sm text-red-600" role="alert">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!canSubmit}
            onClick={handleSubmit}
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            {submitting ? "Submitting…" : "Submit flag"}
          </button>
        </div>
      </div>
    </div>
  );
}
