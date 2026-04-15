import { render, screen } from "@testing-library/react";
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
});
