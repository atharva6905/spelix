import { useEffect, useRef } from "react";

export function useScrollReveal(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.classList.remove("landing-reveal");
      return;
    }

    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;

        Array.from(el.children).forEach((child, i) => {
          (child as HTMLElement).style.transitionDelay = `${i * 80}ms`;
        });

        el.classList.add("is-visible");

        setTimeout(() => {
          Array.from(el.children).forEach((child) => {
            (child as HTMLElement).style.transitionDelay = "";
          });
        }, 1000);

        io.unobserve(el);
      },
      { threshold },
    );

    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);

  return ref;
}
