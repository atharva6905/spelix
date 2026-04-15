import SectionHeading from "./SectionHeading";
import SectionLabel from "./SectionLabel";
import SectionWrapper from "./SectionWrapper";

const FAILURE_MODES: ReadonlyArray<{ title: string; body: string }> = [
  {
    title: "No source.",
    body: "Studies evaluating AI fitness applications against published guidelines have found that only 8% provide any reference to the source of their recommendations (JMIR, 2024). The other 92% just tell you things. An app that confidently asserts your knee angle is off without showing why is not coaching — it is an opinion with a progress bar.",
  },
  {
    title: "No consistency.",
    body: "Across the most popular consumer form-check apps, users regularly report that the same video clip produces different scores and different advice on successive runs. Non-deterministic coaching is not coaching — it is noise with a UI.",
  },
  {
    title: "One body fits all.",
    body: "Real biomechanics is individual. A lifter with long femurs squats differently from one with a short torso. Someone whose arm span exceeds their height has a different optimal deadlift setup than someone whose span is shorter. Most apps calibrate advice to a generic average human who does not exist.",
  },
] as const;

export default function ProblemSection() {
  return (
    <SectionWrapper id="problem">
      <SectionLabel>Introduction</SectionLabel>
      <SectionHeading>
        You've watched yourself lift. You've tried the apps. You know the problem.
      </SectionHeading>

      <div className="mt-12 grid gap-12 md:grid-cols-12">
        <div className="md:col-span-5">
          <p className="font-display text-[96px] leading-none tracking-[-0.03em] text-ink-primary md:text-[128px]">
            8%
          </p>
          <p className="mt-4 font-sans text-sm text-ink-muted">
            of AI fitness apps cite their sources (JMIR, 2024)
          </p>
          <p className="mt-6 font-sans text-base text-ink-primary">
            Every form-check app promises AI-powered feedback. In practice, you
            get a score with no explanation, advice with no source, and answers
            that change every time you re-run the same clip. The best existing
            apps are closer to a confident guess with a clean UI than to coaching.
          </p>
        </div>
        <div className="md:col-span-7">
          <dl className="space-y-8">
            {FAILURE_MODES.map((item) => (
              <div key={item.title}>
                <dt>
                  <h3 className="font-display text-2xl font-normal tracking-[-0.02em] text-ink-primary">
                    {item.title}
                  </h3>
                </dt>
                <dd className="mt-2 font-sans text-base text-ink-primary">
                  {item.body}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-8 font-sans text-base italic text-ink-muted">
            The apps exist. The apps are widely used. And the fitness community
            has known they are not enough for years.
          </p>
        </div>
      </div>
    </SectionWrapper>
  );
}
