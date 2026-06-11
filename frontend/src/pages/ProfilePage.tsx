/**
 * ProfilePage — onboarding and editable profile form.
 *
 * Requirements: FR-PROF-01 through FR-PROF-05
 *
 * - On first load: GET /api/v1/profiles/me to pre-populate if profile exists.
 * - On save: PUT /api/v1/profiles/me (upsert).
 * - Required fields: height, weight, age, experience level (FR-PROF-02).
 * - Optional fields: arm span, femur length (FR-PROF-03).
 * - Experience level descriptions shown inline (FR-PROF-04).
 */

import { useState, useEffect } from "react";
import { getProfile, updateProfile, type ProfileUpdateRequest, type Sex } from "@/api/profiles";

type ExperienceLevel = "beginner" | "intermediate" | "advanced";

const EXPERIENCE_OPTIONS: { value: ExperienceLevel; label: string; description: string }[] = [
  { value: "beginner", label: "Beginner", description: "Less than 1 year of training" },
  { value: "intermediate", label: "Intermediate", description: "1–3 years of training" },
  { value: "advanced", label: "Advanced", description: "More than 3 years of training" },
];

const SEX_OPTIONS: { value: Sex; label: string }[] = [
  { value: "prefer_not_to_say", label: "Prefer not to say" },
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
];

function isSex(value: string | null): value is Sex {
  return value === "male" || value === "female" || value === "prefer_not_to_say";
}

interface FormState {
  height_cm: string;
  weight_kg: string;
  age: string;
  experience_level: ExperienceLevel | "";
  arm_span_cm: string;
  femur_length_cm: string;
  sex: Sex;
}

const EMPTY_FORM: FormState = {
  height_cm: "",
  weight_kg: "",
  age: "",
  experience_level: "",
  arm_span_cm: "",
  femur_length_cm: "",
  sex: "prefer_not_to_say",
};

export default function ProfilePage() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    getProfile()
      .then((profile) => {
        setForm({
          height_cm: profile.height_cm != null ? String(profile.height_cm) : "",
          weight_kg: profile.weight_kg != null ? String(profile.weight_kg) : "",
          age: profile.age != null ? String(profile.age) : "",
          experience_level: (profile.experience_level as ExperienceLevel | null) ?? "",
          arm_span_cm: profile.arm_span_cm != null ? String(profile.arm_span_cm) : "",
          femur_length_cm: profile.femur_length_cm != null ? String(profile.femur_length_cm) : "",
          sex: isSex(profile.sex) ? profile.sex : "prefer_not_to_say",
        });
      })
      .catch((err) => {
        // 404 means no profile yet — that's expected on first login
        if (err?.status !== 404) {
          console.error("Failed to load profile", err);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  function handleChange(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setSuccessMessage(null);
    setErrorMessage(null);
  }

  async function handleSave() {
    setSuccessMessage(null);
    setErrorMessage(null);

    const heightNum = parseFloat(form.height_cm);
    const weightNum = parseFloat(form.weight_kg);
    const ageNum = parseInt(form.age, 10);

    if (!form.height_cm || isNaN(heightNum) || heightNum <= 0) {
      setErrorMessage("Please enter a valid height.");
      return;
    }
    if (!form.weight_kg || isNaN(weightNum) || weightNum <= 0) {
      setErrorMessage("Please enter a valid weight.");
      return;
    }
    if (!form.age || isNaN(ageNum) || ageNum <= 0) {
      setErrorMessage("Please enter a valid age.");
      return;
    }
    if (!form.experience_level) {
      setErrorMessage("Please select an experience level.");
      return;
    }

    const payload: ProfileUpdateRequest = {
      height_cm: heightNum,
      weight_kg: weightNum,
      age: ageNum,
      experience_level: form.experience_level,
      arm_span_cm: form.arm_span_cm ? parseFloat(form.arm_span_cm) : null,
      femur_length_cm: form.femur_length_cm ? parseFloat(form.femur_length_cm) : null,
      sex: form.sex,
    };

    setSaving(true);
    try {
      await updateProfile(payload);
      setSuccessMessage("Profile saved.");
    } catch (err) {
      console.error("Failed to save profile", err);
      setErrorMessage("Failed to save profile. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-sm text-gray-500">Loading profile...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen justify-center bg-gray-50 py-12">
      <div className="w-full max-w-lg rounded-lg bg-white p-8 shadow-sm">
        <h1 className="mb-2 text-2xl font-bold text-gray-900">Your Profile</h1>
        <p className="mb-8 text-sm text-gray-500">
          Body measurements improve coaching accuracy. All stats can be updated at any time.
        </p>

        <div className="space-y-6">
          {/* Required fields */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="height_cm" className="block text-sm font-medium text-gray-700">
                Height (cm)
              </label>
              <input
                id="height_cm"
                type="number"
                min="1"
                step="0.1"
                value={form.height_cm}
                onChange={(e) => handleChange("height_cm", e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="e.g. 175"
              />
            </div>

            <div>
              <label htmlFor="weight_kg" className="block text-sm font-medium text-gray-700">
                Weight (kg)
              </label>
              <input
                id="weight_kg"
                type="number"
                min="1"
                step="0.1"
                value={form.weight_kg}
                onChange={(e) => handleChange("weight_kg", e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="e.g. 75"
              />
            </div>
          </div>

          <div>
            <label htmlFor="age" className="block text-sm font-medium text-gray-700">
              Age (years)
            </label>
            <input
              id="age"
              type="number"
              min="1"
              step="1"
              value={form.age}
              onChange={(e) => handleChange("age", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="e.g. 28"
            />
          </div>

          <div>
            <label htmlFor="experience_level" className="block text-sm font-medium text-gray-700">
              Experience Level
            </label>
            <select
              id="experience_level"
              value={form.experience_level}
              onChange={(e) => handleChange("experience_level", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Select level...</option>
              {EXPERIENCE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label} — {opt.description}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="sex" className="block text-sm font-medium text-gray-700">
              Sex (optional)
            </label>
            <select
              id="sex"
              value={form.sex}
              onChange={(e) => handleChange("sex", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {SEX_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">Used to match coaching evidence to you.</p>
          </div>

          {/* Optional fields */}
          <div className="border-t border-gray-100 pt-4">
            <p className="mb-4 text-sm font-medium text-gray-500">
              Optional — improves limb-angle coaching accuracy
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="arm_span_cm" className="block text-sm font-medium text-gray-700">
                  Arm Span (cm)
                </label>
                <input
                  id="arm_span_cm"
                  type="number"
                  min="1"
                  step="0.1"
                  value={form.arm_span_cm}
                  onChange={(e) => handleChange("arm_span_cm", e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  placeholder="e.g. 178"
                />
              </div>

              <div>
                <label htmlFor="femur_length_cm" className="block text-sm font-medium text-gray-700">
                  Femur Length (cm)
                </label>
                <input
                  id="femur_length_cm"
                  type="number"
                  min="1"
                  step="0.1"
                  value={form.femur_length_cm}
                  onChange={(e) => handleChange("femur_length_cm", e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  placeholder="e.g. 45"
                />
              </div>
            </div>
          </div>

          {errorMessage && (
            <div className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
              {errorMessage}
            </div>
          )}

          {successMessage && (
            <div className="rounded-md bg-green-50 px-4 py-3 text-sm text-green-700">
              {successMessage}
            </div>
          )}

          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Profile"}
          </button>
        </div>
      </div>
    </div>
  );
}
