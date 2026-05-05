import { useScrollReveal } from "@/hooks/landing/useScrollReveal";
import { PRIVACY_ITEMS } from "@/constants/landing";

export default function LandingPrivacy() {
  const revealRef = useScrollReveal();

  return (
    <section data-section="privacy" className="relative py-[110px]">
      <div className="mx-auto max-w-[var(--container-landing)] px-[var(--pad,40px)]">
        <div className="mb-[72px] h-px w-full bg-landing-border-vis" />

        {/* Section header */}
        <div className="mb-[60px] grid grid-cols-[148px_1fr] items-start gap-8 max-landing-sm:grid-cols-1 max-landing-sm:gap-3.5">
          <span className="pt-3.5 font-landing-mono text-[10.5px] uppercase tracking-[2.5px] text-landing-text-muted">
            05 / Your Data
          </span>
          <h2 className="max-w-[760px] font-landing-serif text-[clamp(30px,3.8vw,46px)] font-normal leading-[1.08] tracking-[-0.02em] text-landing-text">
            Your movement data
            <br />
            is health data.
            <br />
            <em className="text-landing-text-dim">We treat it that way.</em>
          </h2>
        </div>

        {/* Privacy grid */}
        <div
          ref={revealRef}
          className="landing-reveal grid grid-cols-3 gap-12 max-landing-sm:grid-cols-1 max-landing-sm:gap-[34px]"
        >
          {PRIVACY_ITEMS.map((item) => (
            <div key={item.title}>
              <div className="mb-[22px] h-px bg-landing-border-vis" />
              <h3 className="mb-4 font-landing-serif text-[22px] tracking-[-0.012em] text-landing-text">
                {item.title}
              </h3>
              <p className="font-display text-[14.5px] leading-[1.62] text-landing-text-dim">
                {item.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
