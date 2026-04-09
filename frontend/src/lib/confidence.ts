/**
 * Shared confidence category helpers — SRS FR-SCOR-09, FR-SCOR-10, NFR-USAB-03
 *
 * Thresholds are authoritative here; do NOT redefine them in consuming files.
 * ≥0.80 → High | ≥0.65 → Moderate | ≥0.50 → Low | <0.50 → Very Low
 */

export type ConfidenceCategory = "High" | "Moderate" | "Low" | "Very Low";

export function getConfidenceCategory(score: number): ConfidenceCategory {
  if (score >= 0.80) return "High";
  if (score >= 0.65) return "Moderate";
  if (score >= 0.50) return "Low";
  return "Very Low";
}
