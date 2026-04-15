import { useEffect, useRef, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  delay?: number;
  translateY?: number;
  className?: string;
}

export default function ScrollReveal({
  children,
  delay = 0,
  translateY = 20,
  className = "",
}: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduce =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduce) {
      el.style.opacity = "1";
      el.style.transform = "none";
      return;
    }

    if (typeof IntersectionObserver === "undefined") return;

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.animate(
            [
              { opacity: 0, transform: `translateY(${translateY}px)` },
              { opacity: 1, transform: "translateY(0)" },
            ],
            {
              duration: 600,
              delay,
              easing: "ease-out",
              fill: "forwards",
            },
          );
          io.unobserve(entry.target);
        }
      },
      { threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [delay, translateY]);

  return (
    <div ref={ref} style={{ opacity: 0 }} className={className}>
      {children}
    </div>
  );
}
