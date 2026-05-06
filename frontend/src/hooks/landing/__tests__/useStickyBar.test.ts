import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useRef } from "react";
import { useStickyBar } from "@/hooks/landing/useStickyBar";

const STORAGE_KEY = "spelix_sticky_dismissed";

beforeEach(() => {
  sessionStorage.clear();
  // Default scrollY = 0, innerHeight = 768
  vi.stubGlobal("scrollY", 0);
  vi.stubGlobal("innerHeight", 768);
});

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function renderStickyBar(finalEl: HTMLElement | null = null) {
  return renderHook(() => {
    const ref = useRef<HTMLElement | null>(finalEl);
    return useStickyBar(ref);
  });
}

describe("useStickyBar", () => {
  it("starts not visible by default (scrollY=0)", () => {
    const { result } = renderStickyBar();
    expect(result.current.isVisible).toBe(false);
  });

  it("starts dismissed when sessionStorage flag is set", () => {
    sessionStorage.setItem(STORAGE_KEY, "1");
    const { result } = renderStickyBar();
    expect(result.current.isVisible).toBe(false);
  });

  it("becomes visible when scrolled past innerHeight and final element is not visible", () => {
    vi.stubGlobal("scrollY", 900); // past innerHeight=768

    // Create a finalEl that is NOT in the viewport (rect.top > innerHeight - 80)
    const finalEl = document.createElement("div");
    vi.spyOn(finalEl, "getBoundingClientRect").mockReturnValue({
      top: 900,
      bottom: 920,
      left: 0,
      right: 100,
      width: 100,
      height: 20,
      x: 0,
      y: 900,
      toJSON: () => ({}),
    });

    const { result } = renderStickyBar(finalEl);

    // Fire scroll event to trigger onScroll
    act(() => {
      window.dispatchEvent(new Event("scroll"));
    });

    expect(result.current.isVisible).toBe(true);
  });

  it("hides when final element becomes visible", () => {
    vi.stubGlobal("scrollY", 900);

    const finalEl = document.createElement("div");
    // rect.top < innerHeight - 80 means final is visible → bar should hide
    vi.spyOn(finalEl, "getBoundingClientRect").mockReturnValue({
      top: 600,
      bottom: 620,
      left: 0,
      right: 100,
      width: 100,
      height: 20,
      x: 0,
      y: 600,
      toJSON: () => ({}),
    });

    const { result } = renderStickyBar(finalEl);

    act(() => {
      window.dispatchEvent(new Event("scroll"));
    });

    expect(result.current.isVisible).toBe(false);
  });

  it("dismiss sets isVisible to false and stores in sessionStorage", () => {
    vi.stubGlobal("scrollY", 900);

    const finalEl = document.createElement("div");
    vi.spyOn(finalEl, "getBoundingClientRect").mockReturnValue({
      top: 900,
      bottom: 920,
      left: 0,
      right: 100,
      width: 100,
      height: 20,
      x: 0,
      y: 900,
      toJSON: () => ({}),
    });

    const { result } = renderStickyBar(finalEl);

    act(() => {
      window.dispatchEvent(new Event("scroll"));
    });

    expect(result.current.isVisible).toBe(true);

    act(() => {
      result.current.dismiss();
    });

    expect(result.current.isVisible).toBe(false);
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe("1");
  });

  it("does not attach scroll listener when already dismissed", () => {
    sessionStorage.setItem(STORAGE_KEY, "1");
    const addSpy = vi.spyOn(window, "addEventListener");

    renderStickyBar();

    // No scroll listener should have been added (dismissed === true branch)
    const scrollListeners = addSpy.mock.calls.filter(([event]) => event === "scroll");
    expect(scrollListeners).toHaveLength(0);
  });

  it("removes scroll listener on unmount", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderStickyBar();
    unmount();
    // Should have removed the scroll listener
    const scrollRemovals = removeSpy.mock.calls.filter(([event]) => event === "scroll");
    expect(scrollRemovals.length).toBeGreaterThan(0);
  });

  it("handles no finalEl gracefully (finalEl is null)", () => {
    vi.stubGlobal("scrollY", 900);

    const { result } = renderStickyBar(null);

    act(() => {
      window.dispatchEvent(new Event("scroll"));
    });

    // When no finalRef.current, finalVisible = false, so isVisible = past && !false = past
    expect(result.current.isVisible).toBe(true);
  });

  it("dismiss handles sessionStorage unavailable gracefully", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("Storage unavailable");
    });

    const { result } = renderStickyBar();

    // Should not throw
    expect(() => {
      act(() => {
        result.current.dismiss();
      });
    }).not.toThrow();

    expect(result.current.isVisible).toBe(false);
  });

  it("initializes dismissed=false when sessionStorage throws on read", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("Storage unavailable");
    });

    const { result } = renderStickyBar();
    // Should default to not dismissed (false)
    expect(result.current.isVisible).toBe(false);
  });
});
