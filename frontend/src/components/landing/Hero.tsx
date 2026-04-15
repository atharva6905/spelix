import BetaDisclaimer from "./BetaDisclaimer";
import EmailCaptureForm from "./EmailCaptureForm";
import SectionHeading from "./SectionHeading";

export default function Hero() {
  return (
    <section
      id="top"
      className="relative w-full overflow-hidden bg-surface-dark text-ink-on-dark"
    >
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[url('/landing/hero-bg.webp')] bg-cover bg-center opacity-60"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-gradient-to-b from-surface-dark/30 to-surface-dark"
      />
      <div className="relative mx-auto grid max-w-[1128px] gap-12 px-6 pb-24 pt-24 md:grid-cols-12 md:px-12 md:pb-32 md:pt-32 lg:px-16">
        <div className="md:col-span-7">
          <SectionHeading as="h1" variant="dark" className="max-w-3xl">
            Barbell form coaching where every piece of feedback cites its source.
          </SectionHeading>
          <p className="mt-6 max-w-xl font-sans text-lg text-ink-on-dark-muted">
            Spelix analyses your squat, bench, or deadlift with computer vision
            and generates structured coaching grounded in peer-reviewed
            biomechanics literature. Every claim is traceable to the study behind it.
          </p>
          <div className="mt-8 max-w-xl">
            <EmailCaptureForm source="hero" />
          </div>
          <div className="mt-6 max-w-xl">
            <BetaDisclaimer variant="dark" />
          </div>
        </div>
        <div className="hidden md:col-span-5 md:block">
          <img
            src="/landing/results-screenshot.png"
            alt="Spelix Results page showing streaming coaching text with a citation tooltip expanded and four dimension score cards"
            className="rounded-[40px] shadow-2xl"
            loading="eager"
            decoding="async"
          />
        </div>
      </div>
    </section>
  );
}
