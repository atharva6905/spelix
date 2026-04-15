import BetaDisclaimer from "./BetaDisclaimer";
import EmailCaptureForm from "./EmailCaptureForm";
import SectionHeading from "./SectionHeading";
import SectionLabel from "./SectionLabel";
import { capture } from "@/lib/posthog";

const BETA_USER_GETS = [
  "Full access to all current features, completely free",
  "A direct line to the team — feedback shapes what ships next",
  "Early access to every new feature before public launch",
  "The knowledge that your analyses help calibrate the system for athletes like you",
];

export default function FinalCtaSection() {
  return (
    <section id="final-cta" className="bg-surface-page py-24">
      <div className="mx-auto max-w-[1128px] px-6 md:px-12 lg:px-16">
        <div className="rounded-[40px] bg-surface-dark px-8 py-16 text-ink-on-dark md:px-16 md:py-24">
          <SectionLabel variant="dark">Join the private beta</SectionLabel>
          <SectionHeading variant="dark" className="max-w-3xl">
            You have filmed your lifts. You have watched them back. You have
            wondered what you were missing.
          </SectionHeading>
          <p className="mt-6 max-w-2xl font-sans text-lg text-ink-on-dark-muted">
            Spelix was built by someone who asked the same questions and went
            looking for the answers in the research. The result is an app that
            shows you the study behind every piece of coaching it gives you.
            Beta access is free, limited, and open now.
          </p>

          <ul className="mt-10 grid max-w-3xl gap-3 font-sans text-base text-ink-on-dark md:grid-cols-2">
            {BETA_USER_GETS.map((g) => (
              <li key={g} className="flex items-start gap-3">
                <span
                  aria-hidden="true"
                  className="mt-2 h-1.5 w-1.5 rounded-full bg-brand-primary"
                />
                <span>{g}</span>
              </li>
            ))}
          </ul>

          <div className="mt-10 max-w-xl">
            <EmailCaptureForm
              source="final_cta"
              buttonLabel="Join the private beta"
              microCopy="Free during beta · No credit card · You'll receive an invite link within a few days of signing up."
              onAttempt={() => capture("landing_email_submit_attempt", { cta_location: "final" })}
              onSuccess={(email) =>
                capture("landing_email_submit_success", {
                  cta_location: "final",
                  email_domain: email.split("@")[1] ?? null,
                })
              }
              onError={(status) =>
                capture("landing_email_submit_error", {
                  cta_location: "final",
                  error_code: status,
                })
              }
            />
          </div>
          <div className="mt-8 max-w-xl">
            <BetaDisclaimer variant="dark" withLink={false} />
          </div>
        </div>
      </div>
    </section>
  );
}
