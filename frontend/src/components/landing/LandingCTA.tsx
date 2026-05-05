import { forwardRef } from "react";
import { useScrollReveal } from "@/hooks/landing/useScrollReveal";
import { CTA } from "@/constants/landing";
import LandingEmailForm from "./LandingEmailForm";

const LandingCTA = forwardRef<HTMLElement>(function LandingCTA(_, ref) {
  const revealRef = useScrollReveal();

  return (
    <section
      ref={ref}
      id="final"
      data-section="final"
      className="relative py-[140px] pb-[130px] text-center"
    >
      <div className="mx-auto max-w-[var(--container-landing)] px-[var(--pad,40px)]">
        <div className="mb-20 h-px w-full bg-landing-border-vis" />

        <div ref={revealRef} className="landing-reveal">
          <p className="mb-[30px] font-landing-mono text-[10.5px] uppercase tracking-[3px] text-landing-text-muted">
            {CTA.overline}
          </p>

          <h2 className="mx-auto mb-11 font-landing-serif text-[clamp(38px,5vw,66px)] font-normal leading-[1.05] tracking-[-0.022em] text-landing-text">
            {CTA.headingLine1}
            <br />
            {CTA.headingLine2}
            <em className="text-landing-text-dim">{CTA.headingEmphasis}</em>
          </h2>

          <div className="mx-auto mb-[22px] flex max-w-[460px] justify-center">
            <LandingEmailForm source="final_cta" />
          </div>

          <p className="font-landing-mono text-[10.5px] tracking-[1.5px] text-landing-text-muted">
            {CTA.subtext}
          </p>
        </div>
      </div>
    </section>
  );
});

export default LandingCTA;
