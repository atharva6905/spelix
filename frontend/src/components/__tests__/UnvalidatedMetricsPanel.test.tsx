/**
 * Unit tests for <UnvalidatedMetricsPanel /> (Session 3, L2-SAGITTAL-INFRA-04).
 *
 * The panel renders one row per applicable registry entry per rep. After
 * Session 3, ALL entries show "Not yet computed". Sessions 4-7 flip
 * `computed_yet=true` per metric; the panel then renders real values + a
 * Flag button.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

// Mock @/lib/supabase BEFORE any module-level imports that touch it. The
// real client calls createClient(VITE_SUPABASE_URL, ...) at import time,
// which fails in CI where those env vars are absent. Same pattern as the
// other component tests.
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi
        .fn()
        .mockResolvedValue({ data: { session: { access_token: "t" } } }),
    },
  },
}));

import UnvalidatedMetricsPanel from "@/components/UnvalidatedMetricsPanel";
import type {
  ExpertAnalysisDetail,
  SagittalMetricRegistryResponse,
} from "@/api/expert";
import * as expertApi from "@/api/expert";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const _makeRegistryResponse = (
  overrides: Partial<SagittalMetricRegistryResponse> = {},
): SagittalMetricRegistryResponse => ({
  entries: [
    {
      key_name: "depth_classification",
      display_label: "Depth Classification",
      unit: "",
      description: "Categorical relabel of squat depth.",
      exercise_applicability: ["squat"],
      computed_yet: false,
      in_scoring: false,
    },
    {
      key_name: "ankle_dorsiflexion_deg",
      display_label: "Ankle Dorsiflexion",
      unit: "deg",
      description: "Angle at the ankle at rep bottom.",
      exercise_applicability: ["squat"],
      computed_yet: false,
      in_scoring: false,
    },
    {
      key_name: "wrist_alignment_deg",
      display_label: "Wrist Alignment",
      unit: "deg",
      description: "Sagittal wrist stacking.",
      exercise_applicability: ["bench"],
      computed_yet: false,
      in_scoring: false,
    },
  ],
  ...overrides,
});

const _makeAnalysis = (
  overrides: Partial<ExpertAnalysisDetail> = {},
): ExpertAnalysisDetail => ({
  id: "11111111-1111-1111-1111-111111111111",
  exercise_type: "squat",
  exercise_variant: "high_bar",
  confidence_score: 0.87,
  form_score_safety: 7.5,
  form_score_technique: 7.0,
  form_score_path_balance: 7.5,
  form_score_control: 6.5,
  form_score_overall: 7.2,
  summary_json: { rep_count: 2 },
  quality_gate_result: null,
  coaching_result: null,
  rep_metrics: [{ rep_index: 1 }, { rep_index: 2 }],
  retrieval_context: null,
  eval_scores: null,
  flagged_for_review: false,
  is_golden_dataset: false,
  created_at: "2026-05-22T10:00:00Z",
  annotated_video_url: null,
  ...overrides,
});

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/api/expert", async () => {
  const actual = await vi.importActual<typeof expertApi>("@/api/expert");
  return {
    ...actual,
    getSagittalMetricsRegistry: vi.fn(),
    createThresholdFlag: vi.fn(),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UnvalidatedMetricsPanel", () => {
  it("renders the panel header and subhead with exact SaMD-compliant language", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue(
      _makeRegistryResponse(),
    );
    render(<UnvalidatedMetricsPanel analysis={_makeAnalysis()} />);
    expect(
      await screen.findByText(
        /Unvalidated Metrics \(computed, pending expert validation\)/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /These metrics are computed but NOT YET scored\. Validate against the video before flagging thresholds\./i,
      ),
    ).toBeInTheDocument();
  });

  it("does NOT use forbidden SaMD phrases in panel copy", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue(
      _makeRegistryResponse(),
    );
    const { container } = render(
      <UnvalidatedMetricsPanel analysis={_makeAnalysis()} />,
    );
    await waitFor(() =>
      expect(expertApi.getSagittalMetricsRegistry).toHaveBeenCalled(),
    );
    const text = container.textContent ?? "";
    expect(text.toLowerCase()).not.toContain("injury risk");
    expect(text.toLowerCase()).not.toContain("injury prevention");
    expect(text.toLowerCase()).not.toContain("safety score");
  });

  it("renders only entries applicable to the analysis exercise (squat -> 2 rows, not bench)", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue(
      _makeRegistryResponse(),
    );
    render(<UnvalidatedMetricsPanel analysis={_makeAnalysis()} />);
    expect(await screen.findByText("Depth Classification")).toBeInTheDocument();
    expect(screen.getByText("Ankle Dorsiflexion")).toBeInTheDocument();
    // wrist_alignment_deg is bench-only -- must NOT render for a squat.
    expect(screen.queryByText("Wrist Alignment")).not.toBeInTheDocument();
  });

  it("shows 'Not yet computed' badge for every row when no value exists in rep_metrics", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue(
      _makeRegistryResponse(),
    );
    render(<UnvalidatedMetricsPanel analysis={_makeAnalysis()} />);
    const badges = await screen.findAllByText(/Not yet computed/i);
    // 2 applicable squat metrics x 2 reps = 4 badges.
    expect(badges.length).toBe(4);
  });

  it("renders the computed value + unit when computed_yet=true AND rep_metrics has the key", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue({
      entries: [
        {
          key_name: "ankle_dorsiflexion_deg",
          display_label: "Ankle Dorsiflexion",
          unit: "deg",
          description: "Angle at the ankle at rep bottom.",
          exercise_applicability: ["squat"],
          computed_yet: true,
          in_scoring: false,
        },
      ],
    });
    const analysis = _makeAnalysis({
      rep_metrics: [
        { rep_index: 1, ankle_dorsiflexion_deg: 12.3 },
        { rep_index: 2, ankle_dorsiflexion_deg: 14.1 },
      ],
    });
    render(<UnvalidatedMetricsPanel analysis={analysis} />);
    expect(await screen.findByText("12.3 deg")).toBeInTheDocument();
    expect(screen.getByText("14.1 deg")).toBeInTheDocument();
  });

  it("renders Flag buttons for computed rows and opens ThresholdFlagModal on click", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue({
      entries: [
        {
          key_name: "ankle_dorsiflexion_deg",
          display_label: "Ankle Dorsiflexion",
          unit: "deg",
          description: "Angle at the ankle at rep bottom.",
          exercise_applicability: ["squat"],
          computed_yet: true,
          in_scoring: false,
        },
      ],
    });
    const analysis = _makeAnalysis({
      rep_metrics: [{ rep_index: 1, ankle_dorsiflexion_deg: 12.3 }],
    });
    render(<UnvalidatedMetricsPanel analysis={analysis} />);
    const flagBtn = await screen.findByRole("button", { name: /Flag/i });
    fireEvent.click(flagBtn);
    expect(await screen.findByText(/Flag threshold/i)).toBeInTheDocument();
  });

  it("renders values nested under rep.metrics_json (real API shape, regression for Session 4)", async () => {
    // Real ExpertAnalysisDetail.rep_metrics rows nest the JSONB column under
    // a `metrics_json` field; Session-3 fixtures put keys at the top level,
    // which silently passed because all entries had computed_yet=false.
    // Session 4 flipped flags and exposed the shape mismatch on prod.
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue({
      entries: [
        {
          key_name: "ecc_con_ratio",
          display_label: "Eccentric / Concentric Ratio",
          unit: "ratio",
          description: "Per-rep descent / ascent duration.",
          exercise_applicability: ["squat"],
          computed_yet: true,
          in_scoring: true,
        },
      ],
    });
    const analysis = _makeAnalysis({
      rep_metrics: [
        { rep_index: 1, metrics_json: { ecc_con_ratio: 1.55 } },
        { rep_index: 2, metrics_json: { ecc_con_ratio: 2.16 } },
      ],
    });
    render(<UnvalidatedMetricsPanel analysis={analysis} />);
    expect(await screen.findByText("1.6 ratio")).toBeInTheDocument();
    expect(screen.getByText("2.2 ratio")).toBeInTheDocument();
  });

  it("renders a graceful error state when the registry fetch fails", async () => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockRejectedValue(
      new Error("network error"),
    );
    render(<UnvalidatedMetricsPanel analysis={_makeAnalysis()} />);
    expect(
      await screen.findByText(/Unable to load sagittal metrics registry/i),
    ).toBeInTheDocument();
  });
});

describe("UnvalidatedMetricsPanel — R5 cannot-compute + confidence", () => {
  // registry: one computed_yet=true squat metric ("ecc_con_ratio") and one
  // computed_yet=false metric ("ankle_dorsiflexion_deg"). The computed_yet=true
  // entry's key is present-but-null in rep_metrics[0].metrics_json.
  beforeEach(() => {
    vi.mocked(expertApi.getSagittalMetricsRegistry).mockResolvedValue({
      entries: [
        {
          key_name: "ecc_con_ratio",
          display_label: "Eccentric / Concentric Ratio",
          unit: "ratio",
          description: "Per-rep descent / ascent duration.",
          exercise_applicability: ["squat"],
          computed_yet: true,
          in_scoring: true,
        },
        {
          key_name: "ankle_dorsiflexion_deg",
          display_label: "Ankle Dorsiflexion",
          unit: "deg",
          description: "Angle at the ankle at rep bottom.",
          exercise_applicability: ["squat"],
          computed_yet: false,
          in_scoring: false,
        },
      ],
    });
  });

  const analysis = _makeAnalysis({
    exercise_type: "squat",
    rep_metrics: [
      {
        rep_index: 1,
        metrics_json: { ecc_con_ratio: null }, // computed_yet=true but null this rep
        confidence_score: 0.41,               // → "Very Low"
        interpolation_fraction: 0.38,
      },
    ],
  });

  it("renders 'Cannot compute' (not 'Not yet computed') for a null value on a computed metric", async () => {
    render(<UnvalidatedMetricsPanel analysis={analysis} />);
    expect(await screen.findByText(/Cannot compute/i)).toBeInTheDocument();
  });

  it("shows the rep's confidence category as the reason", async () => {
    render(<UnvalidatedMetricsPanel analysis={analysis} />);
    // "Very Low" appears in the cell reason line (and also in the header chip)
    const matches = await screen.findAllByText(/Very Low/i);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it("shows the interpolation percentage when > 0", async () => {
    render(<UnvalidatedMetricsPanel analysis={analysis} />);
    expect(await screen.findByText(/38% interpolated/i)).toBeInTheDocument();
  });

  it("still renders 'Not yet computed' for a metric whose registry computed_yet=false", async () => {
    render(<UnvalidatedMetricsPanel analysis={analysis} />);
    expect(await screen.findByText(/Not yet computed/i)).toBeInTheDocument();
  });

  it("renders a per-rep confidence chip in the column header", async () => {
    render(<UnvalidatedMetricsPanel analysis={analysis} />);
    // header chip uses the same category helper → "Very Low" appears for the rep column
    const veryLow = await screen.findAllByText(/Very Low/i);
    expect(veryLow.length).toBeGreaterThanOrEqual(1);
  });

  it("does NOT show an interpolation line when the fraction is 0 (regression guard)", async () => {
    const zeroFrac = _makeAnalysis({
      exercise_type: "squat",
      rep_metrics: [
        {
          rep_index: 1,
          metrics_json: { ecc_con_ratio: null }, // computed_yet=true but null this rep
          confidence_score: 0.41,
          interpolation_fraction: 0.0, // nothing reconstructed (clean rep / bench)
        },
      ],
    });
    render(<UnvalidatedMetricsPanel analysis={zeroFrac} />);
    // Cannot-compute cell still renders (the rep mounted)…
    expect(await screen.findByText(/Cannot compute/i)).toBeInTheDocument();
    // …but the "% interpolated" line is suppressed by the `> 0` guard — never "0% interpolated".
    expect(screen.queryByText(/interpolated/i)).toBeNull();
  });
});
