/**
 * ExpertPaperUploadPage — Research paper upload for RAG corpus.
 *
 * Requirements: FR-EXPV-01 (role check), FR-EXPV-05 (paper upload)
 *
 * - FR-EXPV-01: Only expert_reviewer or admin roles may access.
 * - FR-EXPV-05: Submit a research document with metadata to the RAG ingestion pipeline.
 */

import { useState, useEffect } from "react";
import { Link, Navigate } from "react-router";
import { supabase } from "@/lib/supabase";
import { uploadPaper, type RagDocumentResponse } from "@/api/expert";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EXERCISE_TAG_OPTIONS = [
  { value: "squat", label: "Squat" },
  { value: "bench", label: "Bench Press" },
  { value: "deadlift", label: "Deadlift" },
] as const;

const QUALITY_TIER_OPTIONS = [
  { value: "L1_systematic_review", label: "L1 — Systematic Review / Meta-Analysis" },
  { value: "L2_rct", label: "L2 — Randomized Controlled Trial" },
  { value: "L3_observational", label: "L3 — Observational Study" },
  { value: "L4_guideline", label: "L4 — Clinical Guideline / Expert Consensus" },
] as const;

const STUDY_DESIGN_OPTIONS = [
  { value: "rct", label: "Randomized Controlled Trial (RCT)" },
  { value: "observational", label: "Observational" },
  { value: "systematic_review", label: "Systematic Review / Meta-Analysis" },
  { value: "narrative_review", label: "Narrative Review" },
  { value: "guideline", label: "Guideline / Consensus Statement" },
  { value: "other", label: "Other" },
] as const;

// ---------------------------------------------------------------------------
// Form state
// ---------------------------------------------------------------------------

interface FormState {
  title: string;
  authors: string;
  year: string;
  doi: string;
  exercise_tags: string[];
  quality_tier: string;
  study_design: string;
}

