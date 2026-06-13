/**
 * Upload page — exercise selection, filming guidance, and video file submission.
 * Requirements: FR-XDET-01, FR-XDET-02, FR-XDET-05, FR-XDET-08, FR-XDET-09,
 *               FR-UPLD-01 through FR-UPLD-12, NFR-USAB-01
 */

import { useState, useRef, type ChangeEvent } from "react";
import { useNavigate } from "react-router";
// NOTE: this file deliberately does NOT use tus-js-client. The backend
// generates a Supabase Storage REST signed upload URL
// (`/storage/v1/object/upload/sign/{bucket}/{path}?token=...`), which is a
// completely different protocol from Supabase's TUS resumable upload
// endpoint (`/storage/v1/upload/resumable`). Sending TUS protocol requests
// to the REST signed URL produces `400 headers must have required property
// 'authorization'` because Supabase's TUS endpoint requires an
// `Authorization` header that the REST signed URL endpoint does not. We
// use plain XHR PUT against the REST signed URL because XHR is the only
// browser API that exposes upload progress events (fetch does not). See
// the regression tests in __tests__/UploadPage.test.tsx for the contract.
import {
  createAnalysis,
  startAnalysis,
  type ExerciseType,
  type ExerciseVariant,
} from "@/api/analyses";
import { FieldError } from "@/components/FieldError";

// FR-XDET-01, FR-XDET-02: barbell exercises only, with allowed variants
const EXERCISE_VARIANTS: Record<ExerciseType, ExerciseVariant[]> = {
  squat: ["high_bar", "low_bar"],
  bench: ["flat", "incline", "decline"],
  deadlift: ["conventional", "sumo", "romanian"],
};

const EXERCISE_VARIANT_LABELS: Record<ExerciseVariant, string> = {
  high_bar: "High Bar",
  low_bar: "Low Bar",
  flat: "Flat",
  incline: "Incline",
  decline: "Decline",
  conventional: "Conventional",
  sumo: "Sumo",
  romanian: "Romanian",
};

// NFR-USAB-01: exercise-specific filming guidance for sagittal (side) view
// Phase 0: sagittal view only
const FILMING_GUIDANCE: Record<ExerciseType, string> = {
  squat:
    "For squat: Position your camera at hip height, 2–3 metres away. Film from the side so your full body is visible from head to feet. A sagittal (side) view is required — front and rear views cannot be analysed in Phase 0.",
  bench:
    "For bench press: Position your camera at bench height, 2–3 metres to your side. Ensure your full body and the bar path are visible from a side view. A sagittal (side) view is required — front and rear views cannot be analysed in Phase 0.",
  deadlift:
    "For deadlift: Position your camera at hip height, 2–3 metres to your side. Film from the side so the full lift — from setup to lockout — is visible. A sagittal (side) view is required — front and rear views cannot be analysed in Phase 0.",
};

const DEFAULT_GUIDANCE =
  "Position your camera at hip height, 2–3 metres away. Film from the side so your full body is visible from head to feet. A sagittal (side) view is required for analysis.";

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB

// D-035: duration thresholds — backend rejects beyond these limits
const MAX_DURATION_FREE_S = 60;
const MAX_DURATION_EXTENDED_S = 120;
const WARN_DURATION_S = 30;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Probes the duration of a video File via a temporary HTMLVideoElement.
 * Returns the duration in seconds, or 0 if metadata cannot be read
 * (corrupt/unsupported file — fail open so a corrupt file isn't hard-blocked).
 */
export async function probeVideoDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    const src = URL.createObjectURL(file);
    video.src = src;

    video.addEventListener("loadedmetadata", () => {
      const d = video.duration;
      URL.revokeObjectURL(src);
      resolve(isFinite(d) ? d : 0);
    });

    video.addEventListener("error", () => {
      URL.revokeObjectURL(src);
      resolve(0);
    });
  });
}

/**
 * Validates video duration from a File using a temporary HTMLVideoElement.
 * Returns an error message string, or null if valid.
 * Hard-blocks at >60s (free) / >120s (extended), and also rejects <2s clips.
 */
export async function validateDuration(
  file: File,
  extended: boolean,
): Promise<string | null> {
  const duration = await probeVideoDuration(file);

  // probeVideoDuration returns 0 for unreadable files — skip duration check
  if (duration === 0) return null;

  const cap = extended ? MAX_DURATION_EXTENDED_S : MAX_DURATION_FREE_S;

  if (duration < 2) {
    return "Video is too short (minimum ~2 seconds)";
  } else if (duration > cap) {
    return `This clip is ${duration.toFixed(1)}s, which exceeds the ${cap} second limit. Please trim it before uploading.`;
  }
  return null;
}

