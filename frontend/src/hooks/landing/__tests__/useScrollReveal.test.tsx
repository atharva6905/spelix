import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, render, act } from "@testing-library/react";
import { useScrollReveal } from "@/hooks/landing/useScrollReveal";

// A wrapper component that attaches the ref from useScrollReveal to a real DOM element
function ScrollRevealWrapper({ threshold }: { threshold?: number }) {
  const ref = useScrollReveal(threshold);
  return <div ref={ref} className="landing-reveal"><span>child</span></div>;
}

let capturedCallback: ((entries: IntersectionObserverEntry[], obs: IntersectionObserver) => void) | null;
let mockObserve: ReturnType<typeof vi.fn>;
let mockUnobserve: ReturnType<typeof vi.fn>;
let mockDisconnect: ReturnType<typeof vi.fn>;

function setupIO() {
  capturedCallback = null;
  mockObserve = vi.fn();
  mockUnobserve = vi.fn();
  mockDisconnect = vi.fn();

  const observe = mockObserve;
  const unobserve = mockUnobserve;
  const disconnect = mockDisconnect;

  vi.stubGlobal(
    "IntersectionObserver",
    class MockIO {
      constructor(cb: (entries: IntersectionObserverEntry[], obs: IntersectionObserver) => void) {
        capturedCallback = cb;
      }
      observe = observe;
      unobserve = unobserve;
      disconnect = disconnect;
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

describe("useScrollReveal", () => {
  it("returns a ref object when used directly", () => {
    const { result } = renderHook(() => useScrollReveal());
    expect(result.current).toBeDefined();
    expect("current" in result.current).toBe(true);
  });

  it("does not observe when ref is not attached (null)", () => {
    renderHook(() => useScrollReveal());
    expect(mockObserve).not.toHaveBeenCalled();
  });

  it("creates IntersectionObserver and observes element when ref is attached", () => {
    render(<ScrollRevealWrapper />);
    expect(capturedCallback).not.toBeNull();
    expect(mockObserve).toHaveBeenCalled();
  });

  it("passes threshold option to IntersectionObserver", () => {
    const IoSpy = vi.fn().mockImplementation(function (
      this: { observe: typeof mockObserve; unobserve: typeof mockUnobserve; disconnect: typeof mockDisconnect },
      cb: (entries: IntersectionObserverEntry[], obs: IntersectionObserver) => void,
    ) {
      capturedCallback = cb;
      this.observe = mockObserve;
      this.unobserve = mockUnobserve;
      this.disconnect = mockDisconnect;
    });
    vi.stubGlobal("IntersectionObserver", IoSpy);

    render(<ScrollRevealWrapper threshold={0.5} />);
    expect(IoSpy).toHaveBeenCalledWith(
      expect.any(Function),
      expect.objectContaining({ threshold: 0.5 }),
    );
  });

  it("uses default threshold of 0.12 when not provided", () => {
    const IoSpy = vi.fn().mockImplementation(function (
      this: { observe: typeof mockObserve; unobserve: typeof mockUnobserve; disconnect: typeof mockDisconnect },
      cb: (entries: IntersectionObserverEntry[], obs: IntersectionObserver) => void,
    ) {
      capturedCallback = cb;
      this.observe = mockObserve;
      this.unobserve = mockUnobserve;
      this.disconnect = mockDisconnect;
    });
    vi.stubGlobal("IntersectionObserver", IoSpy);

    render(<ScrollRevealWrapper />);
    expect(IoSpy).toHaveBeenCalledWith(
      expect.any(Function),
      expect.objectContaining({ threshold: 0.12 }),
    );
  });

  it("disconnects IntersectionObserver on unmount", () => {
    const { unmount } = render(<ScrollRevealWrapper />);
    unmount();
    expect(mockDisconnect).toHaveBeenCalled();
  });

  it("removes landing-reveal class and skips IO when prefers-reduced-motion is set", () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));

    const { container } = render(<ScrollRevealWrapper />);
    const wrapper = container.firstChild as HTMLElement;

    // landing-reveal class should be removed
    expect(wrapper.classList.contains("landing-reveal")).toBe(false);
    // IntersectionObserver should NOT have been constructed
    expect(capturedCallback).toBeNull();
  });

  it("IO callback adds is-visible class and unobserves when entry isIntersecting", () => {
    const { container } = render(<ScrollRevealWrapper />);
    const wrapper = container.firstChild as HTMLElement;

    expect(capturedCallback).not.toBeNull();

    const fakeObs = { unobserve: mockUnobserve } as unknown as IntersectionObserver;
    act(() => {
      capturedCallback!([{ isIntersecting: true, target: wrapper } as IntersectionObserverEntry], fakeObs);
    });

    expect(wrapper.classList.contains("is-visible")).toBe(true);
    expect(mockUnobserve).toHaveBeenCalledWith(wrapper);
  });

  it("IO callback: sets transitionDelay on children when isIntersecting", () => {
    const { container } = render(<ScrollRevealWrapper />);
    const wrapper = container.firstChild as HTMLElement;
    const child = wrapper.firstChild as HTMLElement;

    expect(capturedCallback).not.toBeNull();

    const fakeObs = { unobserve: mockUnobserve } as unknown as IntersectionObserver;
    act(() => {
      capturedCallback!([{ isIntersecting: true, target: wrapper } as IntersectionObserverEntry], fakeObs);
    });

    expect(child.style.transitionDelay).toBe("0ms");
  });

  it("IO callback does nothing when entry isIntersecting is false", () => {
    const { container } = render(<ScrollRevealWrapper />);
    const wrapper = container.firstChild as HTMLElement;

    expect(capturedCallback).not.toBeNull();

    const fakeObs = { unobserve: mockUnobserve } as unknown as IntersectionObserver;
    act(() => {
      capturedCallback!([{ isIntersecting: false, target: wrapper } as IntersectionObserverEntry], fakeObs);
    });

    expect(wrapper.classList.contains("is-visible")).toBe(false);
    expect(mockUnobserve).not.toHaveBeenCalled();
  });
});
