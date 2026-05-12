import { useEffect, useState } from "react";
import { getBetaCount } from "@/api/beta";
import { HERO } from "@/constants/landing";
import LandingHeroBackground from "./LandingHeroBackground";
import LandingEmailForm from "./LandingEmailForm";

export default function LandingHero() {
  const [countText, setCountText] = useState<string>(HERO.countText);

  useEffect(() => {
    getBetaCount()
      .then(({ count }) => {
        setCountText(`${count} people on the waitlist`);
      })
      .catch(() => {
        // silently fall back to the hardcoded default
      });
  }, []);

  return (
    <header
      data-section="hero"
      className="relative flex min-h-[92vh] items-center overflow-hidden pt-[140px] pb-[110px]"
    >
      <LandingHeroBackground />

      <div className="relative z-2 w-full">
        <div className="mx-auto max-w-[var(--container-landing)] px-[var(--pad,40px)]">
          {/* Overline */}
          <p className="landing-hero-enter he-0 mb-6 font-landing-mono text-[10.5px] uppercase tracking-[2.5px] text-landing-text-muted">
            {HERO.overline}
          </p>

          {/* Heading */}
          <h1 className="landing-hero-enter he-1 mb-8 max-w-[880px] font-landing-serif text-[clamp(52px,7.2vw,86px)] font-normal leading-[1.0] tracking-[-0.025em] text-landing-text">
            <span className="block">{HERO.h1Lines[0]}</span>
            <span className="block">
              <em>{HERO.h1Lines[1]}</em>
            </span>
            <span className="block">{HERO.h1Lines[2]}</span>
          </h1>

          {/* Subtitle */}
          <p className="landing-hero-enter he-2 mb-8 max-w-[530px] font-display text-[18px] font-light leading-[1.68] text-landing-text-dim">
            {HERO.subtitle}
          </p>

          {/* Email form */}
          <div className="landing-hero-enter he-3 mb-[22px]">
            <LandingEmailForm source="hero" />
          </div>

          {/* Meta */}
          <p className="landing-hero-enter he-4 mb-4 font-landing-mono text-[10.5px] uppercase tracking-[1.5px] text-landing-text-muted">
            {HERO.meta}
          </p>

          {/* Waitlist count */}
          <p className="landing-hero-enter he-5 font-landing-mono text-[11px] text-landing-text-muted">
            <span className="mr-1.5 text-[13px] text-brand-primary opacity-55">
              {HERO.countPrefix}
            </span>
            {countText}
          </p>
        </div>
      </div>
    </header>
  );
}
