/**
 * ExpertPaperUploadPage — Research paper upload for RAG corpus.
 *
 * Requirements: FR-EXPV-01 (role check), FR-EXPV-05 (paper upload)
 *
 * - FR-EXPV-01: Only expert_reviewer or admin roles may access.
 * - FR-EXPV-05: Submit a research document with metadata to the RAG ingestion pipeline.
 *   Uses three-phase signed-URL flow (ADR-EXPERT-01):
 *   1. POST /api/v1/expert/papers → signed upload URL
 *   2. PUT {upload_url} — browser uploads PDF directly to storage
 *   3. POST /api/v1/expert/papers/{id}/complete — finalize + trigger ingestion
 */

import { useState, useEffect } from "react";
import { Link, Navigate } from "react-router";
import { supabase } from "@/lib/supabase";
import { FieldError } from "@/components/FieldError";
import {
  requestPaperUploadUrl,
  uploadPaperFile,
  completePaperUpload,
  SEX_APPLICABILITY_OPTIONS,
} from "@/api/expert";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_BYTES = 50 * 1024 * 1024;

const DOCUMENT_TYPE_OPTIONS = [
  { value: "research_paper", label: "Research Paper" },
  { value: "textbook", label: "Textbook" },
  { value: "clinical_guideline", label: "Clinical Guideline" },
  { value: "expert_annotation", label: "Expert Annotation" },
  { value: "other", label: "Other" },
] as const;

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
  document_type: string;
  doi: string;
  exercise_tags: string[];
  quality_tier: string;
  study_design: string;
  sex_applicability: string;
}

