import { type RefObject, useEffect, useRef } from "react";
import { useProgressRail } from "@/hooks/landing/useProgressRail";
import { useStickyBar } from "@/hooks/landing/useStickyBar";
import LandingEmailForm from "./LandingEmailForm";

interface LandingChromeProps {
  finalRef: RefObject<HTMLElement | null>;
}

export default function LandingChrome({ finalRef }: LandingChromeProps) {
  const { fillPercent, sections, activeSection } = useProgressRail();
  const { isVisible, dismiss } = useStickyBar(finalRef);
  const dotsRef = useRef<Map<string, HTMLDivElement>>(new Map());

  useEffect(() => {
    if (!activeSection) return;
    dotsRef.current.forEach((dot, id) => {
      if (id === activeSection) {
        dot.classList.add("is-active");
        void dot.offsetWidth;
      } else {
        dot.classList.remove("is-active");
      }
    });
  }, [activeSection]);

  return (
    <>
      {/* Progress rail */}
      <div className="fixed top-0 bottom-0 left-0 z-[150] w-[3px] bg-[rgba(255,255,255,0.04)]">
        <div
          className="absolute top-0 left-0 w-full bg-brand-primary"
          style={{ height: `${fillPercent}%` }}
        />
        {sections.map((sec) => (
          <div
            key={sec.id}
            ref={(el) => {
              if (el) dotsRef.current.set(sec.id, el);
              else dotsRef.current.delete(sec.id);
            }}
            className="absolute left-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-landing-text-muted transition-[transform,background] duration-[350ms] ease-in-out [&.is-active]:bg-brand-primary [&.is-active]:animate-[dotPulse_0.8s_ease]"
            style={{ top: `${sec.topPercent}%` }}
          />
        ))}
      </div>

      {/* Sticky CTA bar */}
      <div
        className={`landing-sticky fixed right-0 bottom-0 left-0 z-[180] flex h-[52px] items-center border-t border-[rgba(255,255,255,0.1)] bg-[rgba(20,18,16,0.95)] backdrop-blur-[12px] ${
          isVisible ? "is-on" : ""
        }`}
      >
        <div className="mx-auto flex w-full max-w-[var(--container-landing)] items-center gap-2 px-[var(--pad,40px)]">
          <span className="mr-3.5 font-landing-mono text-[10px] uppercase tracking-[2px] text-landing-text-muted">
            Request Access
          </span>
          <LandingEmailForm source="hero" size="compact" />
          <button
            onClick={dismiss}
            aria-label="Dismiss"
            className="ml-auto flex h-[30px] w-[30px] items-center justify-center rounded-[2px] border-0 bg-transparent text-[16px] text-landing-text-muted hover:bg-[rgba(255,255,255,0.04)] hover:text-landing-text"
          >
            &times;
          </button>
        </div>
      </div>
    </>
  );
}
