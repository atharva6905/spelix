import { FOOTER, NAV } from "@/constants/landing";

export default function LandingFooter() {
  return (
    <footer className="border-t border-landing-border-vis pt-8 pb-7">
      <div className="mx-auto max-w-[var(--container-landing)] px-[var(--pad,40px)]">
        <div className="grid grid-cols-3 items-center gap-5 max-landing-sm:grid-cols-1 max-landing-sm:text-center">
          {/* Left — wordmark */}
          <a
            href="#"
            className="font-landing-serif text-[18px] italic text-landing-text no-underline"
          >
            {NAV.wordmark}
          </a>

          {/* Center — copyright */}
          <span className="text-center font-landing-mono text-[10px] tracking-[1.5px] text-landing-text-muted">
            {FOOTER.copyright}
          </span>

          {/* Right — links */}
          <div className="flex gap-[18px] justify-self-end font-landing-mono text-[10px] uppercase tracking-[1.5px] text-landing-text-muted max-landing-sm:justify-self-center">
            {FOOTER.links.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-landing-text-muted no-underline hover:text-landing-text-dim"
              >
                {link.label}
              </a>
            ))}
          </div>
        </div>

        {/* Legal */}
        <p className="mx-auto mt-[22px] max-w-[var(--container-landing)] font-display text-[11px] leading-[1.6] text-landing-text-muted">
          {FOOTER.legal}
        </p>
      </div>
    </footer>
  );
}