export default function UploadPage() {
  const navigate = useNavigate();

  const [exerciseType, setExerciseType] = useState<ExerciseType | "">("");
  const [exerciseVariant, setExerciseVariant] = useState<ExerciseVariant | "">(
    "",
  );
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileSizeError, setFileSizeError] = useState<string | null>(null);
  const [durationError, setDurationError] = useState<string | null>(null);
  const [durationWarning, setDurationWarning] = useState<string | null>(null);
  const [extendedDuration, setExtendedDuration] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Upload state — XHR PUT to Supabase REST signed upload URL.
  // Pause/resume is intentionally not supported (REST upload cannot resume
  // mid-byte; the button is "Cancel upload" while uploading). For
  // resumability we'd need to switch to Supabase's TUS endpoint with the
  // user's bearer JWT and storage RLS policies — deferred to a follow-up.
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const xhrRef = useRef<XMLHttpRequest | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // FR-XDET-09: upload button disabled until both exercise type AND variant are selected
  const selectionComplete = exerciseType !== "" && exerciseVariant !== "";

  // Full readiness also requires a valid file and no errors
  const isReadyToUpload =
    selectionComplete &&
    selectedFile !== null &&
    !fileSizeError &&
    !durationError;

  function handleExerciseTypeChange(e: ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value as ExerciseType | "";
    setExerciseType(value);
    setExerciseVariant(""); // reset variant when type changes (FR-XDET-09)
  }

  function handleExerciseVariantChange(e: ChangeEvent<HTMLSelectElement>) {
    setExerciseVariant(e.target.value as ExerciseVariant | "");
  }

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setFileSizeError(null);
    setDurationError(null);
    setDurationWarning(null);
    setSelectedFile(null);

    if (!file) return;

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setFileSizeError(
        `File is too large (${formatBytes(file.size)}). Maximum allowed size is 50 MB.`,
      );
      return;
    }

    // D-035: probe duration for immediate client-side feedback
    const d = await probeVideoDuration(file);

    if (d > 0) {
      // Hard-block above cap — mirrors backend ffprobe rejection
      const durErr = d < 2
        ? "Video is too short (minimum ~2 seconds)"
        : null;
      if (durErr) {
        setDurationError(durErr);
        return;
      }

      const cap = extendedDuration ? MAX_DURATION_EXTENDED_S : MAX_DURATION_FREE_S;
      if (d > cap) {
        setDurationError(
          `This clip is ${d.toFixed(1)}s, which exceeds the ${cap} second limit. Please trim it before uploading.`,
        );
        return;
      }

      // Soft warning: >30s but within cap
      if (d > WARN_DURATION_S) {
        setDurationWarning(
          "This clip is longer than 30 seconds. Analysis may take several minutes.",
        );
      }
    }

    setSelectedFile(file);
  }

  function handleCancelUpload() {
    const xhr = xhrRef.current;
    if (!xhr) return;
    xhr.abort();
    xhrRef.current = null;
    setSubmitError("Upload cancelled.");
    setSubmitting(false);
    setUploadProgress(null);
  }

  async function handleSubmit() {
    if (!isReadyToUpload || !exerciseType || !exerciseVariant || !selectedFile) {
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setUploadProgress(0);

    try {
      // Phase A: create analysis record, get upload_url
      const result = await createAnalysis({
        exercise_type: exerciseType,
        exercise_variant: exerciseVariant,
        filename: selectedFile.name,
        file_size_bytes: selectedFile.size,
      });

      // Phase B: REST PUT to Supabase Storage signed upload URL.
      // The signed URL is `/storage/v1/object/upload/sign/{bucket}/{path}?token=...`
      // — a one-shot HTTP PUT, not a TUS resumable upload. Auth lives in the
      // query-string `token`, NOT in an Authorization header. We use XHR
      // (not fetch) for the upload progress events.
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhrRef.current = xhr;

        xhr.upload.addEventListener("progress", (event) => {
          if (event.lengthComputable) {
            const pct = Math.round((event.loaded / event.total) * 100);
            setUploadProgress(pct);
          }
        });

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            setUploadProgress(100);
            resolve();
          } else {
            reject(
              new Error(
                `Upload failed (${xhr.status}). Please try again.`,
              ),
            );
          }
        };

        xhr.onerror = () => {
          reject(new Error("Network error during upload. Please try again."));
        };

        xhr.open("PUT", result.upload_url);
        xhr.setRequestHeader(
          "Content-Type",
          selectedFile.type || "application/octet-stream",
        );
        xhr.send(selectedFile);
      });

      // Phase C: trigger backend pipeline, then navigate
      xhrRef.current = null;
      await startAnalysis(result.id);
      navigate(`/analysis/${result.id}`);
    } catch (err: unknown) {
      const message =
        (err as { message?: string }).message ??
        "Upload failed. Please try again.";
      setSubmitError(message);
      setSubmitting(false);
      setUploadProgress(null);
      xhrRef.current = null;
    }
  }

  const currentVariants =
    exerciseType !== "" ? EXERCISE_VARIANTS[exerciseType] : [];
  const guidanceText =
    exerciseType !== "" ? FILMING_GUIDANCE[exerciseType] : DEFAULT_GUIDANCE;

  const isUploading = submitting && uploadProgress !== null;

  return (
    <div className="mx-auto max-w-xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">
        Upload Your Lift
      </h1>

      {/* Exercise Type — FR-XDET-01 */}
      <div className="mb-4">
        <label
          htmlFor="exercise-type"
          className="mb-1 block text-sm font-medium text-gray-700"
        >
          Exercise Type
        </label>
        <select
          id="exercise-type"
          value={exerciseType}
          onChange={handleExerciseTypeChange}
          className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="">Select exercise type</option>
          <option value="squat">Squat</option>
          <option value="bench">Bench Press</option>
          <option value="deadlift">Deadlift</option>
        </select>
      </div>

      {/* Exercise Variant — FR-XDET-02 */}
      <div className="mb-6">
        <label
          htmlFor="exercise-variant"
          className="mb-1 block text-sm font-medium text-gray-700"
        >
          Exercise Variant
        </label>
        <select
          id="exercise-variant"
          value={exerciseVariant}
          onChange={handleExerciseVariantChange}
          disabled={exerciseType === ""}
          className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:bg-gray-100"
        >
          <option value="">Select variant</option>
          {currentVariants.map((v) => (
            <option key={v} value={v}>
              {EXERCISE_VARIANT_LABELS[v]}
            </option>
          ))}
        </select>
      </div>

      {/* Filming Guidance — NFR-USAB-01, FR-XDET-08 */}
      <div className="mb-6 rounded-md border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
        <p className="font-semibold">Filming Guidance</p>
        <p className="mt-1">{guidanceText}</p>
      </div>

      {/* File Input */}
      <div className="mb-4">
        <label
          htmlFor="video-file"
          className="mb-1 block text-sm font-medium text-gray-700"
        >
          Video File
        </label>
        <input
          id="video-file"
          ref={fileInputRef}
          type="file"
          accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
          onChange={handleFileChange}
          className="block w-full text-sm text-gray-600 file:mr-4 file:rounded-md file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100"
        />
        {selectedFile && !fileSizeError && !durationError && (
          <p className="mt-1 text-xs text-gray-500">
            {selectedFile.name} — {formatBytes(selectedFile.size)}
          </p>
        )}
        <FieldError className="mt-1">{fileSizeError}</FieldError>
        <FieldError className="mt-1">{durationError}</FieldError>
        {durationWarning && (
          <p className="mt-1 text-xs text-amber-600" role="status">
            {durationWarning}
          </p>
        )}
      </div>

      {/* Extended Duration Toggle — B-050 */}
      <div className="mb-6 flex items-center gap-2">
        <input
          id="extended-duration"
          type="checkbox"
          checked={extendedDuration}
          onChange={(e) => setExtendedDuration(e.target.checked)}
          className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
        />
        <label
          htmlFor="extended-duration"
          className="text-sm text-gray-700"
        >
          Extended mode (up to 2 minutes — for longer sets)
        </label>
      </div>

      {/* Submit Error */}
      {submitError && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">
          {submitError}
        </div>
      )}

      {/* Upload Progress — B-044, FR-UPLD-12 */}
      {isUploading && (
        <div className="mb-4">
          <div className="mb-1 flex items-center justify-between text-xs text-gray-600">
            <span>{`Uploading… ${uploadProgress ?? 0}%`}</span>
            <span>{uploadProgress ?? 0}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-2 rounded-full bg-indigo-600 transition-all duration-300"
              style={{ width: `${uploadProgress ?? 0}%` }}
            />
          </div>
          {/* Cancel button — REST upload doesn't support resume mid-byte. */}
          <button
            type="button"
            onClick={handleCancelUpload}
            className="mt-2 text-sm font-medium text-indigo-600 hover:text-indigo-800 focus:outline-none focus:underline"
          >
            Cancel Upload
          </button>
        </div>
      )}

      {/* Upload Button — B-056: disabled attribute set when not ready so keyboard users cannot activate it */}
      <button
        type="button"
        aria-disabled={!selectionComplete ? "true" : "false"}
        onClick={!isReadyToUpload || submitting ? undefined : handleSubmit}
        disabled={!isReadyToUpload || submitting}
        className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-indigo-300"
      >
        {submitting ? "Uploading…" : "Upload Video"}
      </button>
    </div>
  );
}