const INITIAL_FORM: FormState = {
  title: "",
  authors: "",
  year: "",
  doi: "",
  exercise_tags: [],
  quality_tier: "",
  study_design: "",
};

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ExpertPaperUploadPage() {
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [uploadedDoc, setUploadedDoc] = useState<RagDocumentResponse | null>(null);

  // Role check — FR-EXPV-01
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const session = data.session;
      if (!session) {
        setIsAuthorized(false);
        return;
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const payload = session.user as any;
      const role =
        payload?.app_metadata?.role ?? payload?.user_metadata?.role ?? null;
      setIsAuthorized(role === "expert_reviewer" || role === "admin");
    });
  }, []);

  function toggleExerciseTag(tag: string) {
    setForm((f) => ({
      ...f,
      exercise_tags: f.exercise_tags.includes(tag)
        ? f.exercise_tags.filter((t) => t !== tag)
        : [...f.exercise_tags, tag],
    }));
  }

  async function handleSubmit() {
    setSubmitError(null);

    if (!form.title.trim()) {
      setSubmitError("Title is required.");
      return;
    }

    const authors = form.authors
      .split(",")
      .map((a) => a.trim())
      .filter(Boolean);

    const yearNum = form.year.trim() ? parseInt(form.year.trim(), 10) : null;
    if (form.year.trim() && (isNaN(yearNum!) || yearNum! < 1900 || yearNum! > 2100)) {
      setSubmitError("Year must be a valid 4-digit year.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await uploadPaper({
        title: form.title.trim(),
        authors,
        year: yearNum,
        doi: form.doi.trim() || null,
        exercise_tags: form.exercise_tags,
        quality_tier: form.quality_tier || null,
        study_design: form.study_design || null,
        document_type: "research_paper",
      });
      setUploadedDoc(result);
    } catch (err) {
      console.error("Failed to upload paper", err);
      setSubmitError("Failed to upload paper. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (isAuthorized === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-500">Checking permissions...</p>
      </div>
    );
  }

  if (!isAuthorized) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <h1 className="mb-2 text-2xl font-bold text-gray-900">Access Denied</h1>
          <p className="mb-4 text-sm text-gray-500">
            You do not have permission to view this page.
          </p>
          <Navigate to="/" replace />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-10">
      <div className="mx-auto max-w-2xl px-4 sm:px-6 lg:px-8">
        {/* Back link */}
        <div className="mb-6">
          <Link to="/expert" className="text-sm text-indigo-600 hover:underline">
            &larr; Back to Expert Portal
          </Link>
        </div>

        <h1 className="mb-8 text-3xl font-bold text-gray-900">Upload Research Paper</h1>

        {/* Success state */}
        {uploadedDoc ? (
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <div className="mb-4 rounded-md bg-green-50 p-4">
              <h2 className="mb-1 text-base font-semibold text-green-800">
                Paper uploaded successfully
              </h2>
              <p className="text-sm text-green-700">
                Document ID:{" "}
                <span className="font-mono">{uploadedDoc.id}</span>
              </p>
              <p className="mt-1 text-sm text-green-700">
                Status:{" "}
                <span className="font-medium capitalize">{uploadedDoc.review_status}</span>
              </p>
            </div>

            <dl className="mb-6 space-y-2 text-sm text-gray-700">
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Title</dt>
                <dd>{uploadedDoc.title}</dd>
              </div>
              {uploadedDoc.authors.length > 0 && (
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Authors</dt>
                  <dd>{uploadedDoc.authors.join(", ")}</dd>
                </div>
              )}
              {uploadedDoc.year && (
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Year</dt>
                  <dd>{uploadedDoc.year}</dd>
                </div>
              )}
              {uploadedDoc.doi && (
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">DOI</dt>
                  <dd className="font-mono text-xs">{uploadedDoc.doi}</dd>
                </div>
              )}
              {uploadedDoc.exercise_tags.length > 0 && (
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Exercise Tags</dt>
                  <dd className="flex flex-wrap gap-1">
                    {uploadedDoc.exercise_tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 capitalize"
                      >
                        {tag}
                      </span>
                    ))}
                  </dd>
                </div>
              )}
            </dl>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => {
                  setUploadedDoc(null);
                  setForm(INITIAL_FORM);
                }}
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
              >
                Upload Another
              </button>
              <Link
                to="/expert"
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Back to Portal
              </Link>
            </div>
          </div>
        ) : (
          /* Upload form */
          <div className="rounded-lg bg-white p-6 shadow-sm">
            {submitError && (
              <div className="mb-5 rounded-md bg-red-50 p-3 text-sm text-red-600">
                {submitError}
              </div>
            )}

            <div className="space-y-5">
              {/* Title */}
              <div>
                <label htmlFor="title" className="mb-1 block text-sm font-medium text-gray-700">
                  Title <span className="text-red-500">*</span>
                </label>
                <input
                  id="title"
                  type="text"
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="Full paper title"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                />
              </div>

              {/* Authors */}
              <div>
                <label htmlFor="authors" className="mb-1 block text-sm font-medium text-gray-700">
                  Authors
                </label>
                <input
                  id="authors"
                  type="text"
                  value={form.authors}
                  onChange={(e) => setForm((f) => ({ ...f, authors: e.target.value }))}
                  placeholder="Comma-separated, e.g. Smith J, Jones A"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                />
                <p className="mt-0.5 text-xs text-gray-400">Separate multiple authors with commas.</p>
              </div>

              {/* Year */}
              <div>
                <label htmlFor="year" className="mb-1 block text-sm font-medium text-gray-700">
                  Year
                </label>
                <input
                  id="year"
                  type="number"
                  min={1900}
                  max={2100}
                  value={form.year}
                  onChange={(e) => setForm((f) => ({ ...f, year: e.target.value }))}
                  placeholder="e.g. 2023"
                  className="w-36 rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                />
              </div>

              {/* DOI */}
              <div>
                <label htmlFor="doi" className="mb-1 block text-sm font-medium text-gray-700">
                  DOI
                </label>
                <input
                  id="doi"
                  type="text"
                  value={form.doi}
                  onChange={(e) => setForm((f) => ({ ...f, doi: e.target.value }))}
                  placeholder="10.xxxx/xxxxx"
                  className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                />
              </div>

              {/* Exercise tags */}
              <fieldset>
                <legend className="mb-2 text-sm font-medium text-gray-700">Exercise Tags</legend>
                <div className="flex flex-wrap gap-4">
                  {EXERCISE_TAG_OPTIONS.map(({ value, label }) => (
                    <label key={value} className="flex items-center gap-1.5 text-sm text-gray-600">
                      <input
                        type="checkbox"
                        checked={form.exercise_tags.includes(value)}
                        onChange={() => toggleExerciseTag(value)}
                        className="rounded text-indigo-600"
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </fieldset>

              {/* Quality tier */}
              <div>
                <label htmlFor="quality_tier" className="mb-1 block text-sm font-medium text-gray-700">
                  Quality Tier
                </label>
                <select
                  id="quality_tier"
                  value={form.quality_tier}
                  onChange={(e) => setForm((f) => ({ ...f, quality_tier: e.target.value }))}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                >
                  <option value="">Select quality tier...</option>
                  {QUALITY_TIER_OPTIONS.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>

              {/* Study design */}
              <div>
                <label htmlFor="study_design" className="mb-1 block text-sm font-medium text-gray-700">
                  Study Design
                </label>
                <select
                  id="study_design"
                  value={form.study_design}
                  onChange={(e) => setForm((f) => ({ ...f, study_design: e.target.value }))}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                >
                  <option value="">Select study design...</option>
                  {STUDY_DESIGN_OPTIONS.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>

              {/* Document type is always research_paper — no user input needed */}

              <div className="flex items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="rounded-md bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {submitting ? "Uploading..." : "Upload Paper"}
                </button>
                <Link
                  to="/expert"
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  Cancel
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
