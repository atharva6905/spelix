import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useProgressRail } from "@/hooks/landing/useProgressRail";

let mockObserve: ReturnType<typeof vi.fn>;
let mockDisconnect: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mockObserve = vi.fn();
  mockDisconnect = vi.fn();

  vi.stubGlobal(
    "IntersectionObserver",
    vi.fn((cb: (entries: IntersectionObserverEntry[]) => void) => {
      void cb;
      return {
        observe: mockObserve,
        disconnect: mockDisconnect,
        unobserve: vi.fn(),
      };
    }),
  );

  vi.stubGlobal("scrollY", 0);
  vi.stubGlobal("innerHeight", 768);
  Object.defineProperty(document.documentElement, "scrollHeight", {
    configurable: true,
    value: 3000,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useProgressRail", () => {
  it("starts with fillPercent=0, empty sections, activeSection=null", () => {
    const { result } = renderHook(() => useProgressRail());
    expect(result.current.fillPercent).toBe(0);
    expect(result.current.sections).toEqual([]);
    expect(result.current.activeSection).toBeNull();
  });

  it("computes fillPercent based on scroll position", () => {
    const { result } = renderHook(() => useProgressRail());

    // scrollHeight=3000, innerHeight=768 → scrollH = 2232
    // scrollY = 1116 → pct = 1116/2232 * 100 = 50%
    vi.stubGlobal("scrollY", 1116);

    act(() => {
      window.dispatchEvent(new Event("scroll"));
    });

    expect(result.current.fillPercent).toBeCloseTo(50, 0);
  });

  it("sets fillPercent to 0 when scrollH <= 0", () => {
    Object.defineProperty(document.documentElement, "scrollHeight", {
      configurable: true,
      value: 768, // scrollH = 768 - 768 = 0
    });

    const { result } = renderHook(() => useProgressRail());

    act(() => {
      window.dispatchEvent(new Event("scroll"));
    });

    expect(result.current.fillPercent).toBe(0);
  });

  it("sets fillPercent to 100 at end of page", () => {
    // scrollH = 3000 - 768 = 2232, scrollY = 2232 → 100%
    vi.stubGlobal("scrollY", 2232);

    const { result } = renderHook(() => useProgressRail());

    act(() => {
      window.dispatchEvent(new Event("scroll"));
    });

    expect(result.current.fillPercent).toBeCloseTo(100, 0);
  });

  it("does not observe section elements when none exist in DOM", () => {
    renderHook(() => useProgressRail());
    // No [data-section] elements in jsdom → no intersection observer created
    expect(vi.mocked((globalThis as Record<string, unknown>).IntersectionObserver as (...args: unknown[]) => unknown)).not.toHaveBeenCalled();
  });

  it("removes scroll listener on unmount", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() => useProgressRail());
    unmount();

    const scrollRemovals = removeSpy.mock.calls.filter(([e]) => e === "scroll");
    expect(scrollRemovals.length).toBeGreaterThan(0);
  });

  it("removes resize listener on unmount", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() => useProgressRail());
    unmount();

    const resizeRemovals = removeSpy.mock.calls.filter(([e]) => e === "resize");
    expect(resizeRemovals.length).toBeGreaterThan(0);
  });

  it("returns sections as empty array when no data-section elements", () => {
    const { result } = renderHook(() => useProgressRail());
    expect(result.current.sections).toEqual([]);
  });

  it("creates IntersectionObserver and fires IO callback when data-section elements exist", () => {
    // Add a [data-section] element to the DOM
    const el = document.createElement("div");
    el.dataset.section = "hero";
    document.body.appendChild(el);

    const mockObserveForSection = vi.fn();
    const mockDisconnectForSection = vi.fn();
    let sectionCallback: ((entries: IntersectionObserverEntry[]) => void) | null = null;

    vi.stubGlobal(
      "IntersectionObserver",
      class MockIO {
        constructor(cb: (entries: IntersectionObserverEntry[]) => void) {
          sectionCallback = cb;
        }
        observe = mockObserveForSection;
        disconnect = mockDisconnectForSection;
        unobserve = vi.fn();
      },
    );

    const { result } = renderHook(() => useProgressRail());

    // IO should be created since [data-section] elements exist
    expect(sectionCallback).not.toBeNull();
    expect(mockObserveForSection).toHaveBeenCalledWith(el);

    // Fire the IO callback with isIntersecting=true → should set activeSection
    act(() => {
      sectionCallback!([{ isIntersecting: true, target: el } as unknown as IntersectionObserverEntry]);
    });

    expect(result.current.activeSection).toBe("hero");

    // Fire the IO callback with isIntersecting=false → should NOT change activeSection
    act(() => {
      sectionCallback!([{ isIntersecting: false, target: el } as unknown as IntersectionObserverEntry]);
    });

    // activeSection stays "hero" (not changed when not intersecting)
    expect(result.current.activeSection).toBe("hero");

    document.body.removeChild(el);
  });

  it("disconnects IntersectionObserver when data-section elements exist and hook unmounts", () => {
    const el = document.createElement("div");
    el.dataset.section = "features";
    document.body.appendChild(el);

    const mockDisconnectSection = vi.fn();

    vi.stubGlobal(
      "IntersectionObserver",
      class MockIO {
        constructor(_cb: (entries: IntersectionObserverEntry[]) => void) {}
        observe = vi.fn();
        disconnect = mockDisconnectSection;
        unobserve = vi.fn();
      },
    );

    const { unmount } = renderHook(() => useProgressRail());
    unmount();

    expect(mockDisconnectSection).toHaveBeenCalled();

    document.body.removeChild(el);
  });
});
