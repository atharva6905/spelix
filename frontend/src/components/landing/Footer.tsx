import BetaDisclaimer from "./BetaDisclaimer";

export default function Footer() {
  return (
    <footer className="border-t border-border-subtle bg-surface-page py-12">
      <div className="mx-auto grid max-w-[1128px] gap-8 px-6 md:grid-cols-12 md:px-12 lg:px-16">
        <div className="md:col-span-4">
          <p className="font-display text-2xl tracking-tight text-ink-primary">
            Spelix
          </p>
          <p className="mt-2 font-sans text-sm text-ink-muted">
            Built in collaboration with a Kinesiology-specialist B.Sc. candidate.
          </p>
        </div>
        <div className="md:col-span-5">
          <BetaDisclaimer withLink={false} />
        </div>
        <nav className="flex flex-col gap-2 font-sans text-sm md:col-span-3">
          <a href="/beta-terms" className="text-ink-primary underline">
            Beta terms
          </a>
        </nav>
      </div>
    </footer>
  );
}
