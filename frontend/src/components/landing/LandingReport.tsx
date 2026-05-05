import type { CSSProperties } from "react";
import { useScrollReveal } from "@/hooks/landing/useScrollReveal";
import { useTypewriter } from "@/hooks/landing/useTypewriter";
import {
  DIMENSION_CARDS,
  SNIPPET_CITATIONS,
  SNIPPET_LABEL_FINAL,
  SNIPPET_LABEL_INITIAL,
  SNIPPET_TEXT,
} from "@/constants/landing";

export default function LandingReport() {
  const revealRef = useScrollReveal();
  const { ref: snippetRef, displayText, isDone } = useTypewriter(SNIPPET_TEXT);

  return (
    <section data-section="report" className="relative py-[110px]">
      <div className="mx-auto max-w-[var(--container-landing)] px-[var(--pad,40px)]">
        <div className="mb-[72px] h-px w-full bg-landing-border-vis" />

        {/* Section header */}
        <div className="mb-[60px] grid grid-cols-[148px_1fr] items-start gap-8 max-landing-sm:grid-cols-1 max-landing-sm:gap-3.5">
          <span className="pt-3.5 font-landing-mono text-[10.5px] uppercase tracking-[2.5px] text-landing-text-muted">
            03 / Report
          </span>
          <h2 className="max-w-[760px] font-landing-serif text-[clamp(30px,3.8vw,46px)] font-normal leading-[1.08] tracking-[-0.02em] text-landing-text">
            Four dimensions.
            <br />
            <em className="text-landing-text-dim">Per rep.</em>
          </h2>
        </div>

        {/* Dimension grid */}
        <div
          ref={revealRef}
          className="landing-reveal mb-px grid grid-cols-2 gap-px bg-landing-border max-landing-sm:grid-cols-1"
        >
          {DIMENSION_CARDS.map((dim) => (
            <div
              key={dim.index}
              className="landing-dim flex min-h-[230px] flex-col gap-3.5 border-t border-transparent bg-landing-bg-2 px-9 pt-9 pb-7"
            >
              <span className="font-landing-mono text-[10px] uppercase tracking-[2px] text-landing-text-muted">
                {dim.index}
              </span>
              <h3 className="font-landing-serif text-[21px] text-landing-text">
                {dim.name}
              </h3>
              <p className="font-display text-[14.5px] leading-[1.6] text-landing-text-dim">
                {dim.description}
              </p>
              {/* Spark bars */}
              <div className="landing-spark mt-auto flex h-[34px] items-end gap-1.5">
                {dim.sparks.map((s, i) => (
                  <div
                    key={i}
                    className="landing-spark-bar w-3.5 bg-brand-primary"
                    style={
                      {
                        "--spark-h": s.h,
                        opacity: s.opacity,
                      } as CSSProperties
                    }
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Snippet */}
        <div
          ref={snippetRef}
          className="relative mt-px border-l-2 border-brand-primary bg-landing-surface px-[38px] py-[34px]"
        >
          <span className="mb-[18px] block font-landing-mono text-[10px] uppercase tracking-[2px] text-landing-text-muted">
            {isDone ? SNIPPET_LABEL_FINAL : SNIPPET_LABEL_INITIAL}
          </span>
          <p className="min-h-[120px] font-landing-serif text-[17px] italic leading-[1.6] text-landing-text-dim">
            {displayText}
            {!isDone && <span className="landing-snippet-cursor" />}
          </p>
          <div
            className={`landing-snippet-cite mt-[22px] flex flex-wrap gap-x-7 gap-y-0 font-landing-mono text-[11px] leading-[1.8] tracking-[0.5px] text-[rgba(213,255,69,0.75)] ${
              isDone ? "is-visible" : ""
            }`}
          >
            {SNIPPET_CITATIONS.map((cite) => (
              <span key={cite}>{cite}</span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
