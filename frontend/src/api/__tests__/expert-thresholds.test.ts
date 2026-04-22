import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createThresholdFlag,
  getThresholdListing,
  listMyThresholdFlags,
} from "@/api/expert";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "tok" } },
      }),
    },
  },
}));

const makeFetchOk = (payload: unknown) =>
  vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve(payload),
  });

describe("threshold endpoints", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", makeFetchOk(null));
  });

  it("getThresholdListing fetches /expert/thresholds", async () => {
    const payload = {
      version: "v1",
      sections: { squat: [], bench: [], deadlift: [], control: [] },
    };
    vi.stubGlobal("fetch", makeFetchOk(payload));

    const listing = await getThresholdListing();

    expect(listing.version).toBe("v1");
    expect(Object.keys(listing.sections).sort()).toEqual([
      "bench",
      "control",
      "deadlift",
      "squat",
    ]);
  });

  it("createThresholdFlag posts the flag body", async () => {
    const flag = {
      id: "0000-0000-0000-0000",
      reviewer_id: "0000-0000-0000-0001",
      section: "squat",
      key: "knee_valgus_caution_deg",
      current_value: 5,
      current_citation: "Myer et al. 2010",
      proposed_value: 8,
      proposed_citation: "Krosshaug 2016",
      rationale: "An adequate-length rationale explaining the issue.",
      status: "open",
      resolution_note: null,
      resolved_by: null,
      resolved_at: null,
      created_at: "2026-04-21T00:00:00Z",
      updated_at: "2026-04-21T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: () => Promise.resolve(flag),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createThresholdFlag({
      section: "squat",
      key: "knee_valgus_caution_deg",
      proposed_value: 8,
      proposed_citation: "Krosshaug 2016",
      rationale: "An adequate-length rationale explaining the issue.",
    });

    expect(result.id).toBe(flag.id);
    const call = fetchMock.mock.calls[0]!;
    expect(call[0]).toContain("/api/v1/expert/thresholds/flags");
    expect((call[1] as RequestInit).method).toBe("POST");
  });

  it("listMyThresholdFlags passes limit/offset query", async () => {
    const fetchMock = makeFetchOk([]);
    vi.stubGlobal("fetch", fetchMock);

    await listMyThresholdFlags(25, 50);

    const url = fetchMock.mock.calls[0]![0] as string;
    expect(url).toContain("limit=25");
    expect(url).toContain("offset=50");
  });
});
