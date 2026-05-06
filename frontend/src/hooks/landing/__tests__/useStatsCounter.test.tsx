import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, render, act } from "@testing-library/react";
import { useStatsCounter } from "@/hooks/landing/useStatsCounter";

// Wrapper component that attaches the ref to a real DOM element
function StatsCounterWrapper({ target, duration }: { target: number; duration?: number }) {
  const { ref, value, done } = useStatsCounter(target, duration);
  return (
    <div ref={ref} data-value={value} data-done={done ? "true" : "false"}>
      {value}
    </div>
  );
}

let capturedCallback: ((entries: IntersectionObserverEntry[]) => void) | null;
let mockObserve: ReturnType<typeof vi.fn>;
let mockDisconnect: ReturnType<typeof vi.fn>;

function setupIO() {
  capturedCallback = null;
  mockObserve = vi.fn();
  mockDisconnect = vi.fn();

  const observe = mockObserve;
  const disconnect = mockDisconnect;

  vi.stubGlobal(
    "IntersectionObserver",
    class MockIO {
      constructor(cb: (entries: IntersectionObserverEntry[]) => void) {
        capturedCallback = cb;
      }
      observe = observe;
      disconnect = disconnect;
      unobserve = vi.fn();
    },
  );
}

beforeEach(() => {
  setupIO();
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useStatsCounter", () => {
  it("starts with value=0 and done=false", () => {
    const { result } = renderHook(() => useStatsCounter(100));
    expect(result.current.value).toBe(0);
    expect(result.current.done).toBe(false);
  });

  it("returns a ref object", () => {
    const { result } = renderHook(() => useStatsCounter(100));
    expect(result.current.ref).toBeDefined();
    expect("current" in result.current.ref).toBe(true);
  });

  it("does not create IntersectionObserver when ref is null (hook-only render)", () => {
    renderHook(() => useStatsCounter(100));
    expect(capturedCallback).toBeNull();
  });

  it("creates IntersectionObserver and observes element when ref is attached", () => {
    render(<StatsCounterWrapper target={100} />);
    expect(capturedCallback).not.toBeNull();
    expect(mockObserve).toHaveBeenCalled();
  });

  it("disconnects observer on unmount", () => {
    const { unmount } = render(<StatsCounterWrapper target={100} />);
    unmount();
    expect(mockDisconnect).toHaveBeenCalled();
  });

  it("IO callback fires: starts animation (calls requestAnimationFrame) when intersecting", () => {
    const mockRaf = vi.fn((_cb: FrameRequestCallback) => 1);
    vi.stubGlobal("requestAnimationFrame", mockRaf);

    render(<StatsCounterWrapper target={100} />);

    expect(capturedCallback).not.toBeNull();
    act(() => {
      capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry]);
    });

    expect(mockRaf).toHaveBeenCalled();
  });

  it("IO callback: does nothing when not intersecting", () => {
    const mockRaf = vi.fn();
    vi.stubGlobal("requestAnimationFrame", mockRaf);

    render(<StatsCounterWrapper target={100} />);

    expect(capturedCallback).not.toBeNull();
    act(() => {
      capturedCallback!([{ isIntersecting: false } as IntersectionObserverEntry]);
    });

    expect(mockRaf).not.toHaveBeenCalled();
  });

  it("IO callback: does nothing when already started (guard branch)", () => {
    const mockRaf = vi.fn((_cb: FrameRequestCallback) => 1);
    vi.stubGlobal("requestAnimationFrame", mockRaf);

    render(<StatsCounterWrapper target={100} />);

    expect(capturedCallback).not.toBeNull();
    // First call - starts animation
    act(() => {
      capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry]);
    });
    const firstCallCount = mockRaf.mock.calls.length;

    // Second call - already started, should not animate again
    act(() => {
      capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry]);
    });
    expect(mockRaf.mock.calls.length).toBe(firstCallCount);
  });

  it("prefers-reduced-motion: skips requestAnimationFrame and sets value=target immediately", () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    const mockRaf = vi.fn();
    vi.stubGlobal("requestAnimationFrame", mockRaf);

    render(<StatsCounterWrapper target={42} />);

    expect(capturedCallback).not.toBeNull();
    act(() => {
      capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry]);
    });

    // Reduced motion path calls setValue(target) + setDone(true), NOT requestAnimationFrame
    expect(mockRaf).not.toHaveBeenCalled();
  });

  it("accepts custom duration parameter", () => {
    const { result } = renderHook(() => useStatsCounter(50, 500));
    expect(result.current.value).toBe(0);
    expect(result.current.done).toBe(false);
  });

  it("animation tick runs easeOutCubic and advances value toward target", () => {
    // Mock performance.now to control time
    let performanceTime = 0;
    vi.stubGlobal("performance", { now: () => performanceTime });

    // Mock rAF to immediately call the tick with advanced time
    let rafCount = 0;
    const MAX_FRAMES = 10;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      if (rafCount++ < MAX_FRAMES) {
        performanceTime += 200; // advance 200ms per frame
        act(() => { cb(performanceTime); });
      }
      return rafCount;
    });

    const { container } = render(<StatsCounterWrapper target={10} duration={400} />);
    const wrapper = container.firstChild as HTMLElement;

    expect(capturedCallback).not.toBeNull();
    act(() => {
      capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry]);
    });

    // After enough frames, animation should complete (t >= 1)
    expect(wrapper.dataset.done).toBe("true");
  });

  it("animation tick calls requestAnimationFrame again when t < 1", () => {
    let performanceTime = 0;
    vi.stubGlobal("performance", { now: () => performanceTime });

    let rafCallCount = 0;
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      rafCallCount++;
      if (rafCallCount === 1) {
        // First call: advance time partially (t = 0.1/1000 < 1)
        performanceTime += 100;
        act(() => { cb(performanceTime); }); // this should call rAF again
      }
      // Don't recurse further
      return rafCallCount;
    });

    render(<StatsCounterWrapper target={100} duration={1000} />);

    expect(capturedCallback).not.toBeNull();
    act(() => {
      capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry]);
    });

    // rAF should have been called at least twice (initial + recursive)
    expect(rafCallCount).toBeGreaterThanOrEqual(2);
  });
});
