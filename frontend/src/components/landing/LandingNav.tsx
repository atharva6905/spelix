import { useNavScroll } from "@/hooks/landing/useNavScroll";
import { NAV } from "@/constants/landing";

export default function LandingNav() {
  const isScrolled = useNavScroll();

  return (
    <nav
      className={`landing-nav fixed top-0 left-0 right-0 z-[200] flex h-[54px] items-center border-b border-transparent ${
        isScrolled ? "is-scrolled" : ""
      }`}
    >
      <div className="mx-auto flex w-full max-w-[var(--container-landing)] items-center justify-between px-[var(--pad,40px)]">
        <span className="font-landing-serif text-[21px] italic tracking-[-0.01em] text-landing-text">
          {NAV.wordmark}
        </span>
        <span className="rounded-[2px] border border-brand-primary-bdr bg-brand-primary-soft px-2.5 py-1 font-landing-mono text-[10px] uppercase tracking-[2.5px] text-brand-primary">
          {NAV.badge}
        </span>
      </div>
    </nav>
  );
}
