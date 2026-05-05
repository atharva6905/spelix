import { useEffect, useRef } from "react";
import { PROCESS_STEPS } from "@/constants/landing";
import { useScrollReveal } from "@/hooks/landing/useScrollReveal";

export default function LandingProcess() {
  const revealRef = useScrollReveal();
  const stepsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = stepsRef.current;
    if (!el) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.querySelectorAll<HTMLElement>(".landing-step").forEach((step) => {
        step.classList.add("is-in");
      });
      return;
    }

    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        const steps = el.querySelectorAll<HTMLElement>(".landing-step");
        steps.forEach((step, i) => {
          setTimeout(() => step.classList.add("is-in"), i * 150);
        });
        io.disconnect();
      },
      { threshold: 0.2 },
    );

    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <section data-section="process" className="relative py-[110px]">
      <div className="mx-auto max-w-[var(--container-landing)] px-[var(--pad,40px)]">
        <div className="mb-[72px] h-px w-full bg-landing-border-vis" />

        {/* Section header */}
        <div
          ref={revealRef}
          className="landing-reveal mb-[60px] grid grid-cols-[148px_1fr] items-start gap-8 max-landing-sm:grid-cols-1 max-landing-sm:gap-3.5"
        >
          <span className="pt-3.5 font-landing-mono text-[10.5px] uppercase tracking-[2.5px] text-landing-text-muted">
            02 / Process
          </span>
          <h2 className="max-w-[760px] font-landing-serif text-[clamp(30px,3.8vw,46px)] font-normal leading-[1.08] tracking-[-0.02em] text-landing-text">
            Analyze. Retrieve.
            <br />
            <em className="text-landing-text-dim">Coach.</em>
          </h2>
        </div>

        {/* Steps */}
        <div
          ref={stepsRef}
          className="grid grid-cols-3 max-landing-sm:grid-cols-1"
        >
          {PROCESS_STEPS.map((step, i) => (
            <div
              key={step.num}
              className={[
                "landing-step",
                i === 0
                  ? "pr-9 max-landing-sm:px-0"
                  : i === PROCESS_STEPS.length - 1
                    ? "border-r-0 pl-9 max-landing-sm:pl-0"
                    : "px-9 max-landing-sm:px-0",
                "border-r border-landing-border py-2",
                "max-landing-sm:border-r-0 max-landing-sm:border-b max-landing-sm:py-6",
              ].join(" ")}
            >
              <div className="mb-6 flex items-center gap-2.5">
                <span className="font-landing-mono text-[10.5px] tracking-[2px] text-brand-primary">
                  {step.num}
                </span>
                <div className="landing-step-rule" />
              </div>
              <h3 className="mb-4 font-landing-serif text-[25px] tracking-[-0.015em] text-landing-text">
                {step.title}
              </h3>
              <p className="font-display text-[15px] leading-[1.62] text-landing-text-dim">
                {step.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
