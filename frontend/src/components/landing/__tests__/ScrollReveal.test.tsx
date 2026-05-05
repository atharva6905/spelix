import { render, screen, act } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import ScrollReveal from "../ScrollReveal";

describe("ScrollReveal", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  test("renders children", () => {
    render(
      <ScrollReveal>
        <p>hello</p>
      </ScrollReveal>,
    );
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  test("skips animation when prefers-reduced-motion is reduce", () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: true,
      media: "",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    const ioCtor = vi.fn();
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(cb: IntersectionObserverCallback) {
          ioCtor(cb);
        }
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );

    const { container } = render(
      <ScrollReveal>
        <p>hi</p>
      </ScrollReveal>,
    );

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.style.opacity).toBe("1");
    expect(ioCtor).not.toHaveBeenCalled();
  });

  test("creates an IntersectionObserver when motion is not reduced", () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      media: "",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    const observed: Element[] = [];
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(_cb: IntersectionObserverCallback) {}
        observe(el: Element) {
          observed.push(el);
        }
        unobserve() {}
        disconnect() {}
      },
    );

    const { container } = render(
      <ScrollReveal>
        <p>hi</p>
      </ScrollReveal>,
    );

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.style.opacity).toBe("0");
    expect(observed.length).toBe(1);
  });

  test("IntersectionObserver callback animates and unobserves when entry isIntersecting", () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      media: "",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    let capturedCallback: IntersectionObserverCallback | null = null;
    const mockUnobserve = vi.fn();
    const mockDisconnect = vi.fn();

    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(cb: IntersectionObserverCallback) {
          capturedCallback = cb;
        }
        observe() {}
        unobserve = mockUnobserve;
        disconnect = mockDisconnect;
      },
    );

    const { container } = render(
      <ScrollReveal delay={100} translateY={15}>
        <p>hi</p>
      </ScrollReveal>,
    );

    const wrapper = container.firstChild as HTMLElement;
    // Mock animate on the element
    wrapper.animate = vi.fn().mockReturnValue({});

    if (capturedCallback) {
      act(() => {
        capturedCallback!(
          [{ isIntersecting: true, target: wrapper } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      });

      expect(wrapper.animate).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ transform: "translateY(15px)" }),
          expect.objectContaining({ transform: "translateY(0)" }),
        ]),
        expect.objectContaining({ duration: 600, delay: 100 }),
      );
      expect(mockUnobserve).toHaveBeenCalledWith(wrapper);
    }
  });

  test("IntersectionObserver callback: continues (skips) when entry isIntersecting=false", () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      media: "",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    let capturedCallback: IntersectionObserverCallback | null = null;
    const mockUnobserve = vi.fn();

    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(cb: IntersectionObserverCallback) {
          capturedCallback = cb;
        }
        observe() {}
        unobserve = mockUnobserve;
        disconnect() {}
      },
    );

    const { container } = render(
      <ScrollReveal>
        <p>hi</p>
      </ScrollReveal>,
    );

    const wrapper = container.firstChild as HTMLElement;
    wrapper.animate = vi.fn();

    if (capturedCallback) {
      act(() => {
        capturedCallback!(
          [{ isIntersecting: false, target: wrapper } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      });

      expect(wrapper.animate).not.toHaveBeenCalled();
      expect(mockUnobserve).not.toHaveBeenCalled();
    }
  });

  test("disconnects observer on unmount", () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      media: "",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    const mockDisconnect = vi.fn();

    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(_cb: IntersectionObserverCallback) {}
        observe() {}
        unobserve() {}
        disconnect = mockDisconnect;
      },
    );

    const { unmount } = render(
      <ScrollReveal>
        <p>hi</p>
      </ScrollReveal>,
    );

    unmount();
    expect(mockDisconnect).toHaveBeenCalled();
  });
});
