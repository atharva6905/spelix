/**
 * Upload page — exercise selection, filming guidance, and video file submission.
 * Requirements: FR-XDET-01, FR-XDET-02, FR-XDET-05, FR-XDET-08, FR-XDET-09,
 *               FR-UPLD-01 through FR-UPLD-09, NFR-USAB-01
 */

import { useState, useRef, type ChangeEvent } from "react";
import { useNavigate } from "react-router";
import {
  createAnalysis,
  type ExerciseType,
  type ExerciseVariant,
} from "@/api/analyses";

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

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadPage() {
  const navigate = useNavigate();

  const [exerciseType, setExerciseType] = useState<ExerciseType | "">("");
  const [exerciseVariant, setExerciseVariant] = useState<ExerciseVariant | "">(
    "",
  );
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileSizeError, setFileSizeError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // FR-XDET-09: upload button aria-disabled until both exercise type AND variant are selected
  const selectionComplete = exerciseType !== "" && exerciseVariant !== "";

  // Full readiness also requires a valid file for actual submission
  const isReadyToUpload = selectionComplete && selectedFile !== null && !fileSizeError;

  const uploadDisabled = !selectionComplete;

  function handleExerciseTypeChange(e: ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value as ExerciseType | "";
    setExerciseType(value);
    setExerciseVariant(""); // reset variant when type changes (FR-XDET-09)
  }

  function handleExerciseVariantChange(e: ChangeEvent<HTMLSelectElement>) {
    setExerciseVariant(e.target.value as ExerciseVariant | "");
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setFileSizeError(null);
    if (file) {
      if (file.size > MAX_FILE_SIZE_BYTES) {
        setFileSizeError(
          `File is too large (${formatBytes(file.size)}). Maximum allowed size is 50 MB.`,
        );
        setSelectedFile(null);
      } else {
        setSelectedFile(file);
      }
    } else {
      setSelectedFile(null);
    }
  }

  async function handleSubmit() {
    if (!isReadyToUpload || !exerciseType || !exerciseVariant || !selectedFile) {
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      const result = await createAnalysis({
        exercise_type: exerciseType,
        exercise_variant: exerciseVariant,
        filename: selectedFile.name,
        file_size_bytes: selectedFile.size,
      });

      // Navigate to the analysis status page (FR-UPLD-08, FR-UPLD-09)
      navigate(`/analysis/${result.id}`);
    } catch (err: unknown) {
      const message =
        (err as { message?: string }).message ??
        "Upload failed. Please try again.";
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  }

  const currentVariants =
    exerciseType !== "" ? EXERCISE_VARIANTS[exerciseType] : [];
  const guidanceText =
    exerciseType !== "" ? FILMING_GUIDANCE[exerciseType] : DEFAULT_GUIDANCE;

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
      <div className="mb-6">
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
        {selectedFile && !fileSizeError && (
          <p className="mt-1 text-xs text-gray-500">
            {selectedFile.name} — {formatBytes(selectedFile.size)}
          </p>
        )}
        {fileSizeError && (
          <p className="mt-1 text-xs text-red-600">{fileSizeError}</p>
        )}
      </div>

      {/* Submit Error */}
      {submitError && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {submitError}
        </div>
      )}

      {/* Upload Button — FR-XDET-09: aria-disabled until both type + variant selected */}
      <button
        type="button"
        aria-disabled={uploadDisabled ? "true" : "false"}
        onClick={uploadDisabled ? undefined : handleSubmit}
        disabled={submitting}
        className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 aria-[disabled=true]:cursor-not-allowed aria-[disabled=true]:bg-indigo-300"
      >
        {submitting ? "Uploading…" : "Upload Video"}
      </button>
    </div>
  );
}
