import { useScrollReveal } from "@/hooks/landing/useScrollReveal";
import { PROBLEM_CARDS } from "@/constants/landing";

export default function LandingProblem() {
  const revealRef = useScrollReveal();

  return (
    <section data-section="problem" className="relative py-[110px]">
      <div className="mx-auto max-w-[var(--container-landing)] px-[var(--pad,40px)]">
        <div className="mb-[72px] h-px w-full bg-landing-border-vis" />

        {/* Section header */}
        <div className="mb-[60px] grid grid-cols-[148px_1fr] items-start gap-8 max-landing-sm:grid-cols-1 max-landing-sm:gap-3.5">
          <span className="pt-3.5 font-landing-mono text-[10.5px] uppercase tracking-[2.5px] text-landing-text-muted">
            01 / Problem
          </span>
          <h2 className="max-w-[760px] font-landing-serif text-[clamp(30px,3.8vw,46px)] font-normal leading-[1.08] tracking-[-0.02em] text-landing-text">
            Form checkers that
            <br />
            <em className="text-landing-text-dim">can't be trusted.</em>
          </h2>
        </div>

        {/* Cards */}
        <div
          ref={revealRef}
          className="landing-reveal grid grid-cols-3 gap-px bg-landing-border max-landing-sm:grid-cols-1"
        >
          {PROBLEM_CARDS.map((card) => (
            <div
              key={card.tag}
              className="landing-card relative flex min-h-[280px] flex-col gap-[18px] bg-landing-bg-2 px-9 py-10"
            >
              <span
                className="landing-card-tag absolute top-[18px] right-5 font-landing-mono text-[9px] uppercase tracking-[1.5px]"
                style={{
                  color: card.tagColor ?? "var(--color-landing-text-muted)",
                }}
              >
                {card.tag}
              </span>
              <span className="mt-1.5 font-landing-mono text-2xl leading-none text-landing-text-muted opacity-30">
                ⁄⁄
              </span>
              <h3 className="font-landing-serif text-[21px] text-landing-text">
                {card.title}
              </h3>
              <p className="font-display text-[14.5px] leading-[1.6] text-landing-text-dim">
                {card.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
