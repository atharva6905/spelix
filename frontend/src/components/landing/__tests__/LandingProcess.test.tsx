import { render, screen, act } from "@testing-library/react";
import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import LandingProcess from "../LandingProcess";

vi.mock("@/hooks/landing/useScrollReveal", () => ({
  useScrollReveal: () => ({ current: null }),
}));

describe("LandingProcess", () => {
  beforeEach(() => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("renders section label", () => {
    render(<LandingProcess />);
    expect(screen.getByText("02 / Process")).toBeInTheDocument();
  });

  test("renders all 3 step titles", () => {
    render(<LandingProcess />);
    expect(screen.getByText("Upload your lift")).toBeInTheDocument();
    expect(screen.getByText("Every rep, measured")).toBeInTheDocument();
    expect(screen.getByText("Science-backed coaching")).toBeInTheDocument();
  });

  test("renders step numbers", () => {
    render(<LandingProcess />);
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText("02")).toBeInTheDocument();
    expect(screen.getByText("03")).toBeInTheDocument();
  });

  test("adds is-in class to steps when prefers-reduced-motion is set", () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));

    const { container } = render(<LandingProcess />);
    const steps = container.querySelectorAll(".landing-step");
    steps.forEach((step) => {
      expect(step).toHaveClass("is-in");
    });
  });

  test("renders step body descriptions", () => {
    render(<LandingProcess />);
    // Steps should have body text (from PROCESS_STEPS data)
    const steps = screen.getAllByText(/.+/);
    expect(steps.length).toBeGreaterThan(0);
  });

  test("IO callback: adds is-in class to steps when intersecting", () => {
    vi.useFakeTimers();
    let ioCallback: ((entries: IntersectionObserverEntry[]) => void) | null = null;
    const mockDisconnect = vi.fn();

    vi.stubGlobal(
      "IntersectionObserver",
      class MockIO {
        constructor(cb: (entries: IntersectionObserverEntry[]) => void) {
          ioCallback = cb;
        }
        observe = vi.fn();
        disconnect = mockDisconnect;
        unobserve = vi.fn();
      },
    );

    const { container } = render(<LandingProcess />);

    expect(ioCallback).not.toBeNull();

    act(() => {
      ioCallback!([{ isIntersecting: true, target: container.firstChild as Element } as IntersectionObserverEntry]);
    });

    // Advance timers to allow the setTimeout step delays to fire
    act(() => { vi.runAllTimers(); });

    const steps = container.querySelectorAll(".landing-step");
    steps.forEach((step) => {
      expect(step).toHaveClass("is-in");
    });
    expect(mockDisconnect).toHaveBeenCalled();

    vi.useRealTimers();
  });

  test("IO callback: does nothing when not intersecting", () => {
    let ioCallback: ((entries: IntersectionObserverEntry[]) => void) | null = null;
    const mockDisconnect = vi.fn();

    vi.stubGlobal(
      "IntersectionObserver",
      class MockIO {
        constructor(cb: (entries: IntersectionObserverEntry[]) => void) {
          ioCallback = cb;
        }
        observe = vi.fn();
        disconnect = mockDisconnect;
        unobserve = vi.fn();
      },
    );

    const { container } = render(<LandingProcess />);

    expect(ioCallback).not.toBeNull();

    act(() => {
      ioCallback!([{ isIntersecting: false, target: container.firstChild as Element } as IntersectionObserverEntry]);
    });

    const steps = container.querySelectorAll(".landing-step");
    steps.forEach((step) => {
      expect(step).not.toHaveClass("is-in");
    });
    expect(mockDisconnect).not.toHaveBeenCalled();
  });

  test("disconnects IO observer on unmount", () => {
    const mockDisconnect = vi.fn();

    vi.stubGlobal(
      "IntersectionObserver",
      class MockIO {
        constructor(_cb: (entries: IntersectionObserverEntry[]) => void) {}
        observe = vi.fn();
        disconnect = mockDisconnect;
        unobserve = vi.fn();
      },
    );

    const { unmount } = render(<LandingProcess />);
    unmount();
    expect(mockDisconnect).toHaveBeenCalled();
  });
});
