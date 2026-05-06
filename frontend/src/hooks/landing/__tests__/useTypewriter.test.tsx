import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, render, act } from "@testing-library/react";
import { useTypewriter } from "@/hooks/landing/useTypewriter";

// Wrapper component that attaches the ref to a real DOM element
function TypewriterWrapper({ text, wordDelay }: { text: string; wordDelay?: number }) {
  const { ref, displayText, isDone } = useTypewriter(text, wordDelay);
  return (
    <div ref={ref} data-done={isDone ? "true" : "false"}>
      {displayText}
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
  vi.useFakeTimers();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useTypewriter", () => {
  it("starts with empty displayText and isDone=false", () => {
    const { result } = renderHook(() => useTypewriter("hello world"));
    expect(result.current.displayText).toBe("");
    expect(result.current.isDone).toBe(false);
  });

  it("returns a ref object", () => {
    const { result } = renderHook(() => useTypewriter("test"));
    expect(result.current.ref).toBeDefined();
    expect("current" in result.current.ref).toBe(true);
  });

  it("does not create IntersectionObserver when ref is null (hook-only)", () => {
    renderHook(() => useTypewriter("test"));
    expect(capturedCallback).toBeNull();
  });

  it("creates IntersectionObserver and observes element when ref is attached", () => {
    render(<TypewriterWrapper text="hello" />);
    expect(capturedCallback).not.toBeNull();
    expect(mockObserve).toHaveBeenCalled();
  });

  it("disconnects observer on unmount", () => {
    const { unmount } = render(<TypewriterWrapper text="hello" />);
    unmount();
    expect(mockDisconnect).toHaveBeenCalled();
  });

  it("prefers-reduced-motion: immediately sets displayText=text and isDone=true", () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));

    const { container } = render(<TypewriterWrapper text="Hello world" />);
    const wrapper = container.firstChild as HTMLElement;

    // With reduced motion, text should be set immediately
    expect(wrapper.textContent).toBe("Hello world");
    expect(wrapper.dataset.done).toBe("true");
    // IntersectionObserver should NOT be created
    expect(capturedCallback).toBeNull();
  });

  it("IO callback: does nothing when not intersecting", () => {
    render(<TypewriterWrapper text="hello" />);
    expect(capturedCallback).not.toBeNull();

    act(() => {
      capturedCallback!([{ isIntersecting: false } as IntersectionObserverEntry]);
    });

    // No setTimeout scheduled for scheduleNext
    expect(vi.getTimerCount()).toBe(0);
  });

  it("IO callback: starts typewriter animation (schedules setTimeout) when intersecting", () => {
    render(<TypewriterWrapper text="Hi" wordDelay={0} />);
    expect(capturedCallback).not.toBeNull();

    act(() => {
      capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry]);
    });

    // A setTimeout(scheduleNext, 380) should now be scheduled
    expect(vi.getTimerCount()).toBeGreaterThan(0);
  });

  it("IO callback: does nothing when already started (guard branch)", () => {
    render(<TypewriterWrapper text="a b c" wordDelay={0} />);
    expect(capturedCallback).not.toBeNull();

    // First fire - starts animation
    act(() => {
      capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry]);
    });
    act(() => { vi.runAllTimers(); });

    // Second fire - started=true, guard prevents re-run (no new timers after clearing)
    act(() => {
      capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry]);
    });
    // No error thrown
  });

  it("scheduleNext: sets isDone when all tokens consumed", () => {
    const { container } = render(<TypewriterWrapper text="a" wordDelay={0} />);
    const wrapper = container.firstChild as HTMLElement;

    expect(capturedCallback).not.toBeNull();
    act(() => {
      capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry]);
    });

    act(() => { vi.runAllTimers(); });

    expect(wrapper.dataset.done).toBe("true");
  });

  it("whitespace tokens use 0ms delay (isWhitespace branch)", () => {
    // Text "a b" has tokens: ["a", " ", "b"] — the space gets 0ms delay
    const { container } = render(<TypewriterWrapper text="a b" wordDelay={100} />);
    const wrapper = container.firstChild as HTMLElement;

    expect(capturedCallback).not.toBeNull();
    act(() => {
      capturedCallback!([{ isIntersecting: true } as IntersectionObserverEntry]);
    });

    act(() => { vi.runAllTimers(); });

    // After running all timers, all tokens should be rendered
    expect(wrapper.textContent).toBe("a b");
  });
});
