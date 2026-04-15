export default function NavBar() {
  return (
    <header className="sticky top-0 z-40 w-full bg-surface-dark/90 backdrop-blur">
      <nav className="mx-auto flex max-w-[1128px] items-center justify-between px-6 py-4 md:px-12 lg:px-16">
        <a
          href="#top"
          className="font-display text-xl tracking-tight text-ink-on-dark"
        >
          Spelix
        </a>
        <div className="hidden items-center gap-6 md:flex">
          <a href="#how-it-works" className="font-sans text-base text-ink-on-dark-muted hover:text-ink-on-dark">
            How it works
          </a>
          <a href="#why-spelix" className="font-sans text-base text-ink-on-dark-muted hover:text-ink-on-dark">
            Why Spelix
          </a>
          <a href="#privacy" className="font-sans text-base text-ink-on-dark-muted hover:text-ink-on-dark">
            Privacy
          </a>
        </div>
        <a
          href="#final-cta"
          className="rounded-full bg-brand-primary px-4 py-2 font-sans text-sm font-medium text-ink-primary"
        >
          Request beta access
        </a>
      </nav>
    </header>
  );
}
