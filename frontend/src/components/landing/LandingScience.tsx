import { useScrollReveal } from "@/hooks/landing/useScrollReveal";
import { useStatsCounter } from "@/hooks/landing/useStatsCounter";
import { SCIENCE, STATS } from "@/constants/landing";

function StatRow({
  target,
  suffix,
  label,
}: {
  target: number;
  suffix: string;
  label: string;
}) {
  const { ref, value, done } = useStatsCounter(target);

  return (
    <div
      ref={ref}
      className={`landing-stat grid grid-cols-[auto_1fr] items-baseline gap-7 border-t border-landing-border-vis py-[26px] last:border-b ${
        done ? "is-done" : ""
      }`}
    >
      <span className="font-landing-serif text-[50px] font-normal leading-none tracking-[-0.025em] text-landing-text">
        {value}
        {suffix && (
          <span className="landing-stat-suffix">{suffix}</span>
        )}
      </span>
      <span className="font-landing-mono text-[10px] uppercase leading-[1.5] tracking-[2px] text-landing-text-muted">
        {label}
      </span>
    </div>
  );
}

export default function LandingScience() {
  const revealRef = useScrollReveal();

  return (
    <section data-section="science" className="relative py-[110px]">
      <div className="mx-auto max-w-[var(--container-landing)] px-[var(--pad,40px)]">
        <div className="mb-[72px] h-px w-full bg-landing-border-vis" />

        <div
          ref={revealRef}
          className="landing-reveal grid grid-cols-[1.05fr_1fr] items-start gap-20 max-landing-sm:grid-cols-1 max-landing-sm:gap-12"
        >
          {/* Left column */}
          <div>
            <span className="mb-6 block font-landing-mono text-[10.5px] uppercase tracking-[2.5px] text-landing-text-muted">
              {SCIENCE.label}
            </span>
            <h2 className="mb-8 font-landing-serif text-[clamp(34px,3.6vw,46px)] font-normal leading-[1.1] tracking-[-0.02em] text-landing-text">
              {SCIENCE.leadLines.map((line, i) =>
                line.italic ? (
                  <em key={i} className="block text-landing-text-dim">
                    {line.text}
                  </em>
                ) : (
                  <span key={i} className="block">
                    {line.text}
                  </span>
                ),
              )}
            </h2>
            <p className="mb-8 max-w-[460px] font-display text-[16px] font-light leading-[1.65] text-landing-text-dim">
              {SCIENCE.bodyPrefix}
              {SCIENCE.journals.map((journal, i) => (
                <span key={journal}>
                  <em>{journal}</em>
                  {i < SCIENCE.journals.length - 1 ? ", " : ""}
                </span>
              ))}
              {SCIENCE.bodySuffix}
            </p>
            <blockquote className="max-w-[480px] border border-brand-primary-bdr bg-brand-primary-soft px-6 py-[22px] font-landing-serif text-[14.5px] italic leading-[1.55] text-landing-text-dim">
              {SCIENCE.expertQuote}
            </blockquote>
          </div>

          {/* Right column — stats */}
          <div>
            {STATS.map((stat) => (
              <StatRow key={stat.label} {...stat} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