const INITIAL_FORM: FormState = {
  title: "",
  authors: "",
  year: "",
  document_type: "research_paper",
  doi: "",
  exercise_tags: [],
  quality_tier: "",
  study_design: "",
  sex_applicability: "both",
};

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ExpertPaperUploadPage() {
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);

  // File + upload phase state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadPhase, setUploadPhase] = useState<
    "idle" | "requesting" | "uploading" | "completing" | "success" | "error"
  >("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [doiError, setDoiError] = useState<string | null>(null);

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

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    setFileError(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    if (file.type !== "application/pdf") {
      setSelectedFile(null);
      setFileError("File must be a PDF");
      return;
    }
    if (file.size > MAX_BYTES) {
      setSelectedFile(null);
      setFileError("File is larger than 50 MB");
      return;
    }
    setSelectedFile(file);
  }

  // Single source of truth for clearing the three error states. Shared by BOTH
  // the submit-start path and resetForm() so neither can drift and forget an
  // error setter (e.g. setDoiError).
  function clearErrors() {
    setUploadError(null);
    setFileError(null);
    setDoiError(null);
  }

  // Returns the form to a clean idle state. Used by the "Upload Another" button.
  // Reuses clearErrors() for the error portion so error-clearing stays in sync
  // with the submit-start path.
  function resetForm() {
    clearErrors();
    setUploadPhase("idle");
    setSelectedFile(null);
    setUploadProgress(0);
    setForm(INITIAL_FORM);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFile) return;

    // Validate metadata before starting upload
    if (!form.title.trim()) {
      setUploadError("Title is required.");
      setUploadPhase("error");
      return;
    }

    // DOI required iff the document type is a research paper
    // (FR-EXPV-02, issue #234); optional for DOI-less document types.
    const doiRequired = form.document_type === "research_paper";
    if (doiRequired && !form.doi.trim()) {
      setDoiError("DOI is required.");
      return;
    }

    const authors = form.authors
      .split(",")
      .map((a) => a.trim())
      .filter(Boolean);

    const yearNum = form.year.trim() ? parseInt(form.year.trim(), 10) : undefined;
    if (
      form.year.trim() &&
      (isNaN(yearNum!) || yearNum! < 1900 || yearNum! > 2100)
    ) {
      setUploadError("Year must be a valid 4-digit year.");
      setUploadPhase("error");
      return;
    }

    setUploadPhase("requesting");
    clearErrors();
    setUploadProgress(0);

    // Track the in-flight phase locally — uploadPhase state is stale inside the
    // async closure, so we cannot read it in the catch handler.
    let failingPhase: "requesting" | "uploading" | "completing" = "requesting";

    try {
      const signed = await requestPaperUploadUrl({
        title: form.title.trim(),
        document_type: form.document_type as
          | "research_paper"
          | "textbook"
          | "clinical_guideline"
          | "expert_annotation"
          | "other",
        exercise_tags: form.exercise_tags,
        authors,
        year: yearNum,
        // Omit doi entirely when empty and the type allows it; a non-empty
        // DOI is always sent (and normalized/dedup'd by the backend).
        ...(form.doi.trim() ? { doi: form.doi.trim() } : {}),
        study_design: (form.study_design || undefined) as
          | "rct"
          | "observational"
          | "systematic_review"
          | "narrative_review"
          | "guideline"
          | "other"
          | undefined,
        quality_tier: (form.quality_tier || undefined) as
          | "L1_systematic_review"
          | "L2_rct"
          | "L3_observational"
          | "L4_guideline"
          | undefined,
        sex_applicability: form.sex_applicability as "male" | "female" | "both",
        filename: selectedFile.name,
        file_size_bytes: selectedFile.size,
      });

      failingPhase = "uploading";
      setUploadPhase("uploading");
      await uploadPaperFile(signed.upload_url, selectedFile, setUploadProgress);

      failingPhase = "completing";
      setUploadPhase("completing");
      await completePaperUpload(signed.id);

      setUploadPhase("success");
    } catch (err) {
      const apiErr = err as { status?: number; error?: { code?: string; message?: string } };
      if (
        (apiErr.status === 409 && apiErr.error?.code === "DUPLICATE_DOI") ||
        (apiErr.status === 422 && apiErr.error?.code === "INVALID_DOI")
      ) {
        setDoiError(apiErr.error?.message ?? "A paper with this DOI already exists.");
        setUploadPhase("idle");
        return;
      }
      let message =
        apiErr.error?.message ??
        (err instanceof Error ? err.message : "Upload failed");
      // Complete-step 409 = race close-out: the backend deleted the uploaded
      // object + row before raising (issue #218), so the fully-uploaded file is
      // gone and a resubmit re-uploads from scratch. Tell the user (SaMD-safe).
      if (apiErr.status === 409 && failingPhase === "completing") {
        message = `${message} Your uploaded file was discarded; submitting again will re-upload it.`;
      }
      setUploadError(message);
      setUploadPhase("error");
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

        <div className="rounded-lg bg-white p-6 shadow-sm">
          <form onSubmit={handleSubmit}>
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
                  disabled={uploadPhase !== "idle"}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:opacity-50"
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
                  disabled={uploadPhase !== "idle"}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:opacity-50"
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
                  disabled={uploadPhase !== "idle"}
                  className="w-36 rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:opacity-50"
                />
              </div>

              {/* Document type — DOI requirement depends on it (issue #234) */}
              <div>
                <label htmlFor="document_type" className="mb-1 block text-sm font-medium text-gray-700">
                  Document Type <span className="text-red-500">*</span>
                </label>
                <select
                  id="document_type"
                  value={form.document_type}
                  onChange={(e) => {
                    setDoiError(null);
                    setForm((f) => ({ ...f, document_type: e.target.value }));
                  }}
                  disabled={uploadPhase !== "idle"}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:opacity-50"
                >
                  {DOCUMENT_TYPE_OPTIONS.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>

              {/* DOI — required only for research papers (issue #234) */}
              <div>
                <label htmlFor="doi" className="mb-1 block text-sm font-medium text-gray-700">
                  DOI{" "}
                  {form.document_type === "research_paper" ? (
                    <span className="text-red-500">*</span>
                  ) : (
                    <span className="text-xs font-normal text-gray-400">(optional)</span>
                  )}
                </label>
                <input
                  id="doi"
                  type="text"
                  maxLength={200}
                  value={form.doi}
                  onChange={(e) => {
                    setDoiError(null);
                    setForm((f) => ({ ...f, doi: e.target.value }));
                  }}
                  placeholder="10.xxxx/xxxxx"
                  disabled={uploadPhase !== "idle"}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:opacity-50"
                />
                <FieldError className="mt-1">{doiError}</FieldError>
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
                        disabled={uploadPhase !== "idle"}
                        className="rounded text-indigo-600 disabled:opacity-50"
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
                  disabled={uploadPhase !== "idle"}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:opacity-50"
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
                  disabled={uploadPhase !== "idle"}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:opacity-50"
                >
                  <option value="">Select study design...</option>
                  {STUDY_DESIGN_OPTIONS.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>

              {/* Applicable population — FR-EXPV-05 ext. (issue #223) */}
              <div>
                <label htmlFor="sex_applicability" className="mb-1 block text-sm font-medium text-gray-700">
                  Applicable population <span className="text-red-500">*</span>
                </label>
                <select
                  id="sex_applicability"
                  value={form.sex_applicability}
                  onChange={(e) => setForm((f) => ({ ...f, sex_applicability: e.target.value }))}
                  disabled={uploadPhase !== "idle"}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 disabled:opacity-50"
                >
                  {SEX_APPLICABILITY_OPTIONS.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>

              {/* PDF file input */}
              <div>
                <label htmlFor="pdf-file" className="block text-sm font-medium mb-1">
                  PDF file
                </label>
                <input
                  id="pdf-file"
                  type="file"
                  accept="application/pdf"
                  onChange={handleFileChange}
                  disabled={uploadPhase !== "idle"}
                  aria-label="PDF file"
                />
                {selectedFile && (
                  <p className="text-sm text-muted-foreground mt-1">
                    {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                  </p>
                )}
                <FieldError className="mt-1">{fileError}</FieldError>
              </div>

              {/* Upload progress */}
              {uploadPhase === "uploading" && (
                <div>
                  <progress value={uploadProgress} max={100} />
                  <span className="ml-2 text-sm">{uploadProgress}%</span>
                </div>
              )}

              {/* Success banner */}
              {uploadPhase === "success" && (
                <div role="status" className="rounded-md bg-green-100 p-3 text-green-900">
                  {selectedFile?.name} uploaded and queued for review
                </div>
              )}

              {/* Error banner */}
              {uploadPhase === "error" && uploadError && (
                <div role="alert" className="rounded-md bg-red-100 p-3 text-red-900">
                  {uploadError}
                </div>
              )}

              {/* Submit / actions */}
              <div className="flex items-center gap-3 pt-2">
                {uploadPhase === "success" ? (
                  <>
                    <button
                      type="button"
                      onClick={resetForm}
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
                  </>
                ) : (
                  <>
                    <button
                      type="submit"
                      disabled={
                        !selectedFile ||
                        !form.title.trim() ||
                        (form.document_type === "research_paper" && !form.doi.trim()) ||
                        uploadPhase !== "idle"
                      }
                      className="rounded-md bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {uploadPhase === "requesting"
                        ? "Requesting upload URL..."
                        : uploadPhase === "uploading"
                          ? "Uploading..."
                          : uploadPhase === "completing"
                            ? "Finalizing..."
                            : "Upload Paper"}
                    </button>
                    <Link
                      to="/expert"
                      className="text-sm text-gray-500 hover:text-gray-700"
                    >
                      Cancel
                    </Link>
                  </>
                )}
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
